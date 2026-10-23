"""在隔离目录和本机模拟服务上验证交付包，真实数据库仅通过只读连接制作副本。"""

import argparse
import base64
import copy
from contextlib import closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MODELS = ["gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol",
          "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5"]
MARKER = "gpt-daybreak-red-latest"

# 可选测试依赖只从本轮工作目录读取，不修改系统 Python。
validation_dependencies = Path(__file__).resolve().parent / "validation-deps"
if validation_dependencies.is_dir():
    sys.path.insert(0, str(validation_dependencies))


class Rpc:
    def __init__(self, binary, home, cwd):
        self.log = tempfile.TemporaryFile()
        env = dict(os.environ)
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_SQLITE_HOME"):
            env.pop(key, None)
        env.update(CODEX_HOME=str(home), CODEX_APP_SERVER_DISABLE_MANAGED_CONFIG="1")
        command = [str(binary)]
        command += ["app-server", "--listen", "stdio://"]
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.log, env=env, cwd=cwd, bufsize=0)
        self.rows = queue.Queue()
        self.pending = []
        self.serial = 0
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.proc.stdout:
            try:
                self.rows.put(json.loads(line))
            except ValueError:
                self.rows.put({"invalid_stdout": line.decode(errors="replace")[:200]})
        self.rows.put({"process_exited": self.proc.poll()})

    def wait(self, predicate, timeout=60):
        for index, row in enumerate(self.pending):
            if predicate(row):
                return self.pending.pop(index)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                row = self.rows.get(timeout=max(0.1, deadline - time.monotonic()))
            except queue.Empty:
                break
            if "process_exited" in row or "invalid_stdout" in row:
                raise RuntimeError(str(row))
            if predicate(row):
                return row
            self.pending.append(row)
        raise TimeoutError("等待 App Server 响应超时")

    def request(self, method, params, expect_error=False):
        self.serial += 1
        serial = self.serial
        self.proc.stdin.write((json.dumps({"id": serial, "method": method, "params": params}) + "\n").encode())
        self.proc.stdin.flush()
        row = self.wait(lambda item: item.get("id") == serial)
        if expect_error:
            assert "error" in row, (method, "应拒绝该请求")
            return row["error"]
        assert "error" not in row, (method, row.get("error"))
        return row["result"]

    def initialize(self):
        result = self.request("initialize", {"clientInfo": {"name": "codex_release_probe", "version": "1"},
                                             "capabilities": {"experimentalApi": True}})
        self.proc.stdin.write(b'{"method":"initialized"}\n')
        self.proc.stdin.flush()
        return result

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        self.log.seek(0)
        log = self.log.read().decode(errors="replace")
        self.log.close()
        assert "was previously applied but has been modified" not in log, "数据库迁移校验失败"
        assert "unrecognized configuration setting" not in log, "验证夹具包含已不支持的配置字段"
        return log


def write_fixture(home, template, endpoint, transport="http"):
    models = []
    for name in MODELS + ["gpt-6-astra"]:
        item = copy.deepcopy(template)
        item.update(slug=name, display_name=name, visibility="list", priority=len(models),
                    tool_mode="code_mode_only", prefer_websockets=(transport == "websocket"),
                    model_messages={"instructions_template": "本机模拟服务的验证任务。", "instructions_variables": {}},
                    available_access_programs={"cyber": ["standard"] if name == "gpt-6-astra" else ["standard", "daybreak_blue"]})
        models.append(item)
    catalog = home / "models.json"
    catalog.write_text(json.dumps({"models": models}), encoding="utf-8")
    config = f'''model = "gpt-6.1-sol"
model_provider = "openai"
model_catalog_json = {json.dumps(catalog.as_posix())}
approval_policy = "never"
sandbox_mode = "danger-full-access"
cli_auth_credentials_store = "file"
chatgpt_base_url = "{endpoint}/backend-api"
[features]
code_mode = true
code_mode_host = {{ enabled = true, disable_in_process_fallback = true }}
[model_providers.openai]
name = "本地验证 provider"
base_url = "{endpoint}/v1"
requires_openai_auth = true
supports_websockets = {str(transport == "websocket").lower()}
capabilities = {{ external_web_access = false, remote_compaction = "unsupported" }}
experimental_bearer_token = "release-test-key"
http_headers = {{"X-Release-Probe" = "custom-openai"}}
query_params = {{"release_probe" = "1"}}
'''
    (home / "config.toml").write_text(config, encoding="utf-8")
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    token = encode({"alg": "none"}) + "." + encode({"email": "test@example.invalid", "exp": int(time.time()) + 86400,
        "https://api.openai.com/auth": {"chatgpt_plan_type": "pro", "chatgpt_account_id": "release-local-test"}}) + ".c2lnbmF0dXJl"
    auth = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
            "tokens": {"id_token": token, "access_token": "fake-local-access-token", "refresh_token": "fake-local-refresh-token", "account_id": "release-local-test"},
            "last_refresh": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (home / "auth.json").write_text(json.dumps(auth), encoding="utf-8")
    return hashlib.sha256(catalog.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--database-source", type=Path)
    parser.add_argument("--transport", choices=["http", "websocket"], default="http")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    result = {"platform": os.name, "version": subprocess.check_output([str(binary), "--version"], text=True).strip(),
              "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "transport": args.transport, "checks": [], "captured": []}
    assert result["version"] == "codex-cli 0.164.0", result["version"]
    template = next(item for item in json.loads(args.catalog.read_text(encoding="utf-8"))["models"] if item["slug"] == "gpt-5.5")
    captured = []
    tool_outputs = []
    next_tool = {"code": None}

    def process_response(body, headers, path, transport):
        warmup = body.get("generate") is False
        if not warmup:
            captured.append({"model": body.get("model"), "access_programs": body.get("access_programs"),
                             "path": path, "transport": transport, "custom_header": headers.get("X-Release-Probe"),
                             "custom_auth": headers.get("Authorization") == "Bearer release-test-key"})
        tool_outputs.extend(item for item in body.get("input", []) if item.get("type") in ("custom_tool_call_output", "function_call_output"))
        rid = "resp-release-" + str(len(captured)) + ("-warmup" if warmup else "")
        events = [{"type": "response.created", "response": {"id": rid}}]
        if not warmup and next_tool["code"] is not None:
            events.append({"type": "response.output_item.done", "item": {"type": "custom_tool_call", "call_id": "release-tool-call",
                "name": "exec", "input": next_tool["code"]}})
            next_tool["code"] = None
        elif not warmup:
            events.append({"type": "response.output_item.done", "item": {"type": "message", "role": "assistant", "id": "msg-release",
                "content": [{"type": "output_text", "text": "本机验证完成。"}]}})
        events.append({"type": "response.completed", "response": {"id": rid, "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}})
        return events

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.headers.get("Upgrade", "").lower() != "websocket":
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            key = self.headers["Sec-WebSocket-Key"]
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.close_connection = True

            def receive(size):
                value = self.rfile.read(size)
                if len(value) != size:
                    raise EOFError
                return value

            def send(payload, opcode=1):
                header = bytes([128 | opcode])
                size = len(payload)
                header += bytes([size]) if size < 126 else (bytes([126]) + struct.pack("!H", size) if size < 65536 else bytes([127]) + struct.pack("!Q", size))
                self.connection.sendall(header + payload)

            fragments = bytearray()
            try:
                while True:
                    first, second = receive(2)
                    opcode = first & 15
                    size = second & 127
                    if size == 126:
                        size = struct.unpack("!H", receive(2))[0]
                    elif size == 127:
                        size = struct.unpack("!Q", receive(8))[0]
                    mask = receive(4) if second & 128 else None
                    payload = receive(size)
                    if mask:
                        payload = bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
                    if opcode == 8:
                        send(payload, 8)
                        return
                    if opcode == 9:
                        send(payload, 10)
                        continue
                    if opcode == 10:
                        continue
                    fragments.extend(payload)
                    if first & 128:
                        body = json.loads(fragments)
                        fragments.clear()
                        assert body.get("type") == "response.create", body.get("type")
                        for event in process_response(body, self.headers, self.path, "websocket"):
                            send(json.dumps(event).encode())
            except (EOFError, ConnectionError, OSError):
                return

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if "/responses" not in self.path:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.headers.get("Content-Encoding") == "zstd":
                import zstandard
                raw = zstandard.ZstdDecompressor().decompress(raw)
            events = process_response(json.loads(raw), self.headers, self.path, "http")
            data = "".join("event: " + item["type"] + "\ndata: " + json.dumps(item) + "\n\n" for item in events).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="codex-release-probe-") as root:
        root = Path(root)
        home = root / "home"
        work = root / "work"
        home.mkdir()
        work.mkdir()
        original_migrations = {}
        if args.database_source:
            for src in sorted(args.database_source.glob("*.sqlite")):
                with closing(sqlite3.connect(src.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                    has_table = source.execute("SELECT 1 FROM sqlite_master WHERE name='_sqlx_migrations'").fetchone()
                    if not has_table:
                        continue
                    rows = source.execute("SELECT version, hex(checksum) FROM _sqlx_migrations ORDER BY version").fetchall()
                    with closing(sqlite3.connect(home / src.name)) as dest:
                        source.backup(dest)
                original_migrations[src.name] = rows
        original_catalog = write_fixture(home, template, f"http://127.0.0.1:{server.server_port}", args.transport)
        app = None
        logs = []
        try:
            app = Rpc(binary, home, work)
            app.initialize()
            config = app.request("config/read", {"includeLayers": False})["config"]
            assert config["model_provider"] == "openai"
            assert config["model_providers"]["openai"]["name"] == "本地验证 provider"
            assert config["model_providers"]["openai"]["capabilities"] == {
                "external_web_access": False, "remote_compaction": "unsupported"
            }
            result["checks"].append("custom_provider_capability_overrides")
            host_setting = config["features"]["code_mode_host"]
            assert host_setting["enabled"] is True and host_setting["disable_in_process_fallback"] is True
            result["checks"].append("initialize_and_custom_openai_config")
            models = []
            cursor = None
            while True:
                page = app.request("model/list", {"limit": 2, "cursor": cursor, "includeHidden": True})
                models.extend(page["data"])
                cursor = page["nextCursor"]
                if cursor is None:
                    break
            assert MARKER not in [item["model"] for item in models]
            assert sorted(item["model"] for item in models) == sorted(MODELS + ["gpt-6-astra"])
            result["checks"].append("paginated_real_model_list_without_synthetic_marker")
            assert "include_internal_metadata" not in config["model_providers"]["openai"]
            assert "experimental_daybreak_app_compat" not in config["model_providers"]["openai"]
            result["checks"].append("runtime_internal_fields_and_legacy_compat_absent")
            app.request("config/value/write", {"keyPath": "model_providers.openai.name", "value": "本地验证 provider",
                                                "mergeStrategy": "replace", "filePath": str(home / "config.toml")})
            written = app.request("config/read", {"includeLayers": False})["config"]["model_providers"]["openai"]
            assert written["name"] == "本地验证 provider" and written["base_url"] == config["model_providers"]["openai"]["base_url"]
            result["checks"].append("custom_openai_definition_is_writable")
            started = app.request("thread/start", {"model": MODELS[0], "modelProvider": "openai", "cwd": str(work), "daybreakEnabled": True})
            thread_id = started["thread"]["id"]

            def turn(model, program):
                response = app.request("turn/start", {"threadId": thread_id, "model": model, "cyberAccessProgram": program,
                    "input": [{"type": "text", "text": "本机测试", "textElements": []}], "effort": "low"})
                turn_id = response["turn"]["id"]
                event = app.wait(lambda row: row.get("method") == "turn/completed" and row["params"]["turn"]["id"] == turn_id)
                assert event["params"]["turn"]["status"] == "completed", event

            for model in MODELS:
                for rpc_program, body_program in [("daybreakBlue", "daybreak_blue"), ("standard", "standard")]:
                    before = len(captured)
                    turn(model, rpc_program)
                    assert len(captured) == before + 1
                    assert captured[-1]["model"] == model
                    assert captured[-1]["transport"] == args.transport
                    assert captured[-1]["access_programs"] == {"cyber": body_program}
                    assert captured[-1]["custom_header"] == "custom-openai" and captured[-1]["custom_auth"]
                    assert "release_probe=1" in captured[-1]["path"]
            result["checks"].append("seven_models_blue_standard_and_custom_transport")
            next_tool["code"] = 'text("CODE_MODE_HOST_RELEASE_OK");'
            turn(MODELS[0], "standard")
            assert "CODE_MODE_HOST_RELEASE_OK" in json.dumps(tool_outputs), tool_outputs
            helper = binary.parent / ("codex-code-mode-host.exe" if os.name == "nt" else "codex-code-mode-host")
            helper = helper.resolve(strict=True)
            if os.name == "nt":
                command = f'Get-CimInstance Win32_Process -Filter "ParentProcessId = {app.proc.pid}" | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress'
                raw = subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", command], text=True).strip()
                processes = json.loads(raw) if raw else []
                if isinstance(processes, dict):
                    processes = [processes]
                observed = [row["ProcessId"] for row in processes if row.get("ExecutablePath") and Path(row["ExecutablePath"]).resolve() == helper]
            else:
                observed = []
                for proc in Path("/proc").glob("[0-9]*"):
                    try:
                        parent = next(line.split()[1] for line in (proc / "status").read_text().splitlines() if line.startswith("PPid:"))
                        if int(parent) == app.proc.pid and (proc / "exe").resolve(strict=True) == helper:
                            observed.append(int(proc.name))
                    except (OSError, StopIteration):
                        pass
            assert observed, "未观察到交付包代码宿主子进程"
            result["code_mode_host"] = {"path": str(helper), "sha256": hashlib.sha256(helper.read_bytes()).hexdigest(), "observed_pids": observed, "fallback_disabled": True}
            result["checks"].append("real_code_mode_host_execution_without_fallback")
            output_count = len(tool_outputs)
            next_tool["code"] = 'text(await tools.exec_command({cmd:"echo CODEX_SHELL_RELEASE_OK"}));'
            turn(MODELS[0], "standard")
            shell_output = json.dumps(tool_outputs[output_count:])
            assert "CODEX_SHELL_RELEASE_OK" in shell_output and "exit_code" in shell_output, shell_output
            result["checks"].append("code_mode_exec_command")
            logs.append(app.close())
            app = Rpc(binary, home, work)
            app.initialize()
            disabled_models = app.request("model/list", {"limit": 100, "includeHidden": True})["data"]
            assert MARKER not in [item["model"] for item in disabled_models]
            result["checks"].append("restarted_model_list_has_no_synthetic_marker")
            resumed = app.request("thread/resume", {"threadId": thread_id})
            assert resumed["thread"]["daybreakEnabled"] is True
            result["checks"].append("persisted_thread_resume")
            assert hashlib.sha256((home / "models.json").read_bytes()).hexdigest() == original_catalog
            result["checks"].append("catalog_unchanged")
            logs.append(app.close())
            app = None
            real_catalog = json.loads((home / "models.json").read_text(encoding="utf-8"))
            real_red = copy.deepcopy(real_catalog["models"][0])
            real_red.update(slug="release-real-red", display_name="真实 Red 测试模型", available_access_programs={"cyber": ["daybreak_red"]})
            real_catalog["models"].append(real_red)
            (home / "models.json").write_text(json.dumps(real_catalog), encoding="utf-8")
            red_catalog_hash = hashlib.sha256((home / "models.json").read_bytes()).hexdigest()
            app = Rpc(binary, home, work)
            app.initialize()
            red_models = app.request("model/list", {"limit": 100, "includeHidden": True})["data"]
            assert MARKER not in [item["model"] for item in red_models]
            assert next(item for item in red_models if item["model"] == "release-real-red")["availableAccessPrograms"] == {"cyber": ["daybreakRed"]}
            assert hashlib.sha256((home / "models.json").read_bytes()).hexdigest() == red_catalog_hash
            result["checks"].append("real_red_catalog_metadata_preserved")
            logs.append(app.close())
            app = None
            fixture_config = (home / "config.toml").read_text(encoding="utf-8")
            fixture_auth = (home / "auth.json").read_text(encoding="utf-8")
            blue_catalog = {"models": real_catalog["models"][:-1]}

            (home / "models.json").write_text(json.dumps(blue_catalog), encoding="utf-8")
            api_auth = json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "fake-local-api-key"})
            (home / "auth.json").write_text(api_auth, encoding="utf-8")
            # 新版 API-key 会话的程序开关仍受上游功能门槛约束。
            (home / "config.toml").write_text(
                fixture_config.replace("[features]\n", "[features]\napi_key_cyber_access_programs = false\n"),
                encoding="utf-8",
            )
            app = Rpc(binary, home, work)
            app.initialize()
            api_thread = app.request("thread/start", {"model": MODELS[0], "cwd": str(work)})["thread"]["id"]
            before = len(captured)
            api_turn = app.request("turn/start", {
                "threadId": api_thread, "cyberAccessProgram": "daybreakBlue",
                "input": [{"type": "text", "text": "验证 API-key 功能门槛", "textElements": []}],
            })["turn"]["id"]
            api_event = app.wait(lambda row: row.get("method") == "turn/completed" and row["params"]["turn"]["id"] == api_turn)
            assert api_event["params"]["turn"]["status"] == "failed", api_event
            assert "Cyber access programs are disabled for this API-key session" in json.dumps(api_event), api_event
            assert len(captured) == before
            result["checks"].append("upstream_api_key_program_gate_preserved")
            logs.append(app.close())
            app = None
            # 保留 0.164.0 的原生默认策略，验证 API-key 显式选择仍按真实目录发送。
            (home / "config.toml").write_text(fixture_config, encoding="utf-8")
            app = Rpc(binary, home, work)
            app.initialize()
            api_thread = app.request("thread/start", {"model": MODELS[0], "cwd": str(work)})["thread"]["id"]
            for rpc_program, body_program in [("daybreakBlue", "daybreak_blue"), ("standard", "standard")]:
                before = len(captured)
                api_turn = app.request("turn/start", {
                    "threadId": api_thread, "cyberAccessProgram": rpc_program,
                    "input": [{"type": "text", "text": "验证 API-key 默认程序转发", "textElements": []}],
                })["turn"]["id"]
                event = app.wait(lambda row: row.get("method") == "turn/completed" and row["params"]["turn"]["id"] == api_turn)
                assert event["params"]["turn"]["status"] == "completed", event
                assert len(captured) == before + 1
                assert captured[-1]["model"] == MODELS[0]
                assert captured[-1]["access_programs"] == {"cyber": body_program}
                assert captured[-1]["transport"] == args.transport
            result["checks"].append("api_key_default_program_forwarding")
            logs.append(app.close())
            app = None
        finally:
            if app is not None:
                logs.append(app.close()) if app.proc.poll() is None else None
            server.shutdown()
            server.server_close()
            args.output.with_suffix(".stderr.log").write_text("\n".join(logs), encoding="utf-8")
        db_results = []
        for name, before_rows in original_migrations.items():
            with closing(sqlite3.connect(home / name)) as db:
                rows = db.execute("SELECT version, hex(checksum) FROM _sqlx_migrations ORDER BY version").fetchall()
                assert dict(rows).items() >= dict(before_rows).items(), name
                assert db.execute("PRAGMA quick_check").fetchone() == ("ok",), name
                db_results.append({"database": name, "old_migrations": len(before_rows), "new_migrations": len(rows)})
        result["database_copies"] = db_results
        result["captured"] = captured
    result["passed"] = True
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "version": result["version"], "checks": result["checks"],
                      "database_copies": result["database_copies"], "transport": args.transport, "inference_requests": len(captured)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

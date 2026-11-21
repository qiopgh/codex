"""用最终完整包复现 Windows App 的根目录布局，并验证独立 App Server 和数据库副本。"""

import argparse
from contextlib import closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from validate_release import Rpc, write_fixture


class AuxiliaryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """按官方协议返回模拟工作区，其余辅助接口返回空对象。"""
        body = {}
        if self.path.split("?", 1)[0].endswith("/wham/accounts/check"):
            body = {"accounts": [{
                "id": self.server.account_id,
                "name": "本机验证工作区",
                "workspace_backend_origin": self.server.workspace_origin,
                "account_routing_override": "NO_CONSTRAINT",
            }]}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def do_POST(self):
        """这项测试只验证启动，不允许向本机模拟服务发起推理。"""
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path.split("?", 1)[0].endswith("/responses"):
            self.server.inference_requests += 1
            self.send_error(400)
            return
        self.do_GET()

    def log_message(self, *_args):
        pass


def stage_app_layout(package, root, version):
    """复现部署到 App 专用目录时实际采用的文件名及布局。"""
    build = json.loads((package / "custom-build.json").read_text(encoding="utf-8-sig"))
    layout = json.loads((package / "codex-package.json").read_text(encoding="utf-8-sig"))
    assert build["version"] == layout["version"] == version
    assert layout["layoutVersion"] == 1
    assert layout["entrypoint"] == "bin/codex.exe" and layout["execServer"] == "bin/codex-exec-server.exe"
    files = {item["path"]: item for item in build["files"]}
    executor_path = Path(layout["execServer"])
    staged = {}
    for key in files:
        relative = Path(key)
        assert not relative.is_absolute() and ".." not in relative.parts
        if key != "codex-package.json":
            staged[relative.relative_to("bin") if relative.parts[0] == "bin" else relative] = package / relative
    # 保留独立执行服务的标准 bin 路径，使它也能从父目录读取版本元数据。
    staged[executor_path] = package / executor_path
    for name in ("codex-command-runner.exe", "codex-windows-sandbox-setup.exe", "codex-windows-sandbox-service.exe"):
        staged[Path(name)] = package / layout["resourcesDir"] / name

    for relative, source in staged.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    layout["entrypoint"] = "codex.exe"
    metadata = root / "codex-package.json"
    metadata.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
    executable_hashes = {}
    for name in (layout["entrypoint"], executor_path.name, "codex-code-mode-host.exe"):
        path = executor_path if name == executor_path.name else Path(name)
        with (root / path).open("rb") as stream:
            executable_hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        assert executable_hashes[name] == files["bin/" + name]["sha256"], name
    return layout, len(staged) + 1, executable_hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="已解压并校验的 Windows 完整包")
    parser.add_argument("--catalog", type=Path, required=True, help="构建对应的官方模型目录模板")
    parser.add_argument("--database-source", type=Path, required=True, help="升级前 SQLite 一致性备份所在目录")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-version", default="0.171.0")
    args = parser.parse_args()
    assert os.name == "nt", "此验证需要 Windows"
    package = args.package.resolve(strict=True)
    expected_version = args.expected_version
    template = next(model for model in json.loads(args.catalog.read_text(encoding="utf-8"))["models"]
                    if model["slug"] == "gpt-5.5")
    server = ThreadingHTTPServer(("127.0.0.1", 0), AuxiliaryHandler)
    server.inference_requests = 0
    server.workspace_origin = f"https://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    logs = ""
    try:
        with tempfile.TemporaryDirectory(prefix="codex-app-root-") as temporary:
            base = Path(temporary)
            app_root = base / "bin"
            home = base / "home"
            work = base / "work"
            work.mkdir()
            layout, file_count, executable_hashes = stage_app_layout(package, app_root, expected_version)
            binary = app_root / layout["entrypoint"]
            version = subprocess.check_output([str(binary), "--version"], cwd=work, text=True, timeout=30).strip()
            assert version == f"codex-cli {expected_version}", version

            # 使用已有备份脚本，测试仍在单独的 SQLite 副本上运行。
            subprocess.run(
                [sys.executable, "-X", "utf8", str(Path(__file__).with_name("backup_windows_cli_databases.py")),
                 str(args.database_source.resolve(strict=True)), str(home)],
                check=True,
            )
            snapshots = json.loads((home / "backup-manifest.json").read_text(encoding="utf-8"))
            assert len(snapshots) >= 7 and any(item["database"] == "state_5.sqlite" for item in snapshots), snapshots
            write_fixture(home, template, endpoint)
            # 读取测试刚生成的模拟身份，使探针与夹具的工作区标识吻合。
            server.account_id = json.loads((home / "auth.json").read_text(encoding="utf-8"))["tokens"]["account_id"]
            app = Rpc(binary, home, work)
            try:
                initialized = app.initialize()
                assert initialized["platformOs"] == "windows"
                assert Path(initialized["codexHome"]).resolve() == home.resolve()
                config = app.request("config/read", {"includeLayers": False})["config"]
                assert config["model_provider"] == "openai"
                assert config["model_providers"]["openai"]["base_url"] == endpoint + "/v1"
                account = app.request("account/read", {"refreshToken": False})
                assert account["requiresOpenaiAuth"] is True and account["account"]["type"] == "chatgpt"
                assert account["workspaceRouting"]["backendOrigin"] == server.workspace_origin
                thread = app.request("thread/start", {"model": config["model"], "modelProvider": "openai", "cwd": str(work)})
                assert thread["thread"]["id"]
            finally:
                logs = app.close()
            assert app.proc.returncode == 0, app.proc.returncode
            assert server.inference_requests == 0

            databases = []
            for snapshot in snapshots:
                name = snapshot["database"]
                with closing(sqlite3.connect((home / name).as_uri() + "?mode=ro", uri=True)) as db:
                    assert db.execute("PRAGMA quick_check").fetchone() == ("ok",), name
                    count, succeeded = db.execute("SELECT count(*), sum(success) FROM _sqlx_migrations").fetchone()
                    assert count == succeeded and count >= snapshot["migrations"], name
                databases.append({"database": name, "before_migrations": snapshot["migrations"],
                                  "after_migrations": count, "integrity": "ok"})

            # 沿用独立执行服务探针，入口由根目录元数据提供。
            probe_report = base / "executor.json"
            subprocess.run(
                [sys.executable, "-X", "utf8", str(Path(__file__).with_name("validate_exec_server.py")),
                 "--package", str(app_root), "--output", str(probe_report)],
                check=True, stdout=subprocess.DEVNULL,
            )
            executor = json.loads(probe_report.read_text(encoding="utf-8"))
            assert executor["passed"] and executor["sha256"] == executable_hashes[Path(layout["execServer"]).name]
            assert executor["process_exit_code"] == executor["server_exit_code"] == 0
    finally:
        server.shutdown()
        server.server_close()
        args.output.with_suffix(".stderr.log").write_bytes(logs.encode("utf-8"))

    record = {
        "passed": True,
        "version": version,
        "layout": layout,
        "files_staged": file_count,
        "executable_sha256": executable_hashes,
        "checks": ["--version", "initialize", "config/read", "account/read", "thread/start",
                   "database_backup_and_quick_check", "exec_server_metadata_and_process_start"],
        "database_input": "从升级前备份目录通过 SQLite 只读连接和 backup 制作的独立副本",
        "database_copies": databases,
        "exec_server": {key: executor[key] for key in ("version", "executor_version_matches", "process_start",
                                                      "process_exit_code", "server_exit_code", "sha256")},
        "app_server_exit_code": app.proc.returncode,
        "real_inference_requests": 0,
        "desktop_app_launched": False,
        "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "version": version, "database_copies": len(databases),
                      "files_staged": file_count, "checks": record["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""直接执行最终完整包内的独立命令服务，验证握手、命令输出和正常退出。"""

import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve(strict=True)
    layout = json.loads((package / "codex-package.json").read_text(encoding="utf-8-sig"))
    binary = package / layout["execServer"]
    assert binary.is_file() and layout["version"] == "0.166.0"
    version = subprocess.check_output([str(binary), "--version"], text=True, timeout=30).strip()
    assert version.rsplit(" ", 1)[-1] == layout["version"], version
    cli_version = subprocess.check_output([str(package / layout["entrypoint"]), "--version"], text=True, timeout=30).strip()
    assert cli_version == "codex-cli " + layout["version"]
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with tempfile.TemporaryDirectory(prefix="codex-exec-server-release-") as temporary:
        work = Path(temporary).resolve()
        env = {key: os.environ[key] for key in ("SystemRoot", "SYSTEMROOT", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT") if key in os.environ}
        command = [str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe"), "/D", "/S", "/C", "echo EXEC_SERVER_RELEASE_OK"] if os.name == "nt" else ["/bin/sh", "-c", "printf 'EXEC_SERVER_RELEASE_OK\\n'"]
        with tempfile.TemporaryFile() as log:
            proc = subprocess.Popen([str(binary), "--listen", "stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=log, cwd=work, env=env, bufsize=0)
            rows = queue.Queue()

            def read():
                """将协议行交给有超时限制的主流程。"""
                for line in proc.stdout:
                    rows.put(json.loads(line))
                rows.put({"eof": True})

            threading.Thread(target=read, daemon=True).start()
            try:
                proc.stdin.write((json.dumps({"id": 1, "method": "initialize", "params": {"clientName": "release-exec-server-probe"}}) + "\n").encode())
                proc.stdin.flush()
                initialized = rows.get(timeout=45)
                assert initialized.get("id") == 1 and "error" not in initialized, initialized
                assert initialized["result"]["sessionId"]
                assert initialized["result"]["environmentInfo"]["executorVersion"] == layout["version"]
                messages = [{"method": "initialized", "params": {}}, {"id": 2, "method": "process/start", "params": {
                    "processId": "release-probe", "argv": command, "cwd": work.as_uri(), "env": env,
                    "tty": False, "pipeStdin": False, "arg0": None}}]
                proc.stdin.write("".join(json.dumps(message) + "\n" for message in messages).encode())
                proc.stdin.flush()
                output = bytearray()
                started = False
                exited = False
                while not started or not exited:
                    row = rows.get(timeout=45)
                    assert "error" not in row and not row.get("eof"), row
                    if row.get("id") == 2:
                        started = True
                    if row.get("method") == "process/output":
                        output.extend(base64.b64decode(row["params"]["chunk"]))
                    if row.get("method") == "process/exited":
                        assert row["params"]["exitCode"] == 0, row
                        exited = True
                assert b"EXEC_SERVER_RELEASE_OK" in output, output
                proc.stdin.close()
                assert proc.wait(timeout=45) == 0
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=15)
                proc.stdout.close()
    record = {"passed": True, "version": version, "cli_version": cli_version, "binary": str(binary), "sha256": digest,
              "protocol_initialize": True, "executor_version_matches": True, "process_start": True,
              "output_marker": "EXEC_SERVER_RELEASE_OK", "process_exit_code": 0, "server_exit_code": 0,
              "user_services_modified": False, "real_upstream_requests": 0,
              "checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()

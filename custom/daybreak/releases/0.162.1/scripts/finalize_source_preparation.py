"""同步已迁移源码，核对两平台迁移输入，再启动 schema 和构建准备。"""

import json
from pathlib import Path
import shutil
import subprocess


build = Path("/home/debian/codex-build-0.162.1")
linux = Path("/home/debian/codex-source-0.162.1-linux")
windows = Path("/home/debian/codex-source-0.162.1-windows")
new = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=linux, text=True).splitlines()
if new:
    subprocess.run(["git", "add", "--intent-to-add", "--", *new], cwd=linux, check=True)
paths = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=linux, text=True).splitlines()
assert paths and not subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=linux)
for name in paths:
    destination = windows / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(linux / name, destination)
if new:
    subprocess.run(["git", "add", "--intent-to-add", "--", *new], cwd=windows, check=True)
subprocess.run([
    "python3", str(build / "prepare_windows_migrations.py"), str(windows / "codex-rs/state"),
    str(build / "windows-migrations-sha384.json"), "--database-migrations", str(build / "windows-db-migrations.json"),
    "--report", str(build / "windows-migration-match.json"),
], check=True)
subprocess.run([
    "python3", str(build / "check_linux_migrations.py"), str(linux / "codex-rs/state"),
    str(build / "linux-db-migrations.json"), str(build / "linux-migration-match.json"),
], check=True)
audit = json.loads((build / "port-audit-linux.json").read_text())
audit.update(platform="windows", synchronized_from="linux", source_files_synchronized=len(paths),
             migration_line_endings="CRLF", note="先同步同一组定制改动，再按 Windows 真实迁移校验值准备 SQL。")
(build / "port-audit-windows.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
assert not (build / "prepare-status.json").exists(), "已有准备任务记录，先核对运行状态"
with (build / "prepare_build-launcher.log").open("w") as log:
    process = subprocess.Popen(["python3", str(build / "prepare_build.py")], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print(json.dumps({"synchronized_files": len(paths), "preparation_pid": process.pid, "official_archives_already_verified": (build / "official-packages.json").is_file()}))

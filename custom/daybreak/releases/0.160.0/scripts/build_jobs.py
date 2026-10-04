"""记录构建命令、原始日志和退出状态，不干预 App 或现有服务。"""

import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path("/home/debian/codex-build-0.160.0")
kind = sys.argv[1]
source = Path(f"/home/debian/codex-source-0.160.0-{'windows' if kind == 'windows' else 'linux'}")
env = dict(os.environ)
env["PATH"] = "/home/debian/daybreak-build-tools/bin:/home/debian/.cargo/bin:/home/debian/.local/bin:/home/debian/.codex/overrides/daybreak-compat-0.159.2-linux-x86_64-r1/codex-path:" + env["PATH"]
env.update(CARGO_BUILD_JOBS="10", CARGO_PROFILE_RELEASE_LTO="false", CARGO_PROFILE_RELEASE_CODEGEN_UNITS="16", CARGO_PROFILE_RELEASE_DEBUG="0")
env["CARGO_TARGET_DIR"] = "/home/debian/codex-source-0.156.1/target-win" if kind == "windows" else "/home/debian/codex-source-0.156.1/codex-rs/target"
if kind == "windows":
    env.update(CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER="x86_64-w64-mingw32-gcc", CC_x86_64_pc_windows_gnu="x86_64-w64-mingw32-gcc", CXX_x86_64_pc_windows_gnu="x86_64-w64-mingw32-g++-posix", AR_x86_64_pc_windows_gnu="x86_64-w64-mingw32-ar")
    command = ["cargo", "build", "--release", "--locked", "--target", "x86_64-pc-windows-gnu", "-p", "codex-cli", "--bin", "codex", "-p", "codex-windows-sandbox", "--bin", "codex-command-runner", "--bin", "codex-windows-sandbox-setup", "-p", "codex-windows-sandbox-service", "--bin", "codex-windows-sandbox-service"]
else:
    command = ["cargo", "build", "--release", "--locked", "-p", "codex-cli", "--bin", "codex"]
status_path = root / f"{kind}-build-status.json"
status = {"kind": kind, "status": "running", "pid": os.getpid(), "source": str(source), "command": command, "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
with (root / "logs" / f"{kind}-build.log").open("w") as log:
    proc = subprocess.run(command, cwd=source / "codex-rs", env=env, stdout=log, stderr=subprocess.STDOUT)
status.update(status="passed" if proc.returncode == 0 else "failed", exit_code=proc.returncode, completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
if proc.returncode == 0:
    if kind == "windows":
        destination = root / "windows-compiled"
        destination.mkdir(exist_ok=True)
        for name in ("codex", "codex-command-runner", "codex-windows-sandbox-setup", "codex-windows-sandbox-service"):
            shutil.copy2(Path(env["CARGO_TARGET_DIR"]) / "x86_64-pc-windows-gnu/release" / f"{name}.exe", destination)
    else:
        shutil.copy2(Path(env["CARGO_TARGET_DIR"]) / "release/codex", root / "codex-linux-x86_64")
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(status, ensure_ascii=False))
sys.exit(proc.returncode)

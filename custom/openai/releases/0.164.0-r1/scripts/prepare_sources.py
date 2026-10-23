"""核对迁移输入，生成新版 schema 与锁文件，并启动独立平台构建。"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path("/home/debian/codex-build-0.164.0")
LINUX = Path("/home/debian/codex-source-0.164.0-linux")
WINDOWS = Path("/home/debian/codex-source-0.164.0-windows")
BASE = "6aaac694803004a63c6f393d153c96d22521a6b9"
env = dict(os.environ)
env["PATH"] = "/home/debian/daybreak-build-tools/bin:/home/debian/.cargo/bin:/home/debian/.local/bin:/home/debian/.codex/overrides/openai-custom-0.163.0-linux-x86_64-r2/codex-path:" + env["PATH"]
env.update(CARGO_BUILD_JOBS="10", CARGO_TARGET_DIR="/home/debian/codex-source-0.156.1/codex-rs/target",
           CARGO_PROFILE_RELEASE_LTO="false", CARGO_PROFILE_RELEASE_CODEGEN_UNITS="16", CARGO_PROFILE_RELEASE_DEBUG="0")
for name in ("downloads", "packages", "dist", "logs"):
    (ROOT / name).mkdir(exist_ok=True)
record = {"status": "running", "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "checks": []}
status_path = ROOT / "prepare-status.json"
steps = [
    ("linux-database-manifest", ["python3", str(ROOT / "read_db_migrations.py"), "/home/debian/.codex", str(ROOT / "linux-db-migrations.json")], LINUX),
    ("windows-migrations", ["python3", str(ROOT / "prepare_windows_migrations.py"), str(WINDOWS / "codex-rs/state"),
                            str(ROOT / "windows-migrations-sha384.json"), "--database-migrations", str(ROOT / "windows-db-migrations.json"),
                            "--report", str(ROOT / "windows-migration-match.json")], WINDOWS),
    ("linux-migrations", ["python3", str(ROOT / "check_linux_migrations.py"), str(LINUX / "codex-rs/state"),
                          str(ROOT / "linux-db-migrations.json"), str(ROOT / "linux-migration-match.json")], LINUX),
    ("toolchain", ["rustc", "--version", "--verbose"], LINUX / "codex-rs"),
    ("config-schema", ["just", "write-config-schema"], LINUX / "codex-rs"),
    ("bazel-lock-update", ["just", "bazel-lock-update"], LINUX),
    ("fmt-linux", ["just", "fmt"], LINUX / "codex-rs"),
    ("provider-clippy", ["just", "fix", "-p", "codex-model-provider-info"], LINUX / "codex-rs"),
    ("fmt-final", ["just", "fmt"], LINUX / "codex-rs"),
    ("fmt-check", ["just", "fmt-check"], LINUX / "codex-rs"),
]
for name, command, cwd in steps:
    record["current_check"] = name
    status_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    with (ROOT / "logs" / (name + ".log")).open("w") as stream:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
    record["checks"].append({"name": name, "command": command, "exit_code": result.returncode})
    if result.returncode:
        record["status"] = "failed"
        status_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        raise SystemExit(result.returncode)

schema = json.loads((LINUX / "codex-rs/core/config.schema.json").read_text())
properties = schema["definitions"]["ModelProviderInfo"]["properties"]
assert "experimental_daybreak_app_compat" not in properties and "include_internal_metadata" not in properties
for name in json.loads((ROOT / "source-preparation.json").read_text())["files"]:
    relative = name["path"]
    shutil.copy2(LINUX / relative, WINDOWS / relative)
for relative in ("codex-rs/core/config.schema.json", "codex-rs/Cargo.lock", "MODULE.bazel.lock", "justfile"):
    shutil.copy2(LINUX / relative, WINDOWS / relative)
for source in (LINUX, WINDOWS):
    subprocess.run(["git", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol", "diff", "--check"], cwd=source, check=True)
assert not any(b"\r\n" in p.read_bytes() for p in (LINUX / "codex-rs/state").rglob("*.sql"))
patch = subprocess.check_output(["git", "diff", "--binary", BASE], cwd=LINUX)
(ROOT / "codex-0.164.0-openai-r1.patch").write_bytes(patch)
record.update(status="passed", daybreak_compat_absent=True, internal_metadata_not_configurable=True,
              patch_sha256=hashlib.sha256(patch).hexdigest(), completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
status_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
for platform in ("windows", "linux"):
    with (ROOT / (platform + "-launcher.log")).open("w") as stream:
        subprocess.Popen(["python3", str(ROOT / "build_jobs.py"), platform], stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
with (ROOT / "package-launcher.log").open("w") as stream:
    subprocess.Popen(["python3", str(ROOT / "finish_build_and_validate.py")], stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
print("迁移、schema、锁文件、格式和 provider Clippy 检查通过，已启动两平台构建。", flush=True)

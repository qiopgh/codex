"""部署已经验证的 Linux 完整包，备份数据并原子切换命令链接。"""

from contextlib import closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tomllib


home = Path("/home/debian")
codex_home = home / ".codex"
source = home / "codex-build-0.162.1/dist/codex-0.162.1-openai-daybreak-r1-linux-x86_64"
destination = codex_home / "overrides/daybreak-compat-0.162.1-linux-x86_64-r1"
command = home / ".local/bin/codex"
expected_previous = codex_home / "overrides/daybreak-compat-0.160.0-linux-x86_64-r1/bin/codex"
build_root = home / "codex-build-0.162.1"
expected_hash = next(item["sha256"] for item in json.loads((source / "custom-build.json").read_text())["files"] if item["path"] == "bin/codex")
stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y%m%d-%H%M%S-%f")
backup = codex_home / "backups" / ("cli-before-0.162.1-" + stamp)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


assert command.is_symlink() and command.resolve() == expected_previous
assert not destination.exists(), destination
assert digest(source / "bin/codex") == expected_hash
manifest = json.loads((source / "custom-build.json").read_text())
assert manifest["version"] == "0.162.1"
for item in manifest["files"]:
    assert digest(source / item["path"]) == item["sha256"], item["path"]

config_path = codex_home / "config.toml"
config_hash = digest(config_path)
config = tomllib.loads(config_path.read_text())
catalog_path = Path(config["model_catalog_json"]) if config.get("model_catalog_json") else None
catalog_hash = digest(catalog_path) if catalog_path else None
old_target = os.readlink(command)
old_binary_hash = digest(expected_previous)
running = []
for proc in Path("/proc").glob("[0-9]*"):
    try:
        executable = Path(os.readlink(proc / "exe"))
        if executable.name in ("codex", "codex-code-mode-host"):
            running.append({"pid": int(proc.name), "executable": str(executable)})
    except OSError:
        pass

backup.mkdir(parents=True, mode=0o700)
databases = backup / "databases"
databases.mkdir(mode=0o700)
shutil.copy2(config_path, backup / "config.toml")
(backup / "config.toml").chmod(0o600)
rows = []
for name in ("goals_1.sqlite", "logs_2.sqlite", "memories_1.sqlite", "queue_1.sqlite",
             "state_5.sqlite", "thread_history_1.sqlite"):
    original = codex_home / name
    if not original.is_file():
        continue
    with closing(sqlite3.connect(original.as_uri() + "?mode=ro", uri=True)) as current:
        with closing(sqlite3.connect(databases / name)) as snapshot:
            current.backup(snapshot, pages=4096)
            assert snapshot.execute("PRAGMA quick_check").fetchone() == ("ok",), name
            migrations = snapshot.execute("SELECT count(*) FROM _sqlx_migrations").fetchone()[0]
    (databases / name).chmod(0o600)
    rows.append({"database": name, "migrations": migrations, "integrity": "ok"})
(databases / "backup-manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"stage": "backup_complete", "databases": len(rows), "backup_directory": str(backup)}, ensure_ascii=False), flush=True)

shutil.copytree(source, destination, symlinks=True)
for item in manifest["files"]:
    assert digest(destination / item["path"]) == item["sha256"], item["path"]
for relative in ("bin/codex", "bin/codex-code-mode-host", "codex-path/rg", "codex-resources/bwrap"):
    assert os.access(destination / relative, os.X_OK), relative
version = subprocess.check_output([str(destination / "bin/codex"), "--version"], text=True).strip()
assert version == "codex-cli 0.162.1", version
helper_versions = {}
for relative, option in (("bin/codex-code-mode-host", "--help"), ("codex-path/rg", "--version"),
                         ("codex-resources/bwrap", "--version")):
    output = subprocess.check_output([str(destination / relative), option], text=True)
    helper_versions[relative] = output.splitlines()[0]
print(json.dumps({"stage": "package_verified", "version": version, "files": len(manifest["files"])}, ensure_ascii=False), flush=True)

validation_path = backup / "installed-binary-validation.json"
subprocess.run(["python3", str(build_root / "validate_release.py"), "--binary", str(destination / "bin/codex"),
                "--catalog", "/home/debian/codex-source-0.162.1-linux/codex-rs/models-manager/models.json",
                "--database-source", str(codex_home), "--output", str(validation_path)], check=True)
validation = json.loads(validation_path.read_text())
assert validation["passed"] and validation["sha256"] == expected_hash
assert digest(config_path) == config_hash
assert not catalog_path or digest(catalog_path) == catalog_hash
assert os.readlink(command) == old_target and command.resolve() == expected_previous

record = {
    "status": "ready_to_activate", "version": version, "command": str(command),
    "installed_directory": str(destination), "previous_target": old_target,
    "previous_binary_sha256": old_binary_hash, "binary_sha256": expected_hash,
    "backup_directory": str(backup), "database_backups": rows,
    "package_files_verified": len(manifest["files"]), "helper_commands": helper_versions,
    "config_unchanged": True, "config_sha256": config_hash,
    "catalog_unchanged": True, "catalog_sha256": catalog_hash,
    "daybreak_compat_enabled": config.get("model_providers", {}).get("openai", {}).get("experimental_daybreak_app_compat", False),
    "provider": config.get("model_provider"), "isolated_validation": str(validation_path),
    "isolated_checks": validation["checks"], "mock_http_requests": len(validation["captured"]),
    "running_processes_before_activation": running, "daemon_restarted": False,
    "completed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
}
record_path = backup / "linux-deployment.json"
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")

# 替换符号链接，不影响已经加载旧程序的进程。
temporary_link = command.with_name(".codex-0.162.1-" + stamp + ".tmp")
assert not temporary_link.exists() and not temporary_link.is_symlink()
temporary_link.symlink_to(destination / "bin/codex")
os.replace(temporary_link, command)
try:
    actual_version = subprocess.check_output([str(command), "--version"], text=True).strip()
    assert actual_version == version and command.resolve() == destination / "bin/codex"
except BaseException:
    temporary_link.symlink_to(old_target)
    os.replace(temporary_link, command)
    raise
record["status"] = "deployed"
record["resolved_command"] = str(command.resolve())
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
(build_root / "linux-deployment.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": "deployed", "version": version, "command": str(command),
                  "resolved_command": str(command.resolve()), "backup_directory": str(backup),
                  "verified_package_files": len(manifest["files"]), "isolated_checks": validation["checks"],
                  "mock_http_requests": len(validation["captured"]), "config_unchanged": True,
                  "catalog_unchanged": True, "daemon_restarted": False}, ensure_ascii=False), flush=True)

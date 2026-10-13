"""复用 release 缓存执行选定回归，合并同一大型 crate 的集成测试目标。"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path("/home/debian/codex-build-0.162.1")
source = Path("/home/debian/codex-source-0.162.1-linux")
env = dict(os.environ)
env["PATH"] = "/home/debian/daybreak-build-tools/bin:/home/debian/.cargo/bin:/home/debian/.local/bin:/home/debian/.codex/overrides/daybreak-compat-0.160.0-linux-x86_64-r1/codex-path:" + env["PATH"]
env.update(CARGO_BUILD_JOBS="10", CARGO_PROFILE_RELEASE_LTO="false", CARGO_PROFILE_RELEASE_CODEGEN_UNITS="16", CARGO_PROFILE_RELEASE_DEBUG="0", CARGO_TARGET_DIR="/home/debian/codex-source-0.156.1/codex-rs/target")
status_path = root / "selected-checks-status.json"
record = {"status": "running", "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "checks": []}
changed_files = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=source, text=True).splitlines()
before_hashes = {relative: hashlib.sha256((source / relative).read_bytes()).hexdigest() for relative in changed_files if (source / relative).is_file()}
checks = [
    ("provider-config-tests", ["just", "test", "--release", "--locked", "-p", "codex-model-provider-info", "-p", "codex-config", "-p", "codex-model-provider", "--lib", "-E", "package(codex-model-provider-info) | test(model_provider) | test(capability_overrides_preserve_unspecified_provider_defaults)"], source / "codex-rs"),
    ("provider-catalog-tests", ["just", "test", "--release", "--locked", "-p", "codex-models-manager", "--lib", "-E", "test(authoritative_catalog_preserves_hidden_models_and_matches_exact_ids) | test(authoritative_catalog_failure_invalidates_cache_until_refresh_succeeds)"], source / "codex-rs"),
    ("daybreak-integration-tests", ["just", "test", "--release", "--locked", "-p", "codex-core", "-p", "codex-app-server", "--test", "daybreak_app_compat"], source / "codex-rs"),
    ("database-concurrency-tests", ["just", "test", "--release", "--locked", "-p", "codex-state", "--lib", "-E", "test(writable_pool_reads_do_not_wait_for_an_existing_writer) | test(open_read_write_pool_preserves_existing_settings_under_write_lock) | test(open_read_write_pool_preserves_wal_conversion_lock_error) | test(sqlite::validation)"], source / "codex-rs"),
    ("provider-clippy", ["just", "fix", "-p", "codex-model-provider-info"], source / "codex-rs"),
    ("fmt-check", ["just", "fmt-check"], source / "codex-rs"),
]
for name, command, cwd in checks:
    record["current_check"] = name
    status_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    with (root / "logs" / f"{name}.log").open("w") as log:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
    record["checks"].append({"name": name, "command": command, "exit_code": result.returncode})
    if result.returncode:
        record["status"] = "failed"
        status_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        raise SystemExit(result.returncode)
after_hashes = {relative: hashlib.sha256((source / relative).read_bytes()).hexdigest() for relative in changed_files if (source / relative).is_file()}
record["source_unchanged_by_checks"] = before_hashes == after_hashes
assert record["source_unchanged_by_checks"], "检查修改了源码，必须重新构建交付程序"
record.update(status="passed", completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
status_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
print("选定回归、Clippy 与格式检查通过。")

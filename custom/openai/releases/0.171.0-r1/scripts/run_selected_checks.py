"""合并运行 provider 与配置写入回归，避免拆分重复构建大型 crate。"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path("/home/debian/codex-build-0.171.0")
SOURCE = Path("/home/debian/codex-source-0.171.0-linux")
fixture_patch = ROOT / "release-test-home.patch"
fixture_file = "codex-rs/test-binary-support/lib.rs"
test_home_root = ROOT / "release-test-homes"
test_home_root.mkdir(mode=0o700, exist_ok=True)
env = dict(os.environ)
env["PATH"] = "/home/debian/daybreak-build-tools/bin:/home/debian/.cargo/bin:/home/debian/.local/bin:/home/debian/.codex/overrides/openai-custom-0.167.1-linux-x86_64-r1/codex-path:" + env["PATH"]
env.update(CARGO_BUILD_JOBS="10", CARGO_PROFILE_RELEASE_LTO="false", CARGO_PROFILE_RELEASE_CODEGEN_UNITS="16",
           CARGO_PROFILE_RELEASE_DEBUG="0", CARGO_TARGET_DIR="/home/debian/codex-source-0.156.1/codex-rs/target",
           TEST_TMPDIR=str(test_home_root))
changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=SOURCE, text=True).splitlines()
assert fixture_file not in changed
audited_files = [*changed, fixture_file]
before = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in audited_files}
filterset = (
    "package(codex-model-provider-info) | (package(codex-config) & test(model_provider))"
    " | test(gcp_provider_) | test(capability_overrides_preserve_unspecified_provider_defaults)"
    " | test(openai_provider_override_is_writable) | test(model_provider_list_checks_builtin_configuration_fields)"
    " | (package(codex-state) & (test(sqlite) | test(attached_thread_discovery) | test(migrations::tests::)))"
    " | test(invalid_requirements_do_not_replace_cached_bundle) | test(custom_openai_catalog_preserves_inference_routing)"
)
command = ["just", "test", "--release", "--locked", "-p", "codex-model-provider-info", "-p", "codex-config",
           "-p", "codex-model-provider", "-p", "codex-app-server", "-p", "codex-state", "-p", "codex-cloud-config",
           "-p", "codex-core", "--lib", "--test", "all", "-E", filterset]
record = {"status": "running", "command": command, "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "test_home_root": str(test_home_root), "test_only_patch": fixture_patch.name,
          "test_only_patch_sha256": hashlib.sha256(fixture_patch.read_bytes()).hexdigest()}
path = ROOT / "selected-checks-status.json"
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
# 只在测试期间适配夹具，随后恢复官方的测试支持文件。
subprocess.run(["git", "apply", "--check", str(fixture_patch)], cwd=SOURCE, check=True)
subprocess.run(["git", "apply", str(fixture_patch)], cwd=SOURCE, check=True)
try:
    with (ROOT / "logs/selected-regression.log").open("w") as log:
        result = subprocess.run(command, cwd=SOURCE / "codex-rs", env=env, stdout=log, stderr=subprocess.STDOUT)
finally:
    subprocess.run(["git", "apply", "-R", str(fixture_patch)], cwd=SOURCE, check=True)
after = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in audited_files}
record.update(status="passed" if result.returncode == 0 else "failed", exit_code=result.returncode,
              source_unchanged=before == after, test_only_patch_restored=before[fixture_file] == after[fixture_file],
              completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
summary = re.search(r"(\d+) tests run: (\d+) passed(?:, (\d+) skipped)?", (ROOT / "logs/selected-regression.log").read_text())
if summary:
    record["test_summary"] = dict(run=int(summary[1]), passed=int(summary[2]), skipped=int(summary[3] or 0))
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
raise SystemExit(result.returncode)

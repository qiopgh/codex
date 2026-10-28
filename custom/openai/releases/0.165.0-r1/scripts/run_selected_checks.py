"""合并运行 provider 与配置写入回归，避免拆分重复构建大型 crate。"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path("/home/debian/codex-build-0.165.0")
SOURCE = Path("/home/debian/codex-source-0.165.0-linux")
env = dict(os.environ)
env["PATH"] = "/home/debian/daybreak-build-tools/bin:/home/debian/.cargo/bin:/home/debian/.local/bin:/home/debian/.codex/overrides/openai-custom-0.164.0-linux-x86_64-r1/codex-path:" + env["PATH"]
env.update(CARGO_BUILD_JOBS="10", CARGO_PROFILE_RELEASE_LTO="false", CARGO_PROFILE_RELEASE_CODEGEN_UNITS="16",
           CARGO_PROFILE_RELEASE_DEBUG="0", CARGO_TARGET_DIR="/home/debian/codex-source-0.156.1/codex-rs/target")
changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=SOURCE, text=True).splitlines()
before = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in changed}
command = ["just", "test", "--release", "--locked", "-p", "codex-model-provider-info", "-p", "codex-config",
           "-p", "codex-model-provider", "-p", "codex-app-server", "-p", "codex-state", "--lib", "-E",
           "package(codex-model-provider-info) | (package(codex-config) & test(model_provider)) | test(gcp_provider_accepts_partial_endpoint_and_auth_overrides) | test(capability_overrides_preserve_unspecified_provider_defaults) | test(openai_provider_override_is_writable) | (package(codex-state) & (test(sqlite) | test(attached_thread_discovery)))"]
record = {"status": "running", "command": command, "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
path = ROOT / "selected-checks-status.json"
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
with (ROOT / "logs/selected-regression.log").open("w") as log:
    result = subprocess.run(command, cwd=SOURCE / "codex-rs", env=env, stdout=log, stderr=subprocess.STDOUT)
after = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in changed}
record.update(status="passed" if result.returncode == 0 else "failed", exit_code=result.returncode,
              source_unchanged=before == after, completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
summary = re.search(r"(\d+) tests run: (\d+) passed(?:, (\d+) skipped)?", (ROOT / "logs/selected-regression.log").read_text())
if summary:
    record["test_summary"] = dict(run=int(summary[1]), passed=int(summary[2]), skipped=int(summary[3] or 0))
path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
raise SystemExit(result.returncode)

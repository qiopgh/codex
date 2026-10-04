"""在逐项检查上游变化后迁移补丁，冲突时保留现场供人工合并。"""

import json
from pathlib import Path
import re
import subprocess
import sys


root = Path(sys.argv[1]).resolve(strict=True)
patch_path = Path(sys.argv[2]).resolve(strict=True)
build = Path("/home/debian/codex-build-0.160.0")
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == "a956835d020762cb2b570053af06f643a11c0ecc"
upstream = set(subprocess.check_output(["git", "diff", "--name-only", "rust-v0.159.3", "rust-v0.160.0"], cwd=root, text=True).splitlines())
reviewed = {"codex-rs/config/src/config_toml.rs", "codex-rs/core/src/session/mod.rs",
            "codex-rs/model-provider-info/src/lib.rs", "codex-rs/model-provider/src/provider.rs"}
skip = {"codex-rs/Cargo.lock", "codex-rs/core/config.schema.json"}
chunks = [c for c in re.split(r"(?=^diff --git )", patch_path.read_text(), flags=re.M) if c.strip()]
record = {"base": "rust-v0.160.0", "previous": "rust-v0.159.3", "applied": [], "regenerate": sorted(skip), "reviewed_upstream_files": sorted(reviewed)}
for chunk in chunks:
    relative = chunk.splitlines()[0].split(" b/", 1)[1]
    if relative in skip:
        continue
    assert relative not in upstream or relative in reviewed, f"尚未核对的上游改动：{relative}"
    check = subprocess.run(["git", "apply", "--check", "-"], input=chunk, text=True, cwd=root, capture_output=True)
    command = ["git", "apply", "-"] if check.returncode == 0 else ["git", "apply", "--3way", "-"]
    result = subprocess.run(command, input=chunk, text=True, cwd=root, capture_output=True)
    record["applied"].append({"path": relative, "three_way": check.returncode != 0, "exit_code": result.returncode})
    if result.returncode:
        record["manual_merge_required"] = relative
        (build / "port-audit-linux.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(result.stdout + result.stderr)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        raise SystemExit(result.returncode)
(build / "port-audit-linux.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False, indent=2))

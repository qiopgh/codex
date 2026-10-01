"""核对上游差异后迁移 0.159.2 补丁，重新生成新版锁文件和 schema。"""

import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(sys.argv[1]).resolve(strict=True)
patch = Path(sys.argv[2]).read_text(encoding="utf-8")
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == "01fc69f4026735edfdf6789820549727a4867b11"
upstream = set(subprocess.check_output(["git", "diff", "--name-only", "rust-v0.159.2", "rust-v0.159.3"], cwd=root, text=True).splitlines())
chunks = [c for c in re.split(r"(?=^diff --git )", patch, flags=re.M) if c.strip()]
skip = {"codex-rs/Cargo.lock", "codex-rs/core/config.schema.json"}
applied = []
for chunk in chunks:
    relative = chunk.splitlines()[0].split(" b/", 1)[1]
    if relative in skip:
        continue
    assert relative not in upstream, f"上游修改了补丁文件，必须人工迁移：{relative}"
    subprocess.run(["git", "apply", "--check", "-"], input=chunk, text=True, cwd=root, check=True)
    subprocess.run(["git", "apply", "-"], input=chunk, text=True, cwd=root, check=True)
    applied.append(relative)
print(json.dumps({"source": str(root), "applied_files": applied, "upstream_changed_files": sorted(upstream), "regenerate": sorted(skip)}, ensure_ascii=False, indent=2))

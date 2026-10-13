"""合并已逐项核对的新增字段冲突，同时保留上游字段和定制字段。"""

import json
from pathlib import Path
import re
import subprocess


root = Path("/home/debian/codex-source-0.162.1-linux")
build = Path("/home/debian/codex-build-0.162.1")
files = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=root, text=True).splitlines()
resolved = []
pattern = re.compile(r"^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n", re.M | re.S)
for name in files:
    path = root / name
    text = path.read_text()

    def replace(match):
        upstream, custom = match[1], match[2]
        assert (upstream.strip(), custom.strip()) in {
            ("capabilities: None,", "experimental_daybreak_app_compat: false,"),
            ("mod capabilities;", "mod daybreak_app_compat;"),
        }, (name, upstream, custom)
        resolved.append({"path": name, "upstream": upstream.strip(), "custom": custom.strip()})
        return upstream + custom

    merged = pattern.sub(replace, text)
    assert not re.search(r"^(<<<<<<<|=======|>>>>>>>)", merged, re.M), name
    path.write_text(merged)
    subprocess.run(["git", "add", "--", name], cwd=root, check=True)
audit_path = build / "port-audit-linux.json"
audit = json.loads(audit_path.read_text())
audit["resolved_conflicts"] = resolved
audit["conflicts_remaining"] = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=root, text=True).splitlines()
assert not audit["conflicts_remaining"]
audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
missing = []
for path in (root / "codex-rs").rglob("*.rs"):
    rows = path.read_text().splitlines()
    for index, line in enumerate(rows):
        if re.match(r"\s+include_internal_metadata:\s*(?:true|false),", line):
            if not any("experimental_daybreak_app_compat:" in previous for previous in rows[max(0, index-12):index]):
                missing.append({"path": path.relative_to(root).as_posix(), "line": index+1})
print(json.dumps({"resolved_conflicts": len(resolved), "remaining": audit["conflicts_remaining"], "new_literals_to_review": missing}, ensure_ascii=False))

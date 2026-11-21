"""核对 Linux 源码保持 LF，已应用迁移与源码 SHA-384 完全匹配。"""

import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve(strict=True)
by_version = {}
files = {}
for path in sorted(root.rglob("*.sql")):
    raw = path.read_bytes()
    assert b"\r\n" not in raw, path
    entry = {"path": path.relative_to(root).as_posix(), "sha384": hashlib.sha384(raw).hexdigest()}
    files[entry["path"]] = entry["sha384"]
    by_version.setdefault(int(path.name.split("_", 1)[0]), []).append(entry)
report = {"sql_files": len(files), "line_endings": "LF", "databases": [], "all_applied_matched": True}
for database in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")):
    matches = []
    for row in database["migrations"]:
        candidates = [e for e in by_version.get(row["version"], []) if e["sha384"] == row["sha384"]]
        assert row["success"] and len(candidates) == 1, (database["database"], row)
        matches.append(dict(version=row["version"], **candidates[0]))
    report["databases"].append({"database": database["database"], "matched": matches})
Path(sys.argv[3]).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sql_files": len(files), "databases": len(report["databases"]), "applied_matched": sum(len(d["matched"]) for d in report["databases"])}, ensure_ascii=False))

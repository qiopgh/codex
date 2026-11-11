"""以 codex-rs/state 为根目录准备 CRLF 迁移，并核对本机已应用的 SHA-384。"""

import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("manifest", type=Path)
parser.add_argument("--database-migrations", type=Path)
parser.add_argument("--report", type=Path)
parser.add_argument("--check-only", action="store_true")
args = parser.parse_args()
root = args.root.resolve(strict=True)
assert root.name == "state" and root.parent.name == "codex-rs", root
files = {}
by_version = {}
changed = 0
for path in sorted(root.rglob("*.sql")):
    original = path.read_bytes()
    lf = original.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    relative = path.relative_to(root).as_posix()
    entry = {"path": relative, "lf": hashlib.sha384(lf).hexdigest(), "crlf": hashlib.sha384(crlf).hexdigest()}
    version = path.name.split("_", 1)[0]
    if version.isdigit():
        by_version.setdefault(int(version), []).append(entry)
    files[relative] = entry["crlf"]
    if not args.check_only and original != crlf:
        path.write_bytes(crlf)
        changed += 1
report = {"sql_files": len(files), "converted": changed, "databases": [], "all_applied_matched": True}
if args.database_migrations:
    for database in json.loads(args.database_migrations.read_text(encoding="utf-8")):
        matched = []
        for row in database["migrations"]:
            candidates = by_version.get(row["version"], [])
            actual = [e for e in candidates if e["crlf"] == row["sha384"]]
            assert row["success"] and len(actual) == 1, (database["database"], row, candidates)
            matched.append({"version": row["version"], "path": actual[0]["path"], "sha384": row["sha384"], "line_endings": "CRLF"})
        report["databases"].append({"database": database["database"], "matched": matched})
if args.check_only:
    expected = json.loads(args.manifest.read_text(encoding="utf-8"))
    assert files == expected, "新迁移清单与源码不一致"
    assert all(hashlib.sha384((root / relative).read_bytes()).hexdigest() == checksum for relative, checksum in expected.items()), "源码尚未准备为 CRLF"
else:
    args.manifest.write_text(json.dumps(files, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if args.report:
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sql_files": len(files), "converted": changed, "databases": len(report["databases"]), "applied_matched": sum(len(d["matched"]) for d in report["databases"])}, ensure_ascii=False))

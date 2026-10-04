"""只读导出已应用迁移的校验值，不输出配置或认证内容。"""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

source = Path(sys.argv[1]).resolve(strict=True)
rows = []
for path in sorted(source.glob("*.sqlite")):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='_sqlx_migrations'").fetchone():
            continue
        migrations = [dict(version=v, description=d, success=bool(s), sha384=c.lower())
                      for v, d, s, c in db.execute("SELECT version, description, success, hex(checksum) FROM _sqlx_migrations ORDER BY version")]
    rows.append(dict(database=path.name, migrations=migrations))
Path(sys.argv[2]).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"databases": len(rows), "applied_migrations": sum(len(r["migrations"]) for r in rows)}, ensure_ascii=False))

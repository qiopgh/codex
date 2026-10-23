"""在升级 CLI 前制作本机 SQLite 一致性副本，不改动原数据库。"""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys


source = Path(sys.argv[1]).resolve(strict=True)
destination = Path(sys.argv[2]).resolve()
destination.mkdir(parents=True, exist_ok=False)
rows = []
for name in ("goals_1.sqlite", "logs_2.sqlite", "memories_1.sqlite", "queue_1.sqlite",
             "state_5.sqlite", "thread_history_1.sqlite"):
    path = source / name
    if not path.is_file():
        continue
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(destination / name)) as backup:
            original.backup(backup, pages=4096)
            assert backup.execute("PRAGMA quick_check").fetchone() == ("ok",), name
            count = backup.execute("SELECT count(*) FROM _sqlx_migrations").fetchone()[0]
    rows.append({"database": name, "migrations": count, "integrity": "ok",
                 "size_bytes": (destination / name).stat().st_size})
(destination / "backup-manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"database_backups": len(rows), "integrity": "ok"}, ensure_ascii=False))

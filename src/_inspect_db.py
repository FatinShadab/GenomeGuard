import sqlite3

conn = sqlite3.connect(
    "file:G:/Toufiiq/GenomeGuard/src/.genome/watcher.db?mode=ro", uri=True
)
cur = conn.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("TABLES:", tables)
for t in tables:
    print("---", t)
    print("cols:", cur.execute(f"PRAGMA table_info({t})").fetchall())
    try:
        rows = cur.execute(f"SELECT * FROM {t} LIMIT 5").fetchall()
        print("rows:", rows)
    except Exception as e:
        print("err:", e)

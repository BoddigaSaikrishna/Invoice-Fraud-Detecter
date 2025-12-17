import sqlite3
from pathlib import Path
DB='audit.db'
if not Path(DB).exists():
    print('audit.db not found')
    raise SystemExit(1)
conn=sqlite3.connect(DB)
cur=conn.execute('SELECT id, html_path FROM reports ORDER BY created_at DESC LIMIT 50')
rows=cur.fetchall()
conn.close()
if not rows:
    print('No rows')
else:
    for r in rows:
        print(f"{r[0]}\t{r[1]}")

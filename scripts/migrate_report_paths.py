import sqlite3, os
from pathlib import Path
DB='audit.db'
if not Path(DB).exists():
    print('audit.db not found')
    raise SystemExit(1)
conn=sqlite3.connect(DB)
cur=conn.execute('SELECT id, html_path FROM reports')
rows=cur.fetchall()
updated=0
for r in rows:
    rid, path = r
    if not path:
        continue
    base = os.path.basename(path)
    if base != path:
        conn.execute('UPDATE reports SET html_path=? WHERE id=?', (base, rid))
        updated += 1
conn.commit()
conn.close()
print(f'Updated {updated} rows')

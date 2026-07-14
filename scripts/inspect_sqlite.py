import sqlite3
import sys

path = sys.argv[1]
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for t in ('user', 'submission', 'user_notification'):
    print(f"\n=== {t} ===")
    cur.execute(f'SELECT * FROM "{t}"')
    rows = cur.fetchall()
    for r in rows:
        print(dict(r))
conn.close()

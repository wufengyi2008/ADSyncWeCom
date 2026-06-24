import sqlite3

conn = sqlite3.connect('data/sync.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM operation_logs WHERE detail LIKE "%OU查询%" ORDER BY id DESC LIMIT 5')
rows = cursor.fetchall()

for row in rows:
    print(f'ID: {row[0]}')
    print(f'时间: {row[5]}')
    print(f'详情:')
    print(row[4])
    print('='*80)

conn.close()

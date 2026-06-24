import sqlite3

conn = sqlite3.connect('data/sync.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(operation_logs)")
columns = cursor.fetchall()
print("表结构:")
for col in columns:
    print(f"{col[0]}: {col[1]}")
print()

cursor.execute('SELECT * FROM operation_logs WHERE operation_type IN (?, ?) ORDER BY id DESC LIMIT 30', ('SYNC_DEBUG', 'SYNC_ERROR'))
rows = cursor.fetchall()

for row in rows:
    print(f'ID: {row[0]}')
    print(f'类型: {row[1]}')
    print(f'操作者: {row[2]}')
    print(f'目标: {row[3]}')
    print(f'详情:')
    print(row[4][:500])
    print('='*50)

conn.close()

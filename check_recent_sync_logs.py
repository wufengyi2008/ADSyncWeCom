import sqlite3

conn = sqlite3.connect('data/sync.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM operation_logs WHERE operation_type = "SYNC_DEBUG" AND target = "SELECTED_USERS" ORDER BY id DESC LIMIT 15')
rows = cursor.fetchall()

for row in rows:
    print(f'ID: {row[0]}')
    print(f'时间: {row[5]}')
    print(f'详情:')
    print(row[4])
    print('='*80)

print("\n" + "="*80)
print("PowerShell命令日志:")
print("="*80)

cursor.execute('SELECT * FROM operation_logs WHERE target = "PowerShell" ORDER BY id DESC LIMIT 10')
rows = cursor.fetchall()

for row in rows:
    print(f'ID: {row[0]}')
    print(f'时间: {row[5]}')
    print(f'详情:')
    print(row[4])
    print('='*80)

conn.close()
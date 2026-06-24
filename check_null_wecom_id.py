import sqlite3

conn = sqlite3.connect('data/sync.db')
cursor = conn.cursor()

cursor.execute('SELECT id, name, wecom_id FROM departments WHERE wecom_id IS NULL OR wecom_id = ""')
rows = cursor.fetchall()

if rows:
    print(f'发现 {len(rows)} 个部门的 wecom_id 为空:')
    for row in rows:
        print(f'  ID: {row[0]}, 名称: {row[1]}, wecom_id: {row[2]}')
else:
    print('所有部门的 wecom_id 都不为空')

conn.close()

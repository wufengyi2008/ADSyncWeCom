import sqlite3

conn = sqlite3.connect('data/sync.db')
cursor = conn.cursor()

# 查看所有部门信息
cursor.execute('SELECT id, name, wecom_id, sync_status FROM departments')
rows = cursor.fetchall()

print("部门列表:")
for row in rows:
    print(f"ID: {row[0]}, 名称: {row[1]}, wecom_id: {row[2]}, 同步状态: {row[3]}")

conn.close()
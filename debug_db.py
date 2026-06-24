import sqlite3

# 连接数据库
conn = sqlite3.connect('adsync_wecom.db')
cursor = conn.cursor()

# 获取表结构
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()

print('=== users表字段顺序 ===')
for i, col in enumerate(columns):
    print(f'  {i}: {col[1]} - {col[2]}')

# 检查数据库中是否存在字段顺序错误
print('\n=== 验证数据 ===')
cursor.execute('SELECT wecom_id, name, position, sync_status FROM users WHERE wecom_id = "WuBaoliang"')
row = cursor.fetchone()
if row:
    print(f'用户 WuBaoliang:')
    print(f'  wecom_id: {row[0]}')
    print(f'  name: {row[1]}')
    print(f'  position (第6个字段): {repr(row[2])}')
    print(f'  sync_status (第9个字段): {row[3]}')

# 检查字段索引
print('\n=== 字段索引 ===')
col_names = [col[1] for col in columns]
for name in ['position', 'sync_status', 'wecom_id', 'name']:
    if name in col_names:
        print(f'  {name}: 索引 {col_names.index(name)}')

conn.close()

from database import Database
db = Database()

# 查看users表结构
cursor = db.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print('=== users表结构 ===')
for col in columns:
    print(f'  {col[1]} - {col[2]}')

# 查看一条原始数据
print('\n=== 原始数据示例 ===')
cursor = db.execute('SELECT * FROM users LIMIT 1')
row = cursor.fetchone()
if row:
    print(f'Row keys: {list(row.keys())}')
    print(f'Raw values: {dict(row)}')

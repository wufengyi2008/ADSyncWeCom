import sqlite3
import os
import sys
import hashlib

def get_app_dir():
    return os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(get_app_dir(), 'data', 'sync.db')
DB_KEY = hashlib.sha256(b'WeCom_AD_Sync_Secure_Key_2024').digest().hex()[:32]

# 尝试连接加密数据库
try:
    from pysqlcipher3 import dbapi2 as sqlite
    conn = sqlite.connect(DB_FILE, timeout=30)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA key='{DB_KEY}'")
    cursor.execute("PRAGMA cipher_compatibility = 3")
    conn.row_factory = sqlite3.Row
    
    # 获取表结构
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    
    print('=== users表字段顺序 ===')
    for i, col in enumerate(columns):
        print(f'  {i}: {col[1]} - {col[2]}')
    
    # 查询人事行政部用户
    cursor.execute('SELECT wecom_id, name, position, sync_status FROM users WHERE wecom_id = "WuBaoliang"')
    row = cursor.fetchone()
    if row:
        print(f'\n=== 用户 WuBaoliang 数据 ===')
        print(f'  wecom_id: {row["wecom_id"]}')
        print(f'  name: {row["name"]}')
        print(f'  position: {repr(row["position"])}')
        print(f'  sync_status: {row["sync_status"]}')
    
    # 查询sync_status字段的所有不同值
    cursor.execute('SELECT DISTINCT sync_status FROM users LIMIT 10')
    print(f'\n=== sync_status字段的不同值 ===')
    for row in cursor.fetchall():
        print(f'  {repr(row["sync_status"])}')
    
    conn.close()
    
except Exception as e:
    print(f'Error: {e}')

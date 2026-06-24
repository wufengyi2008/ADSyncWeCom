from database import Database
db = Database()

# 查询人事行政部
dept = db.fetch_one('SELECT * FROM departments WHERE name LIKE "%人事%"')
print('=== 部门信息 ===')
if dept:
    print(f'部门ID: {dept["wecom_id"]}')
    print(f'部门名称: {dept["name"]}')
    
    # 查询该部门下的用户
    users = db.fetch_all('''
        SELECT u.* FROM users u
        JOIN user_department ud ON u.wecom_id = ud.user_wecom_id
        WHERE ud.dept_wecom_id = ?
    ''', (dept['wecom_id'],))

    print(f'\n=== 该部门用户 ({len(users)}人) ===')
    for u in users:
        print(f'  姓名: {u["name"]}, 账号: {u["account"]}, 职位: [{repr(u["position"])}], 状态: {u["sync_status"]}')

# 查看同步日志
print('\n=== 最近同步日志 ===')
logs = db.fetch_all('SELECT * FROM sync_logs ORDER BY id DESC LIMIT 10')
for log in logs:
    print(f'  {log["start_time"]} - {log["sync_type"]}: {log["status"]} - {log["message"]}')

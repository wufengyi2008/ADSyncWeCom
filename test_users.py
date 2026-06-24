from wecom_api import WeComAPI

# 测试获取所有用户
api = WeComAPI()

try:
    users = api.get_all_users()
    print(f'获取到 {len(users)} 个用户')
    
    if users:
        user = users[0]
        print(f'\n第一个用户数据结构:')
        for key, value in user.items():
            print(f'  {key}: {repr(value)} - 类型: {type(value).__name__}')
        
        print(f'\nposition字段值: {repr(user.get("position"))}')
        print(f'department字段值: {repr(user.get("department"))}')
        
except Exception as e:
    print(f'Error: {e}')

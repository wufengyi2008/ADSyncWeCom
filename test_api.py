from wecom_api import WeComAPI

# 测试获取用户详情
api = WeComAPI()

try:
    # 获取部门列表
    depts = api.get_department_list()
    print('部门列表:')
    for d in depts[:3]:
        print(f'  {d}')
    
    # 获取用户详情
    if depts:
        dept_id = depts[0]['id']
        users = api.get_department_users(dept_id)
        if users:
            user_id = users[0]['userid']
            detail = api.get_user_detail(user_id)
            print(f'\n用户详情:')
            print(f'  {detail}')
            print(f'\nposition字段类型: {type(detail.get("position"))}')
            print(f'position字段值: {detail.get("position")}')
            
except Exception as e:
    print(f'Error: {e}')

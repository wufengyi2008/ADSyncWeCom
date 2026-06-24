import requests
import time
import json
from config_manager import ConfigManager

class WeComAPI:
    def __init__(self):
        self.config = ConfigManager()
        self.base_url = 'https://qyapi.weixin.qq.com/cgi-bin'
        self.access_token = None
        self.token_expire_time = 0
    
    def _get_access_token(self):
        now = time.time()
        if self.access_token and now < self.token_expire_time:
            return self.access_token
        
        corp_id = self.config.get('corp_id')
        corp_secret = self.config.get_encrypted('corp_secret')
        
        if not corp_id or not corp_secret:
            raise Exception('企业微信配置未完成')
        
        url = f'{self.base_url}/gettoken?corpid={corp_id}&corpsecret={corp_secret}'
        
        for retry in range(3):
            try:
                response = requests.get(url, timeout=30)
                data = response.json()
                
                if data.get('errcode') == 0:
                    self.access_token = data['access_token']
                    self.token_expire_time = now + (data.get('expires_in', 7200) - 60)
                    return self.access_token
                else:
                    raise Exception(f'获取access_token失败: {data.get("errmsg", "未知错误")}')
            except Exception as e:
                if retry < 2:
                    time.sleep(2 ** retry)
                    continue
                raise e
    
    def _request(self, path, method='GET', params=None, data=None):
        token = self._get_access_token()
        url = f'{self.base_url}{path}?access_token={token}'
        
        if params:
            url += '&' + '&'.join(f'{k}={v}' for k, v in params.items())
        
        for retry in range(3):
            try:
                if method == 'GET':
                    response = requests.get(url, timeout=30)
                else:
                    response = requests.post(url, json=data, timeout=30)
                
                result = response.json()
                
                if result.get('errcode') == 0:
                    return result
                elif result.get('errcode') == 42001:
                    self.access_token = None
                    token = self._get_access_token()
                    url = f'{self.base_url}{path}?access_token={token}'
                    continue
                else:
                    raise Exception(f'API调用失败 [{result.get("errcode")}]: {result.get("errmsg", "未知错误")}')
            except Exception as e:
                if retry < 2:
                    time.sleep(2 ** retry)
                    continue
                raise e
    
    def get_department_list(self):
        result = self._request('/department/list')
        return result.get('department', [])
    
    def get_department_info(self, department_id):
        params = {'id': department_id}
        result = self._request('/department/get', params=params)
        return result if result.get('errcode') == 0 else None
    
    def get_department_users(self, department_id, fetch_child=True):
        params = {
            'department_id': department_id,
            'fetch_child': '1' if fetch_child else '0'
        }
        result = self._request('/user/simplelist', params=params)
        return result.get('userlist', [])
    
    def get_user_detail(self, user_id):
        params = {'userid': user_id}
        result = self._request('/user/get', params=params)
        return result
    
    def get_all_users(self):
        departments = self.get_department_list()
        all_users = []
        seen_users = set()
        
        for dept in departments:
            dept_users = self.get_department_users(dept['id'])
            for user in dept_users:
                if user['userid'] not in seen_users:
                    seen_users.add(user['userid'])
                    detail = self.get_user_detail(user['userid'])
                    all_users.append(detail)
        
        return all_users
    
    def get_user_department_relation(self):
        departments = self.get_department_list()
        user_depts = []
        
        for dept in departments:
            users = self.get_department_users(dept['id'], fetch_child=False)
            for user in users:
                user_depts.append({
                    'user_id': user['userid'],
                    'dept_id': str(dept['id'])
                })
        
        return user_depts

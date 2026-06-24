# -*- coding: utf-8 -*-
"""
wecom_api.py - 企业微信API封装模块，提供部门和用户数据接口

作者：怡悦2011
日期：2026
"""
import logging
import time
import requests
from typing import Dict, List
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries=3, delay=1):
    """
    重试装饰器 - 在函数失败时自动重试
    
    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} 重试延迟 {delay} 秒 ({attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} 重试{max_retries}次后仍然失败")
            raise last_exception
        return wrapper
    return decorator


class WeComAPI:
    """企业微信API客户端"""
    
    def __init__(self, corpid: str, corpsecret: str):
        """
        初始化企业微信API客户端
        
        Args:
            corpid: 企业ID
            corpsecret: 应用密钥
        """
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.access_token = None
        self.token_expires_at = 0
        self._get_access_token()  # 初始化时获取access_token
    
    def _get_access_token(self) -> str:
        """
        获取或刷新access_token
        
        Returns:
            str: access_token
        """
        # 如果token有效，直接返回
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        @retry_on_failure(max_retries=3, delay=2)
        def fetch_token():
            url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corpid}&corpsecret={self.corpsecret}"
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                logger.info("成功获取access_token")
                return result['access_token'], result.get('expires_in', 7200)
            else:
                error_msg = f"获取access_token失败: {result.get('errmsg')}"
                logger.error(error_msg)
                raise Exception(error_msg)

        self.access_token, expires_in = fetch_token()
        self.token_expires_at = time.time() + expires_in - 300  # 提前5分钟过期
        logger.info(f"access_token将于 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.token_expires_at))} 过期")
        return self.access_token

    def _make_request(self, method: str, url: str, max_retries: int = 3) -> Dict:
        """
        发起API请求，自动处理token过期
        
        Args:
            method: 请求方法（GET/POST）
            url: 请求URL
            max_retries: 最大重试次数
            
        Returns:
            Dict: API响应结果
        """
        for attempt in range(max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, timeout=10)
                else:
                    response = requests.post(url, timeout=10)
                
                result = response.json()
                
                # 40014: access_token无效
                # 42001: access_token已过期
                if result.get('errcode') in (40014, 42001):
                    logger.warning("Access token过期，重新获取...")
                    self.access_token = None
                    self._get_access_token()
                    # 如果URL中已有access_token参数，则替换
                    if 'access_token=' in url:
                        url = url.split('access_token=')[0] + f'access_token={self.access_token}'
                    else:
                        url = url + f'&access_token={self.access_token}'
                    continue
                
                return result
                
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"请求失败 ({attempt + 1}/{max_retries}): {e}")
                    time.sleep(1)
                else:
                    logger.error(f"请求失败: {e}")
                    raise

    def get_department_list(self) -> List[Dict]:
        """
        获取企业微信部门列表
        
        Returns:
            List[Dict]: 部门列表
        """
        url = f"https://qyapi.weixin.qq.com/cgi-bin/department/list?access_token={self.access_token}"
        result = self._make_request('GET', url)
        
        if result.get('errcode') == 0:
            departments = result["department"]
            logger.info(f"获取到 {len(departments)} 个部门")
            return departments
        else:
            error_msg = f"获取部门列表失败: {result.get('errmsg')}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_department_users(self, department_id: int) -> List[Dict]:
        """
        获取指定部门的用户列表
        
        Args:
            department_id: 部门ID
            
        Returns:
            List[Dict]: 用户列表
        """
        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/list?access_token={self.access_token}&department_id={department_id}&fetch_child=0"
        result = self._make_request('GET', url)
        
        if result.get('errcode') == 0:
            users = result["userlist"]
            logger.debug(f"部门 {department_id} 获取到 {len(users)} 个用户")
            return users
        else:
            error_msg = f"获取部门用户失败: {result.get('errmsg')}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_user_detail(self, userid: str) -> Dict:
        """
        获取用户详细信息
        
        Args:
            userid: 用户ID
            
        Returns:
            Dict: 用户详细信息
        """
        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={self.access_token}&userid={userid}"
        result = self._make_request('GET', url)
        
        if result.get('errcode') == 0:
            return result
        else:
            error_msg = f"获取用户信息失败: {userid}, {result.get('errmsg')}"
            logger.error(error_msg)
            return {}

    def get_all_users(self) -> List[Dict]:
        """
        获取所有用户列表（去重）
        
        Returns:
            List[Dict]: 去重后的用户列表
        """
        all_users = []
        try:
            # 1. 获取部门列表
            departments = self.get_department_list()
            logger.info(f"获取到 {len(departments)} 个部门")
            
            # 2. 遍历每个部门获取用户
            for dept in departments:
                users = self.get_department_users(dept['id'])
                all_users.extend(users)
            
            # 3. 去重（同一个用户可能属于多个部门）
            seen_userids = set()
            unique_users = []
            for user in all_users:
                if user['userid'] not in seen_userids:
                    seen_userids.add(user['userid'])
                    unique_users.append(user)
            
            logger.info(f"获取到 {len(unique_users)} 个用户")
            return unique_users
            
        except Exception as e:
            logger.error(f"获取所有用户失败: {str(e)}")
            return []

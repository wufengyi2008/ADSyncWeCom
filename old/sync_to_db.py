# -*- coding: utf-8 -*-
"""
sync_to_db.py - 企业微信数据同步模块，同步部门和用户到本地数据库

作者：怡悦2011
日期：2026
"""
import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional

from wecom_api import WeComAPI
from database import Database

logger = logging.getLogger(__name__)


def sync_wecom_to_db(wecom: WeComAPI, db: Database, 
                     progress_callback: Optional[Callable] = None, 
                     domain: Optional[str] = None) -> bool:
    """
    同步企业微信数据到本地数据库（以企业微信数据为准）
    
    Args:
        wecom: 企业微信API客户端实例
        db: 数据库实例
        progress_callback: 进度回调函数，接收字符串参数
        domain: 邮件域名，用于生成用户邮箱
        
    Returns:
        bool: 同步是否成功
        
    同步的数据：
        - 部门信息（名称、层级关系、完整路径）
        - 用户信息（工号、姓名、职位、邮箱等）
        - 用户与部门的隶属关系
        
    同步策略：
        1. 更新：本地数据与企业微信不同时，以企业微信为准更新
        2. 增加：企业微信有但本地没有的数据，添加到本地
        3. 删除：企业微信没有但本地有的数据，从本地删除
    """
    logger.info("开始同步企业微信数据到数据库...")
    
    def progress(msg: str):
        """内部进度回调，输出到日志和UI"""
        # 同时记录到数据库
        db.insert_operation_log('INFO', 'SYNC_DB', msg)
        if progress_callback:
            progress_callback(msg)
        logger.info(msg)

    try:
        # ==================== 第1步：同步部门数据 ====================
        progress("正在获取部门列表...")
        departments = wecom.get_department_list()
        progress(f"获取到 {len(departments)} 个部门")

        # 构建部门树结构用于计算路径
        dept_tree = {}
        wecom_dept_ids = set()  # 企业微信部门ID集合，用于后续比对
        for dept in departments:
            dept_id = dept['id']
            wecom_dept_ids.add(dept_id)
            dept_tree[dept_id] = {
                'name': dept['name'],           # 部门名称
                'parentid': dept['parentid'],   # 父部门ID
                'path': []                       # 完整路径（待计算）
            }

        # 计算每个部门的完整路径
        # 例如：广东省高峰科技有限公司\生产制造中心\SMT部
        for dept_id in dept_tree:
            path = []
            current_id = dept_id
            while current_id != 0:  # 0表示根部门
                if current_id not in dept_tree:
                    break
                # 将部门名称插入到路径开头（逆序构建）
                path.insert(0, dept_tree[current_id]['name'])
                current_id = dept_tree[current_id]['parentid']
            dept_tree[dept_id]['path'] = path

        # 保存部门到数据库
        for dept_id, dept_info in dept_tree.items():
            # 将路径列表转为反斜杠分隔的字符串
            path_str = '\\'.join(dept_info['path']) if dept_info['path'] else dept_info['name']
            db.insert_department(dept_id, dept_info['name'], dept_info['parentid'], path_str)

        # 删除本地有但企业微信没有的部门
        local_departments = db.get_all_departments()
        deleted_dept_count = 0
        for local_dept in local_departments:
            if local_dept['wecom_dept_id'] not in wecom_dept_ids:
                if db.delete_department_by_wecom_id(local_dept['wecom_dept_id']):
                    deleted_dept_count += 1
        
        if deleted_dept_count > 0:
            progress(f"删除了 {deleted_dept_count} 个本地多余部门")

        progress("部门数据同步完成")

        # ==================== 第2步：同步用户数据 ====================
        progress("正在获取用户列表...")
        all_users = wecom.get_all_users()
        progress(f"获取到 {len(all_users)} 个用户")

        # 收集企业微信用户ID集合，用于后续比对
        wecom_user_ids = set()
        for user in all_users:
            wecom_user_ids.add(user['userid'])

        total_users = len(all_users)
        for i, user in enumerate(all_users):
            # 提取用户基本信息
            userid = user['userid']                    # 企业微信用户ID
            name = user.get('name', '')                # 用户姓名
            
            # 每50个用户报告一次进度
            if i % 50 == 0:
                progress(f"正在同步用户 {i+1}/{total_users}...")
            
            # 生成邮箱地址
            email = f"{userid}@{domain}" if domain else ''
            mobile = user.get('mobile', '')            # 手机号
            alias = user.get('alias', '')              # 工号/别名
            position = user.get('position', '')        # 职位
            
            # 调试日志
            logger.debug(f"用户 {name}({userid}) - 工号: {alias}, 邮箱: {email}, 职位: {position}")
            
            # 获取所属部门ID列表
            dept_ids = user.get('department', [])
            dept_ids_str = ','.join(str(d) for d in dept_ids) if dept_ids else ''

            # 插入或更新用户
            db_user_id = db.insert_user(
                userid, name, email, mobile, 
                dept_ids_str, alias, position
            )
            
            # 如果插入失败（返回0），尝试查找已存在的用户
            if db_user_id == 0:
                existing_user = db.get_user_by_wecom_id(userid)
                if existing_user:
                    db_user_id = existing_user['id']

            # 处理用户与部门的隶属关系
            if db_user_id > 0:
                # 先清除旧的关系
                db.clear_user_department(db_user_id)
                # 添加新的关系
                for dept_id in dept_ids:
                    # 根据企业微信部门ID查找数据库部门ID
                    db_dept = db.get_department_by_wecom_id(dept_id)
                    if db_dept:
                        db.insert_user_department(db_user_id, db_dept['id'])

        # 删除本地有但企业微信没有的用户
        local_users = db.get_all_users()
        deleted_user_count = 0
        for local_user in local_users:
            if local_user['wecom_userid'] not in wecom_user_ids:
                if db.delete_user_by_wecom_id(local_user['wecom_userid']):
                    deleted_user_count += 1
        
        if deleted_user_count > 0:
            progress(f"删除了 {deleted_user_count} 个本地多余用户")

        logger.info("用户数据同步完成")
        
        # 记录同步日志
        db.insert_sync_log(
            'SYNC',                                    # 同步类型
            'WECOM',                                   # 目标类型
            0,                                         # 目标ID
            '企业微信同步',                            # 目标名称
            'SUCCESS',                                 # 状态：成功
            f'同步完成，部门:{len(departments)}个(删除{deleted_dept_count}个), 用户:{total_users}人(删除{deleted_user_count}人)'
        )
        
        return True
        
    except Exception as e:
        error_msg = f"同步企业微信数据到数据库失败: {str(e)}"
        logger.error(error_msg)
        db.insert_operation_log('ERROR', 'SYNC_DB', error_msg)
        db.insert_sync_log(
            'SYNC',
            'WECOM',
            0,
            '企业微信同步',
            'FAILED',
            str(e)
        )
        return False


def get_department_users(db: Database, dept_id: int) -> List[Dict]:
    """
    获取指定部门的用户列表
    
    Args:
        db: 数据库实例
        dept_id: 数据库部门ID
        
    Returns:
        List[Dict]: 用户列表
    """
    return db.get_users_by_department(dept_id)


def get_department_tree(db: Database) -> List[Dict]:
    """
    获取部门树形结构
    
    用于在GUI中展示树形部门结构
    
    Args:
        db: 数据库实例
        
    Returns:
        List[Dict]: 树形部门结构列表（根部门列表）
        
    返回格式示例：
        [
            {
                'id': 1,
                'wecom_dept_id': 100,
                'name': '广东省高峰科技有限公司',
                'path': '广东省高峰科技有限公司',
                'sync_status': 1,
                'children': [
                    {
                        'id': 2,
                        'wecom_dept_id': 101,
                        'name': '生产制造中心',
                        'path': '广东省高峰科技有限公司\\生产制造中心',
                        'sync_status': 1,
                        'children': [...]
                    }
                ]
            }
        ]
    """
    # 获取所有部门
    departments = db.get_all_departments()
    
    # 构建ID到部门的映射
    dept_map = {dept['id']: dept for dept in departments}
    
    # 找出根部门（parent_id = 0）
    tree = []
    for dept in departments:
        if dept['parent_id'] == 0:
            tree.append(build_tree(dept, dept_map))
    
    return tree


def build_tree(dept: Dict, dept_map: Dict) -> Dict:
    """
    递归构建部门树
    
    Args:
        dept: 当前部门
        dept_map: 所有部门的映射表
        
    Returns:
        Dict: 包含children的部门节点
    """
    children = []
    
    # 查找子部门
    for child_id, child_dept in dept_map.items():
        if child_dept['parent_id'] == dept['wecom_dept_id']:
            # 递归构建子树
            children.append(build_tree(child_dept, dept_map))
    
    return {
        'id': dept['id'],                      # 数据库ID
        'wecom_dept_id': dept['wecom_dept_id'], # 企业微信部门ID
        'name': dept['name'],                   # 部门名称
        'path': dept['path'],                   # 完整路径
        'sync_status': dept['sync_status'],     # 同步状态
        'children': children                    # 子部门列表
    }

# -*- coding: utf-8 -*-
"""
db_user.py - 用户数据操作模块，提供用户CRUD和批量操作

作者：怡悦2011
日期：2026
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UserDB:
    """用户数据库操作类"""

    def __init__(self, db_base):
        self.db = db_base

    def insert_user(self, wecom_userid: str, name: str, email: str = None, 
                   mobile: str = None, department_ids: str = None, 
                   alias: str = None, position: str = None) -> int:
        """
        插入或更新用户
        
        Args:
            wecom_userid: 企业微信用户ID
            name: 用户姓名
            email: 邮箱地址
            mobile: 手机号码
            department_ids: 部门ID列表（逗号分隔）
            alias: 别名
            position: 职位
            
        Returns:
            用户ID（成功）或0（失败）
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            # 检查是否已存在
            cursor.execute(
                'SELECT id, name, email, mobile, department_ids, alias, position FROM users WHERE wecom_userid = ?',
                (wecom_userid,)
            )
            existing = cursor.fetchone()
            
            if existing:
                existing_id, existing_name, existing_email, existing_mobile, \
                existing_dept_ids, existing_alias, existing_position = existing
                
                # 如果数据没有变化，跳过更新
                if (existing_name == name and 
                    existing_email == email and 
                    existing_mobile == mobile and 
                    existing_dept_ids == department_ids and 
                    existing_alias == alias and 
                    existing_position == position):
                    logger.debug(f"用户数据无变化，跳过更新: {name} (ID: {wecom_userid})")
                    return existing_id
            
            # 插入或更新
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (wecom_userid, name, email, mobile, department_ids, alias, position, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (wecom_userid, name, email, mobile, department_ids, alias, position))
            conn.commit()
            logger.debug(f"用户已保存: {name} (ID: {wecom_userid})")
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"插入用户失败: {e}")
            return 0

    def batch_insert_users(self, users: List[Dict]) -> int:
        """
        批量插入用户
        
        Args:
            users: 用户列表，每个用户包含 wecom_userid, name, email, mobile, department_ids, alias, position
            
        Returns:
            成功插入/更新的用户数量
        """
        if not users:
            return 0
            
        conn = self.db._connect()
        cursor = conn.cursor()
        count = 0
        
        try:
            for user in users:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO users 
                        (wecom_userid, name, email, mobile, department_ids, alias, position, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        user.get('wecom_userid'),
                        user.get('name'),
                        user.get('email'),
                        user.get('mobile'),
                        user.get('department_ids'),
                        user.get('alias'),
                        user.get('position')
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"批量插入用户失败: {user.get('name')} - {e}")
            
            conn.commit()
            logger.info(f"批量插入完成，成功 {count} 条")
            return count
            
        except Exception as e:
            logger.error(f"批量插入失败: {e}")
            return 0

    def get_all_users(self) -> List[Dict]:
        """获取所有用户列表"""
        try:
            return self.db.fetch_all('SELECT * FROM users ORDER BY name')
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return []

    def get_users_by_department(self, dept_id: int) -> List[Dict]:
        """
        获取指定部门的用户
        
        Args:
            dept_id: 部门ID
            
        Returns:
            用户列表
        """
        try:
            return self.db.fetch_all(
                'SELECT * FROM users WHERE id IN (SELECT user_id FROM user_department WHERE dept_id = ?)',
                (dept_id,)
            )
        except Exception as e:
            logger.error(f"获取部门用户失败: {e}")
            return []

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户"""
        try:
            return self.db.fetch_one('SELECT * FROM users WHERE id = ?', (user_id,))
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def get_user_by_wecom_id(self, wecom_userid: str) -> Optional[Dict]:
        """根据企业微信ID获取用户"""
        try:
            return self.db.fetch_one('SELECT * FROM users WHERE wecom_userid = ?', (wecom_userid,))
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def update_user_sync_status(self, user_id: int, status: int, sync_time: str = None):
        """
        更新用户同步状态
        
        Args:
            user_id: 用户ID
            status: 同步状态 (0:未同步, 1:已同步, 2:需同步, 3:已禁用)
            sync_time: 同步时间
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            if sync_time:
                cursor.execute(
                    'UPDATE users SET sync_status = ?, synced_at = ? WHERE id = ?',
                    (status, sync_time, user_id)
                )
            else:
                cursor.execute(
                    'UPDATE users SET sync_status = ? WHERE id = ?',
                    (status, user_id)
                )
            conn.commit()
        except Exception as e:
            logger.error(f"更新用户同步状态失败: {e}")

    def batch_update_user_sync_status(self, user_ids: List[int], status: int, sync_time: str = None):
        """
        批量更新用户同步状态
        
        Args:
            user_ids: 用户ID列表
            status: 同步状态
            sync_time: 同步时间
        """
        if not user_ids:
            return
            
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            placeholders = ','.join('?' * len(user_ids))
            if sync_time:
                cursor.execute(
                    f'UPDATE users SET sync_status = ?, synced_at = ? WHERE id IN ({placeholders})',
                    (status, sync_time) + tuple(user_ids)
                )
            else:
                cursor.execute(
                    f'UPDATE users SET sync_status = ? WHERE id IN ({placeholders})',
                    (status,) + tuple(user_ids)
                )
            conn.commit()
            logger.info(f"批量更新 {len(user_ids)} 个用户状态为 {status}")
        except Exception as e:
            logger.error(f"批量更新用户状态失败: {e}")

    def update_user_ad_exists(self, user_id: int, exists: int):
        """
        更新用户AD存在状态
        
        Args:
            user_id: 用户ID
            exists: 是否存在于AD中 (1:存在, 0:不存在)
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET ad_exists = ? WHERE id = ?', (exists, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"更新AD存在状态失败: {e}")

    def delete_user_by_wecom_id(self, wecom_userid: str) -> bool:
        """
        根据企业微信ID删除用户
        
        Args:
            wecom_userid: 企业微信用户ID
            
        Returns:
            是否删除成功
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM users WHERE wecom_userid = ?', (wecom_userid,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"删除用户失败: {e}")
            return False

    def delete_users_by_wecom_ids(self, wecom_userids: List[str]) -> int:
        """
        批量删除用户
        
        Args:
            wecom_userids: 企业微信用户ID列表
            
        Returns:
            删除的用户数量
        """
        if not wecom_userids:
            return 0
            
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            placeholders = ','.join('?' * len(wecom_userids))
            cursor.execute(f'DELETE FROM users WHERE wecom_userid IN ({placeholders})', 
                          tuple(wecom_userids))
            conn.commit()
            deleted = cursor.rowcount
            logger.info(f"批量删除完成，删除 {deleted} 条")
            return deleted
        except Exception as e:
            logger.error(f"批量删除失败: {e}")
            return 0

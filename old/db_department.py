# -*- coding: utf-8 -*-
"""
db_department.py - 部门数据操作模块，提供部门CRUD和层级查询

作者：怡悦2011
日期：2026
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DepartmentDB:
    """
    部门数据库操作类
    
    Attributes:
        db: 数据库基础实例
    """
    
    def __init__(self, db_base):
        """
        初始化部门操作类
        
        Args:
            db_base: DatabaseBase实例
        """
        self.db = db_base

    # ==================== 插入/更新 ====================

    def insert_department(self, dept_id: int, name: str, parent_id: int, path: str) -> int:
        """
        插入或更新部门（仅在数据变化时更新）
        
        Args:
            dept_id: 企业微信部门ID
            name: 部门名称
            parent_id: 父部门ID
            path: 部门完整路径
            
        Returns:
            int: 插入/更新的记录ID，失败返回0
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            # 先检查是否已存在相同数据的部门
            cursor.execute('''
                SELECT id, name, parent_id, path FROM departments WHERE wecom_dept_id = ?
            ''', (dept_id,))
            existing = cursor.fetchone()
            
            if existing:
                # 检查数据是否有变化
                existing_name = existing[1]
                existing_parent_id = existing[2]
                existing_path = existing[3]
                
                if existing_name == name and existing_parent_id == parent_id and existing_path == path:
                    # 数据没有变化，不更新
                    logger.debug(f"部门数据未变化，跳过更新: {name} (ID: {dept_id})")
                    return existing[0]  # 返回现有ID
            
            # 数据有变化或不存在，执行插入/更新
            cursor.execute('''
                INSERT OR REPLACE INTO departments 
                (wecom_dept_id, name, parent_id, path, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (dept_id, name, parent_id, path))
            conn.commit()
            logger.debug(f"插入/更新部门成功: {name} (ID: {dept_id})")
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"插入部门失败: {e}")
            return 0
        finally:
            pass  # 保持连接复用

    # ==================== 查询 ====================

    def get_all_departments(self) -> List[Dict]:
        """
        获取所有部门列表
        
        Returns:
            List[Dict]: 部门列表
        """
        try:
            return self.db.fetch_all('SELECT * FROM departments ORDER BY wecom_dept_id')
        except Exception as e:
            logger.error(f"获取部门列表失败: {e}")
            return []

    def get_department_by_id(self, dept_id: int) -> Optional[Dict]:
        """
        根据数据库ID获取部门
        
        Args:
            dept_id: 数据库ID
            
        Returns:
            Optional[Dict]: 部门信息字典，无结果返回None
        """
        try:
            return self.db.fetch_one('SELECT * FROM departments WHERE id = ?', (dept_id,))
        except Exception as e:
            logger.error(f"获取部门失败: {e}")
            return None

    def get_department_by_wecom_id(self, wecom_dept_id: int) -> Optional[Dict]:
        """
        根据企业微信部门ID获取部门
        
        Args:
            wecom_dept_id: 企业微信部门ID
            
        Returns:
            Optional[Dict]: 部门信息字典，无结果返回None
        """
        try:
            return self.db.fetch_one('SELECT * FROM departments WHERE wecom_dept_id = ?', (wecom_dept_id,))
        except Exception as e:
            logger.error(f"获取部门失败: {e}")
            return None

    def get_all_child_dept_ids(self, dept_id: int) -> list:
        """
        获取部门所有子部门的数据库ID列表
        
        使用递归查找所有子部门。
        注意：parent_id字段存储的是企业微信部门ID，不是数据库自增ID。
        
        Args:
            dept_id: 部门的数据库自增ID
            
        Returns:
            list: 所有子部门的数据库ID列表（包含传入的dept_id）
        """
        result = [dept_id]
        try:
            # 先获取当前部门的企业微信ID
            dept = self.db.fetch_one('SELECT wecom_dept_id FROM departments WHERE id = ?', (dept_id,))
            if not dept:
                return result
            
            wecom_id = dept['wecom_dept_id']
            
            # 用企业微信ID查找子部门（parent_id存储的是企业微信ID）
            children = self.db.fetch_all(
                'SELECT id FROM departments WHERE parent_id = ?', 
                (wecom_id,)
            )
            for child in children:
                result.extend(self.get_all_child_dept_ids(child['id']))
        except Exception as e:
            logger.error(f"获取子部门失败: {e}")
        return result

    def get_department_user_count(self, dept_id: int, include_children: bool = True) -> int:
        """
        获取部门下的用户数量
        
        Args:
            dept_id: 部门数据库ID
            include_children: 是否包含子部门用户，默认True
            
        Returns:
            int: 用户数量
        """
        try:
            if include_children:
                # 获取所有子部门ID（包含当前部门）
                child_ids = self.get_all_child_dept_ids(dept_id)
                
                # 构建IN子句的占位符
                placeholders = ','.join('?' * len(child_ids))
                
                # 统计所有子部门的用户数
                result = self.db.fetch_one(f'''
                    SELECT COUNT(DISTINCT user_id) as count 
                    FROM user_department 
                    WHERE dept_id IN ({placeholders})
                ''', tuple(child_ids))
            else:
                # 只统计当前部门的用户数
                result = self.db.fetch_one('''
                    SELECT COUNT(*) as count FROM user_department WHERE dept_id = ?
                ''', (dept_id,))
                
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"获取部门用户数失败: {e}")
            return 0

    # ==================== 更新 ====================

    def update_department_sync_status(self, dept_id: int, status: int, sync_time: str = None):
        """
        更新部门同步状态
        
        Args:
            dept_id: 数据库ID
            status: 同步状态（0=未同步, 1=已同步, 2=需同步, 3=失败）
            sync_time: 同步时间，None则不更新
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            if sync_time:
                cursor.execute('''
                    UPDATE departments SET sync_status = ?, sync_time = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, sync_time, dept_id))
            else:
                cursor.execute('''
                    UPDATE departments SET sync_status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, dept_id))
            conn.commit()
        except Exception as e:
            logger.error(f"更新部门同步状态失败: {e}")
        finally:
            pass

    # ==================== 删除 ====================

    def delete_department_by_wecom_id(self, wecom_dept_id: int) -> bool:
        """
        根据企业微信部门ID删除部门
        
        Args:
            wecom_dept_id: 企业微信部门ID
            
        Returns:
            bool: 删除是否成功
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            # 先获取部门信息用于日志
            dept = self.db.fetch_one('SELECT id, name FROM departments WHERE wecom_dept_id = ?', (wecom_dept_id,))
            if dept:
                dept_id, dept_name = dept['id'], dept['name']
                
                # 删除部门前需要先删除相关的用户-部门关系
                cursor.execute('DELETE FROM user_department WHERE dept_id = ?', (dept_id,))
                
                # 删除部门
                cursor.execute('DELETE FROM departments WHERE wecom_dept_id = ?', (wecom_dept_id,))
                conn.commit()
                logger.info(f"删除部门成功: {dept_name} (企业微信ID: {wecom_dept_id})")
                return True
            return False
        except Exception as e:
            logger.error(f"删除部门失败: {e}")
            return False
        finally:
            pass

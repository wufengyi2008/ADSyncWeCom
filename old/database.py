# -*- coding: utf-8 -*-
"""
database.py - 数据库操作主入口，整合所有数据库操作功能

作者：怡悦2011
日期：2026
"""
import logging
from typing import Dict, List, Optional

from db_base import DatabaseBase
from db_department import DepartmentDB
from db_user import UserDB
from db_log import LogDB

logger = logging.getLogger(__name__)


class Database(DatabaseBase):
    """
    数据库操作主类
    
    整合所有数据库操作功能，保持与旧版本接口兼容
    
    Attributes:
        department: 部门操作实例
        user: 用户操作实例
        log: 日志操作实例
    """
    
    def __init__(self, db_path: str = 'sync.db'):
        """
        初始化数据库
        
        Args:
            db_path: SQLite数据库文件路径，默认'sync.db'
        """
        super().__init__(db_path)
        
        # 初始化子模块
        self.department = DepartmentDB(self)
        self.user = UserDB(self)
        self.log = LogDB(self)
        
        # 初始化数据库（创建表结构）
        self._init_database()

    def _init_database(self):
        """
        初始化数据库表结构
        
        创建所有必要的表：
        - departments: 部门表
        - users: 用户表
        - user_department: 用户-部门关系表
        - sync_logs: 同步日志表
        - operation_logs: 操作日志表
        """
        conn = self._connect()
        cursor = conn.cursor()
        
        # ==================== 创建部门表 ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 自增主键
                wecom_dept_id INTEGER UNIQUE NOT NULL,  -- 企业微信部门ID
                name TEXT NOT NULL,                      -- 部门名称
                parent_id INTEGER,                       -- 父部门ID
                path TEXT,                               -- 部门路径（如：广东省高峰科技有限公司\生产制造中心\SMT部）
                sync_status INTEGER DEFAULT 0,           -- 同步状态：0=未同步, 1=已同步, 2=需同步, 3=失败
                sync_time TEXT,                          -- 最后同步时间
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,-- 创建时间
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP -- 更新时间
            )
        ''')

        # ==================== 创建用户表 ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 自增主键
                wecom_userid TEXT UNIQUE NOT NULL,       -- 企业微信用户ID（工号）
                name TEXT NOT NULL,                      -- 用户姓名
                alias TEXT,                              -- 别名/工号
                email TEXT,                              -- 邮箱
                mobile TEXT,                             -- 手机号
                position TEXT,                           -- 职位
                department_ids TEXT,                     -- 所属部门ID列表（逗号分隔）
                sync_status INTEGER DEFAULT 0,           -- 同步状态：0=未同步, 1=已同步, 2=需同步, 3=已禁用
                sync_time TEXT,                          -- 最后同步时间
                ad_exists INTEGER DEFAULT 0,             -- 是否已存在于AD域：0=否, 1=是
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,-- 创建时间
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP -- 更新时间
            )
        ''')

        # ==================== 创建用户-部门关系表 ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_department (
                id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 自增主键
                user_id INTEGER NOT NULL,                 -- 用户ID
                dept_id INTEGER NOT NULL,                 -- 部门ID
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,-- 创建时间
                UNIQUE(user_id, dept_id)                 -- 防止重复关系
            )
        ''')

        # ==================== 创建同步日志表 ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 自增主键
                sync_type TEXT NOT NULL,                  -- 同步类型：SYNC=普通同步, AUTO=自动同步
                target_type TEXT NOT NULL,                -- 目标类型：DEPT=部门, USER=用户, WECOM=企业微信
                target_id INTEGER,                        -- 目标ID
                target_name TEXT,                         -- 目标名称
                status TEXT NOT NULL,                     -- 状态：SUCCESS=成功, FAILED=失败, PARTIAL=部分成功
                message TEXT,                             -- 详细信息/错误消息
                created_at TEXT DEFAULT CURRENT_TIMESTAMP   -- 创建时间
            )
        ''')

        # ==================== 创建操作日志表 ====================
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 自增主键
                log_level TEXT NOT NULL,                 -- 日志级别：DEBUG, INFO, WARNING, ERROR
                module TEXT NOT NULL,                    -- 模块名称：GUI, AD_SYNC, SYNC_DB, DATABASE等
                message TEXT NOT NULL,                    -- 日志消息
                details TEXT,                             -- 详细信息（如命令内容、堆栈等）
                created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
            )
        ''')

        # ==================== 检查并添加必要字段（兼容旧数据库）====================
        try:
            cursor.execute("SELECT alias FROM users LIMIT 1")
        except Exception:
            cursor.execute('ALTER TABLE users ADD COLUMN alias TEXT')
            logger.info("添加 alias 字段成功")

        try:
            cursor.execute("SELECT position FROM users LIMIT 1")
        except Exception:
            cursor.execute('ALTER TABLE users ADD COLUMN position TEXT')
            logger.info("添加 position 字段成功")

        conn.commit()
        logger.info("数据库初始化完成")

    # ==================== 兼容旧接口的方法 ====================
    # 以下方法保持与旧版本database.py接口兼容
    # 实际实现委托给相应的子模块

    def insert_department(self, dept_id: int, name: str, parent_id: int, path: str) -> int:
        """插入或更新部门（委托给department子模块）"""
        return self.department.insert_department(dept_id, name, parent_id, path)

    def get_all_departments(self) -> List[Dict]:
        """获取所有部门列表"""
        return self.department.get_all_departments()

    def get_department_by_id(self, dept_id: int) -> Optional[Dict]:
        """根据数据库ID获取部门"""
        return self.department.get_department_by_id(dept_id)

    def get_department_by_wecom_id(self, wecom_dept_id: int) -> Optional[Dict]:
        """根据企业微信部门ID获取部门"""
        return self.department.get_department_by_wecom_id(wecom_dept_id)

    def update_department_sync_status(self, dept_id: int, status: int, sync_time: str = None):
        """更新部门同步状态"""
        self.department.update_department_sync_status(dept_id, status, sync_time)

    def delete_department_by_wecom_id(self, wecom_dept_id: int) -> bool:
        """根据企业微信部门ID删除部门"""
        return self.department.delete_department_by_wecom_id(wecom_dept_id)

    def get_all_child_dept_ids(self, dept_id: int) -> list:
        """获取部门所有子部门的ID列表"""
        return self.department.get_all_child_dept_ids(dept_id)

    def get_department_user_count(self, dept_id: int, include_children: bool = True) -> int:
        """获取部门下的用户数量"""
        return self.department.get_department_user_count(dept_id, include_children)

    def insert_user(self, wecom_userid: str, name: str, email: str = None, mobile: str = None, 
                   department_ids: str = None, alias: str = None, position: str = None) -> int:
        """插入或更新用户"""
        return self.user.insert_user(wecom_userid, name, email, mobile, department_ids, alias, position)

    def get_all_users(self) -> List[Dict]:
        """获取所有用户列表"""
        return self.user.get_all_users()

    def get_users_by_department(self, dept_id: int) -> List[Dict]:
        """获取指定部门的用户列表"""
        return self.user.get_users_by_department(dept_id)

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据数据库ID获取用户"""
        return self.user.get_user_by_id(user_id)

    def get_user_by_wecom_id(self, wecom_userid: str) -> Optional[Dict]:
        """根据企业微信用户ID获取用户"""
        return self.user.get_user_by_wecom_id(wecom_userid)

    def update_user_sync_status(self, user_id: int, status: int, sync_time: str = None):
        """更新用户同步状态"""
        self.user.update_user_sync_status(user_id, status, sync_time)

    def update_user_ad_exists(self, user_id: int, exists: int):
        """更新用户AD存在状态"""
        self.user.update_user_ad_exists(user_id, exists)

    def delete_user_by_wecom_id(self, wecom_userid: str) -> bool:
        """根据企业微信用户ID删除用户"""
        return self.user.delete_user_by_wecom_id(wecom_userid)

    def insert_user_department(self, user_id: int, dept_id: int) -> bool:
        """添加用户与部门的关联"""
        return self.user.insert_user_department(user_id, dept_id)

    def clear_user_department(self, user_id: int) -> bool:
        """清除用户的所有部门关联"""
        return self.user.clear_user_department(user_id)

    def insert_sync_log(self, sync_type: str, target_type: str, target_id: int,
                       target_name: str, status: str, message: str = None) -> int:
        """插入同步日志"""
        return self.log.insert_sync_log(sync_type, target_type, target_id, target_name, status, message)

    def get_sync_logs(self, limit: int = 100) -> List[Dict]:
        """获取同步日志"""
        return self.log.get_sync_logs(limit)

    def insert_operation_log(self, log_level: str, module: str, message: str, details: str = None) -> int:
        """插入操作日志"""
        return self.log.insert_operation_log(log_level, module, message, details)

    def get_operation_logs(self, limit: int = 100, log_level: str = None, module: str = None) -> List[Dict]:
        """获取操作日志"""
        return self.log.get_operation_logs(limit, log_level, module)

    def clear_operation_logs(self, days: int = 30) -> int:
        """清理旧的操作日志"""
        return self.log.clear_operation_logs(days)

    def clear_all_data(self):
        """
        清空所有数据
        
        警告：此操作不可恢复！
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            # 按外键依赖顺序删除
            cursor.execute('DELETE FROM user_department')
            cursor.execute('DELETE FROM users')
            cursor.execute('DELETE FROM departments')
            conn.commit()
            logger.info("已清空所有数据")
        except Exception as e:
            logger.error(f"清空数据失败: {e}")
        finally:
            pass

    def get_statistics(self) -> Dict:
        """
        获取同步统计数据
        
        Returns:
            Dict: 统计数据字典
        """
        try:
            # 统计各部门数据
            dept_stats = self.fetch_all('''
                SELECT 
                    sync_status,
                    COUNT(*) as count
                FROM departments
                GROUP BY sync_status
            ''')
            
            # 统计各用户数据
            user_stats = self.fetch_all('''
                SELECT 
                    sync_status,
                    COUNT(*) as count
                FROM users
                GROUP BY sync_status
            ''')
            
            # 总用户数
            total_users = self.fetch_one('SELECT COUNT(*) as count FROM users')
            
            # 总部门数
            total_depts = self.fetch_one('SELECT COUNT(*) as count FROM departments')
            
            # 最近的同步日志
            recent_logs = self.get_sync_logs(5)
            
            # 构建统计字典
            dept_dict = {item['sync_status']: item['count'] for item in dept_stats}
            user_dict = {item['sync_status']: item['count'] for item in user_stats}
            
            return {
                'departments': dept_dict,
                'users': user_dict,
                'total_users': total_users['count'] if total_users else 0,
                'total_departments': total_depts['count'] if total_depts else 0,
                'synced_users': user_dict.get(1, 0),           # 状态1表示已同步
                'synced_departments': dept_dict.get(1, 0),     # 状态1表示已同步
                'recent_logs': recent_logs
            }
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            return {}

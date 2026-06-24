# -*- coding: utf-8 -*-
"""
db_base.py - 数据库连接基础模块，提供连接管理和通用查询方法

作者：怡悦2011
日期：2026
"""
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseBase:
    """
    数据库连接基础类
    
    提供数据库连接管理和通用工具方法
    
    Attributes:
        db_path: 数据库文件路径
        conn: 数据库连接对象
    """
    
    def __init__(self, db_path: str = 'sync.db'):
        """
        初始化数据库连接
        
        Args:
            db_path: SQLite数据库文件路径，默认'sync.db'
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        
        # 确保数据库目录存在
        db_dir = Path(db_path).parent
        if db_dir and db_dir != Path('.'):
            db_dir.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """
        建立或复用数据库连接
        
        使用单例模式保持连接复用，提高性能。
        设置 check_same_thread=False 允许跨线程使用连接对象。
        
        Returns:
            sqlite3.Connection: 数据库连接对象
        """
        if self.conn is None:
            # check_same_thread=False 允许跨线程使用连接
            # 这是必要的，因为GUI在主线程创建连接，同步操作在子线程执行
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # 返回可按列名访问的Row对象
            logger.debug(f"数据库连接已建立: {self.db_path}")
        return self.conn

    def _close(self):
        """
        关闭数据库连接
        
        注意：调用此方法后会断开连接
        """
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("数据库连接已关闭")

    @contextmanager
    def get_connection(self):
        """
        上下文管理器，自动管理数据库事务
        
        使用方法：
            with db.get_connection() as conn:
                cursor.execute(...)
                # 自动提交或回滚
        
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()  # 发生异常时回滚事务
            logger.error(f"数据库事务失败: {e}")
            raise
        finally:
            pass  # 保持连接复用，不关闭

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        执行单条SQL语句
        
        Args:
            sql: SQL语句
            params: 参数元组
            
        Returns:
            sqlite3.Cursor: 游标对象
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def executescript(self, sql: str) -> sqlite3.Cursor:
        """
        执行多条SQL语句（脚本）
        
        Args:
            sql: SQL脚本
            
        Returns:
            sqlite3.Cursor: 游标对象
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.executescript(sql)
        conn.commit()
        return cursor

    def fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """
        查询单条记录
        
        Args:
            sql: SELECT语句
            params: 参数元组
            
        Returns:
            Optional[Dict]: 查询结果字典，无结果返回None
        """
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> List[Dict]:
        """
        查询多条记录
        
        Args:
            sql: SELECT语句
            params: 参数元组
            
        Returns:
            List[Dict]: 查询结果列表
        """
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        """关闭数据库连接（对外暴露的方法）"""
        self._close()

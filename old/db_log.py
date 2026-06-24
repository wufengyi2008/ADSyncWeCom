# -*- coding: utf-8 -*-
"""
db_log.py - 日志数据操作模块，提供同步日志和操作日志管理

作者：怡悦2011
日期：2026
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LogDB:
    """日志数据库操作类"""

    def __init__(self, db_base):
        self.db = db_base

    def insert_sync_log(self, sync_type: str, target_type: str, target_id: int,
                       target_name: str, status: str, message: str = None) -> int:
        """
        插入同步日志
        
        Args:
            sync_type: 同步类型 (SYNC, DELETE, UPDATE)
            target_type: 目标类型 (DEPARTMENT, USER)
            target_id: 目标ID
            target_name: 目标名称
            status: 状态 (SUCCESS, FAILED, DISABLED, SYNCED)
            message: 附加消息
            
        Returns:
            日志ID（成功）或0（失败）
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO sync_logs (sync_type, target_type, target_id, target_name, status, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (sync_type, target_type, target_id, target_name, status, message))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"插入同步日志失败: {e}")
            return 0

    def batch_insert_sync_logs(self, logs: List[Dict]) -> int:
        """
        批量插入同步日志
        
        Args:
            logs: 日志列表，每项包含 sync_type, target_type, target_id, target_name, status, message
            
        Returns:
            成功插入的数量
        """
        if not logs:
            return 0
            
        conn = self.db._connect()
        cursor = conn.cursor()
        count = 0
        try:
            for log in logs:
                try:
                    cursor.execute('''
                        INSERT INTO sync_logs (sync_type, target_type, target_id, target_name, status, message, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        log.get('sync_type'),
                        log.get('target_type'),
                        log.get('target_id'),
                        log.get('target_name'),
                        log.get('status'),
                        log.get('message')
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"批量插入日志失败: {log.get('target_name')} - {e}")
            conn.commit()
            logger.info(f"批量插入同步日志完成，成功 {count} 条")
            return count
        except Exception as e:
            logger.error(f"批量插入同步日志失败: {e}")
            return 0

    def get_sync_logs(self, limit: int = 100) -> List[Dict]:
        """
        获取同步日志列表
        
        Args:
            limit: 返回条数限制，默认100
            
        Returns:
            日志列表
        """
        try:
            return self.db.fetch_all('SELECT * FROM sync_logs ORDER BY created_at DESC LIMIT ?', (limit,))
        except Exception as e:
            logger.error(f"获取同步日志失败: {e}")
            return []

    def get_sync_logs_by_type(self, sync_type: str = None, target_type: str = None, 
                             status: str = None, limit: int = 100) -> List[Dict]:
        """
        按条件筛选同步日志
        
        Args:
            sync_type: 同步类型筛选
            target_type: 目标类型筛选
            status: 状态筛选
            limit: 返回条数限制
            
        Returns:
            日志列表
        """
        try:
            query = 'SELECT * FROM sync_logs WHERE 1=1'
            params = []
            
            if sync_type:
                query += ' AND sync_type = ?'
                params.append(sync_type)
            if target_type:
                query += ' AND target_type = ?'
                params.append(target_type)
            if status:
                query += ' AND status = ?'
                params.append(status)
                
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            return self.db.fetch_all(query, tuple(params))
        except Exception as e:
            logger.error(f"获取同步日志失败: {e}")
            return []

    def insert_operation_log(self, log_level: str, module: str, message: str, details: str = None) -> int:
        """
        插入操作日志
        
        Args:
            log_level: 日志级别 (INFO, WARNING, ERROR)
            module: 模块名
            message: 日志消息
            details: 详细信息
            
        Returns:
            日志ID（成功）或0（失败）
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO operation_logs (log_level, module, message, details, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (log_level, module, message, details))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"插入操作日志失败: {e}")
            return 0

    def batch_insert_operation_logs(self, logs: List[Dict]) -> int:
        """
        批量插入操作日志
        
        Args:
            logs: 日志列表，每项包含 log_level, module, message, details
            
        Returns:
            成功插入的数量
        """
        if not logs:
            return 0
            
        conn = self.db._connect()
        cursor = conn.cursor()
        count = 0
        try:
            for log in logs:
                try:
                    cursor.execute('''
                        INSERT INTO operation_logs (log_level, module, message, details, created_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        log.get('log_level'),
                        log.get('module'),
                        log.get('message'),
                        log.get('details')
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"批量插入操作日志失败: {log.get('message')} - {e}")
            conn.commit()
            logger.info(f"批量插入操作日志完成，成功 {count} 条")
            return count
        except Exception as e:
            logger.error(f"批量插入操作日志失败: {e}")
            return 0

    def get_operation_logs(self, limit: int = 100, log_level: str = None, module: str = None) -> List[Dict]:
        """
        获取操作日志
        
        Args:
            limit: 返回条数限制，默认100
            log_level: 日志级别筛选（可选）
            module: 模块名称筛选（可选）
            
        Returns:
            日志列表
        """
        try:
            query = 'SELECT * FROM operation_logs WHERE 1=1'
            params = []
            
            if log_level:
                query += ' AND log_level = ?'
                params.append(log_level)
            if module:
                query += ' AND module = ?'
                params.append(module)
                
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            return self.db.fetch_all(query, tuple(params))
        except Exception as e:
            logger.error(f"获取操作日志失败: {e}")
            return []

    def clear_operation_logs(self, days: int = 30) -> int:
        """
        清理指定天数之前的操作日志
        
        Args:
            days: 保留天数，默认30天
            
        Returns:
            删除的日志数量
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(f'DELETE FROM operation_logs WHERE created_at < DATE("now", "-{days} days")')
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"清理操作日志完成，删除 {deleted} 条")
            return deleted
        except Exception as e:
            logger.error(f"清理操作日志失败: {e}")
            return 0

    def get_operation_logs_by_level(self, log_level: str, limit: int = 100) -> List[Dict]:
        """
        按级别获取操作日志
        
        Args:
            log_level: 日志级别
            limit: 返回条数限制
            
        Returns:
            日志列表
        """
        try:
            return self.db.fetch_all(
                'SELECT * FROM operation_logs WHERE log_level = ? ORDER BY created_at DESC LIMIT ?',
                (log_level, limit)
            )
        except Exception as e:
            logger.error(f"获取操作日志失败: {e}")
            return []

    def clean_old_logs(self, days: int = 30) -> int:
        """
        清理指定天数之前的日志
        
        Args:
            days: 保留天数，默认30天
            
        Returns:
            删除的日志数量
        """
        conn = self.db._connect()
        cursor = conn.cursor()
        try:
            # 删除同步日志
            cursor.execute(f'DELETE FROM sync_logs WHERE created_at < DATE("now", "-{days} days")')
            sync_deleted = cursor.rowcount
            
            # 删除操作日志
            cursor.execute(f'DELETE FROM operation_logs WHERE created_at < DATE("now", "-{days} days")')
            op_deleted = cursor.rowcount
            
            conn.commit()
            total_deleted = sync_deleted + op_deleted
            logger.info(f"清理日志完成，删除 {total_deleted} 条（同步日志: {sync_deleted}, 操作日志: {op_deleted}）")
            return total_deleted
        except Exception as e:
            logger.error(f"清理日志失败: {e}")
            return 0

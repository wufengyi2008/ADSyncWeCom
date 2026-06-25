import time
import threading
from datetime import datetime, timedelta

class SyncScheduler:
    def __init__(self):
        self.db = None
        self.config = None
        self.sync_service = None
        self._scheduler_thread = None
        self._stop_event = threading.Event()
        self._today_executed = False
        self._last_check_date = datetime.now().date()
        self._lock = threading.Lock()
        self._is_running = False
        self._initialized = False
        self._sync_time = '02:00'
        self._next_sync_time = None
        self._on_sync_complete_callback = None
    
    def _ensure_initialized(self):
        if not self._initialized:
            from database import Database
            from config_manager import ConfigManager
            from sync_service import SyncService
            self.db = Database()
            self.config = ConfigManager()
            self.sync_service = SyncService()
            self._sync_time = self.config.get('sync_time', '02:00')
            self._calculate_next_sync_time()
            self._initialized = True
    
    def _calculate_next_sync_time(self):
        now = datetime.now()
        try:
            hour, minute = map(int, self._sync_time.split(':'))
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if target_time <= now:
                target_time += timedelta(days=1)
            
            self._next_sync_time = target_time
            return self._next_sync_time
        except:
            return None
    
    def _get_next_sync_time(self):
        if not self._next_sync_time:
            self._calculate_next_sync_time()
        return self._next_sync_time
    
    def _should_run(self):
        if not self._initialized:
            return False
        
        now = datetime.now()
        
        if now.date() != self._last_check_date:
            self._today_executed = False
            self._last_check_date = now.date()
        
        if self._today_executed:
            return False
        
        try:
            hour, minute = map(int, self._sync_time.split(':'))
            
            if now.hour == hour and now.minute == minute:
                return True
            
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_time < now:
                target_time += timedelta(days=1)
            
            time_diff = (target_time - now).total_seconds()
            
            if 0 < time_diff <= 60:
                return True
            
            if now.hour == hour and now.minute > minute:
                if not self._today_executed:
                    return True
            
            return False
        except:
            return False
    
    def _daily_reset(self):
        while not self._stop_event.is_set():
            if self._stop_event.wait(60):
                break
            
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                self._today_executed = False
                self._calculate_next_sync_time()
    
    def _sync_step(self, step_name, sync_func, **kwargs):
        try:
            self.db.log_operation('SYNC_AUTO', step_name, f'开始执行: {step_name}')
            result = sync_func(**kwargs)
            status = result.get('status', 'UNKNOWN')
            message = result.get('message', '')
            sync_count = result.get('sync_count', 0)
            error_count = result.get('error_count', 0)
            
            if status == 'SUCCESS':
                self.db.log_operation('SYNC_AUTO', step_name, f'执行成功: {sync_count}条记录，错误: {error_count}条')
            else:
                self.db.log_operation('SYNC_ERROR', step_name, f'执行失败: {message}')
            
            return status == 'SUCCESS'
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.db.log_operation('SYNC_ERROR', step_name, f'执行异常: {str(e)}\n完整错误堆栈:\n{error_trace}')
            return False
    
    def _auto_sync_workflow(self):
        results = []
        errors = []
        total_sync_count = 0
        total_error_count = 0
        start_time = datetime.now()
        dept_stats = {}
        user_stats = {}
        
        try:
            self.db.log_operation('SYNC_AUTO', 'START', '【自动同步】开始执行自动同步工作流')
            
            wecom_result = self.sync_service.sync_wecom_to_db()
            wecom_status = wecom_result.get('status', 'UNKNOWN')
            wecom_sync_count = wecom_result.get('sync_count', 0)
            wecom_error_count = wecom_result.get('error_count', 0)
            total_sync_count += wecom_sync_count
            total_error_count += wecom_error_count
            results.append(f"企微全量同步: {wecom_status} (同步: {wecom_sync_count}, 错误: {wecom_error_count})")
            if wecom_status != 'SUCCESS':
                errors.append(f"企微全量同步失败: {wecom_result.get('message', '')}")
            self.db.log_operation('SYNC_AUTO', 'WECOM_TO_DB', f'【自动同步】企微全量同步完成: {wecom_status}, {wecom_sync_count}条记录, {wecom_error_count}条错误')
            
            dept_total = self.db.fetch_one('SELECT COUNT(*) FROM departments')['COUNT(*)']
            dept_synced = self.db.fetch_one('SELECT COUNT(*) FROM departments WHERE sync_status = 1')['COUNT(*)']
            dept_unsynced = self.db.fetch_one('SELECT COUNT(*) FROM departments WHERE sync_status = 0')['COUNT(*)']
            dept_needsync = self.db.fetch_one('SELECT COUNT(*) FROM departments WHERE sync_status = 2')['COUNT(*)']
            dept_stats = {
                'total': dept_total,
                'synced': dept_synced,
                'unsynced': dept_unsynced,
                'needsync': dept_needsync
            }
            
            user_total = self.db.fetch_one('SELECT COUNT(*) FROM users')['COUNT(*)']
            user_synced = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 1')['COUNT(*)']
            user_unsynced = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 0')['COUNT(*)']
            user_needsync = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 2')['COUNT(*)']
            user_disabled = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 3')['COUNT(*)']
            user_stats = {
                'total': user_total,
                'synced': user_synced,
                'unsynced': user_unsynced,
                'needsync': user_needsync,
                'disabled': user_disabled
            }
            
            ad_status_result = self.sync_service.sync_ad_status()
            ad_status_status = ad_status_result.get('status', 'UNKNOWN')
            ad_status_sync_count = ad_status_result.get('sync_count', 0)
            ad_status_error_count = ad_status_result.get('error_count', 0)
            total_sync_count += ad_status_sync_count
            total_error_count += ad_status_error_count
            results.append(f"AD状态同步: {ad_status_status} (同步: {ad_status_sync_count}, 错误: {ad_status_error_count})")
            if ad_status_status != 'SUCCESS':
                errors.append(f"AD状态同步失败: {ad_status_result.get('message', '')}")
            self.db.log_operation('SYNC_AUTO', 'AD_STATUS', f'【自动同步】AD状态同步完成: {ad_status_status}, {ad_status_sync_count}条记录, {ad_status_error_count}条错误')
            
            dept_sync_total = 0
            dept_sync_errors = 0
            dept_sync_success = True
            user_sync_total = 0
            user_sync_errors = 0
            user_sync_success = True
            sync_depts_str = self.config.get('sync_departments', '')
            if sync_depts_str:
                sync_dept_ids = [d.strip() for d in sync_depts_str.split(',') if d.strip()]
                if sync_dept_ids:
                    for dept_id in sync_dept_ids:
                        try:
                            dept_info = self.db.fetch_one('SELECT name FROM departments WHERE wecom_id = ?', (dept_id,))
                            dept_name = dept_info['name'] if dept_info else dept_id
                            
                            dept_result = self.sync_service.sync_department_users_to_ad(dept_wecom_id=dept_id)
                            dept_status = dept_result.get('status', 'UNKNOWN')
                            dept_sync_count = dept_result.get('sync_count', 0)
                            dept_error_count = dept_result.get('error_count', 0)
                            total_sync_count += dept_sync_count
                            total_error_count += dept_error_count
                            dept_sync_total += 1
                            user_sync_total += dept_sync_count
                            user_sync_errors += dept_error_count
                            
                            if dept_status != 'SUCCESS':
                                dept_sync_success = False
                                user_sync_success = False
                                dept_sync_errors += 1
                                errors.append(f"部门[{dept_name}]同步失败: {dept_result.get('message', '')}")
                            
                            self.db.log_operation('SYNC_AUTO', f'DEPT_USERS_TO_AD_{dept_id}', 
                                                 f'【自动同步】部门[{dept_name}]同步完成: {dept_status}, {dept_sync_count}条记录, {dept_error_count}条错误')
                        except Exception as e:
                            import traceback
                            error_trace = traceback.format_exc()
                            dept_sync_success = False
                            user_sync_success = False
                            dept_sync_errors += 1
                            errors.append(f"部门[{dept_id}]同步异常: {str(e)}")
                            self.db.log_operation('SYNC_ERROR', f'DEPT_USERS_TO_AD_{dept_id}', 
                                                 f'【自动同步】部门同步异常: {str(e)}\n完整错误堆栈:\n{error_trace}')
                    
                    dept_sync_status = 'SUCCESS' if dept_sync_success else 'FAILED'
                    user_sync_status = 'SUCCESS' if user_sync_success else 'FAILED'
                    results.append(f"部门同步: {dept_sync_status} (同步: {dept_sync_total}, 错误: {dept_sync_errors})")
                    results.append(f"用户同步: {user_sync_status} (同步: {user_sync_total}, 错误: {user_sync_errors})")
                else:
                    results.append("选中部门同步: 未配置允许同步的部门，跳过")
                    self.db.log_operation('SYNC_AUTO', 'DEPT_SYNC', '【自动同步】未配置允许同步的部门，跳过部门同步')
            else:
                results.append("选中部门同步: 未配置允许同步的部门，跳过")
                self.db.log_operation('SYNC_AUTO', 'DEPT_SYNC', '【自动同步】未配置允许同步的部门，跳过部门同步')
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            workflow_status = 'SUCCESS' if not errors else 'FAILED'
            self.db.log_operation('SYNC_AUTO', 'COMPLETE', f'【自动同步】工作流执行完成: {workflow_status}, 总同步: {total_sync_count}条, 总错误: {total_error_count}条, 耗时: {duration:.2f}秒')
            
            self._send_bot_notification(results, errors, total_sync_count, total_error_count, duration, workflow_status, dept_stats, user_stats)
            
            if self._on_sync_complete_callback:
                try:
                    self._on_sync_complete_callback()
                except Exception as e:
                    self.db.log_operation('SYNC_ERROR', 'CALLBACK', f'【自动同步】同步完成回调执行失败: {str(e)}')
            
            return workflow_status == 'SUCCESS'
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            errors.append(f"自动同步工作流异常: {str(e)}")
            self.db.log_operation('SYNC_ERROR', 'WORKFLOW', f'【自动同步】工作流异常: {str(e)}\n完整错误堆栈:\n{error_trace}')
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self._send_bot_notification(results, errors, total_sync_count, total_error_count, duration, 'FAILED', dept_stats, user_stats)
            
            return False
    
    def _send_bot_notification(self, results, errors, total_sync_count, total_error_count, duration, workflow_status, dept_stats=None, user_stats=None):
        bot_key = self.config.get('wechat_bot_key', '')
        if not bot_key:
            return
        
        try:
            from wecom_api import WeComAPI
            wecom_api = WeComAPI()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if dept_stats is None:
                dept_stats = {}
            if user_stats is None:
                user_stats = {}
            
            if workflow_status == 'SUCCESS':
                content = f"✅ 【自动同步完成】\n\n"
                content += f"⏰ 执行时间: {timestamp}\n"
                content += f"⏱️ 耗时: {duration:.2f}秒\n"
                content += f"📊 同步统计: 成功{total_sync_count}条, 错误{total_error_count}条\n\n"
                content += "📋 执行详情:\n"
                for result in results:
                    content += f"  - {result}\n"
                
                if dept_stats:
                    content += "\n🏢 部门信息:\n"
                    content += f"  部门总数: {dept_stats.get('total', 0)}\n"
                    content += f"  已同步: {dept_stats.get('synced', 0)}\n"
                    content += f"  未同步: {dept_stats.get('unsynced', 0)}\n"
                    content += f"  需同步: {dept_stats.get('needsync', 0)}\n"
                
                if user_stats:
                    content += "\n👥 用户信息:\n"
                    content += f"  用户总数: {user_stats.get('total', 0)}\n"
                    content += f"  已同步: {user_stats.get('synced', 0)}\n"
                    content += f"  未同步: {user_stats.get('unsynced', 0)}\n"
                    content += f"  需同步: {user_stats.get('needsync', 0)}\n"
                    content += f"  已禁用: {user_stats.get('disabled', 0)}\n"
            else:
                content = f"❌ 【自动同步失败】\n\n"
                content += f"⏰ 执行时间: {timestamp}\n"
                content += f"⏱️ 耗时: {duration:.2f}秒\n"
                content += f"📊 同步统计: 成功{total_sync_count}条, 错误{total_error_count}条\n\n"
                content += "📋 执行详情:\n"
                for result in results:
                    content += f"  - {result}\n"
                content += "\n❌ 错误信息:\n"
                for error in errors[:5]:
                    content += f"  - {error}\n"
                if len(errors) > 5:
                    content += f"  - ... (共{len(errors)}个错误)\n"
                
                if dept_stats:
                    content += "\n🏢 部门信息:\n"
                    content += f"  部门总数: {dept_stats.get('total', 0)}\n"
                    content += f"  已同步: {dept_stats.get('synced', 0)}\n"
                    content += f"  未同步: {dept_stats.get('unsynced', 0)}\n"
                    content += f"  需同步: {dept_stats.get('needsync', 0)}\n"
                
                if user_stats:
                    content += "\n👥 用户信息:\n"
                    content += f"  用户总数: {user_stats.get('total', 0)}\n"
                    content += f"  已同步: {user_stats.get('synced', 0)}\n"
                    content += f"  未同步: {user_stats.get('unsynced', 0)}\n"
                    content += f"  需同步: {user_stats.get('needsync', 0)}\n"
                    content += f"  已禁用: {user_stats.get('disabled', 0)}\n"
            
            wecom_api.send_bot_message(content)
        except Exception as e:
            self.db.log_operation('SYNC_ERROR', 'BOT_NOTIFY', f'【自动同步】发送企业微信机器人通知失败: {str(e)}')
    
    def _scheduler_loop(self):
        self._ensure_initialized()
        self._last_check_date = datetime.now().date()
        
        reset_thread = threading.Thread(target=self._daily_reset, daemon=True)
        reset_thread.start()
        
        while not self._stop_event.is_set():
            if self._stop_event.wait(60):
                break
            
            current_sync_time = self.config.get('sync_time', '02:00')
            if current_sync_time != self._sync_time:
                self._sync_time = current_sync_time
                self._calculate_next_sync_time()
            
            if self._should_run():
                try:
                    self._auto_sync_workflow()
                    self._today_executed = True
                    self._calculate_next_sync_time()
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    self.db.log_operation('SYNC_ERROR', 'SCHEDULER', f'调度器执行异常: {str(e)}\n完整错误堆栈:\n{error_trace}')
        
        self._is_running = False
    
    def is_running(self):
        with self._lock:
            return self._is_running
    
    def set_on_sync_complete_callback(self, callback):
        self._on_sync_complete_callback = callback
    
    def start(self):
        with self._lock:
            if self._is_running:
                return
            
            if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
                return
            
            self._stop_event.clear()
            self._today_executed = False
            self._is_running = True
            
            if self._initialized:
                self._sync_time = self.config.get('sync_time', '02:00')
                self._calculate_next_sync_time()
            
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True
            )
            self._scheduler_thread.start()
    
    def stop(self):
        with self._lock:
            if not self._is_running:
                return
            
            self._stop_event.set()
            
            if self._scheduler_thread and self._scheduler_thread.is_alive():
                self._scheduler_thread.join(timeout=5)
            
            self._scheduler_thread = None
            self._is_running = False
    
    def trigger_manual_sync(self):
        try:
            result = {}
            
            wecom_result = self.sync_service.sync_wecom_to_db()
            result['wecom_to_db'] = wecom_result
            
            ad_status_result = self.sync_service.sync_ad_status()
            result['ad_status'] = ad_status_result
            
            sync_depts_str = self.config.get('sync_departments', '')
            if sync_depts_str:
                sync_dept_ids = [d.strip() for d in sync_depts_str.split(',') if d.strip()]
                dept_results = {}
                for dept_id in sync_dept_ids:
                    dept_result = self.sync_service.sync_department_users_to_ad(dept_wecom_id=dept_id)
                    dept_results[dept_id] = dept_result
                result['dept_sync'] = dept_results
            
            return {'status': 'success', 'message': '手动同步完成', 'results': result}
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            return {'status': 'error', 'message': str(e), 'traceback': error_trace}
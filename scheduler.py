import time
import threading
from datetime import datetime

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
    
    def _ensure_initialized(self):
        if not self._initialized:
            from database import Database
            from config_manager import ConfigManager
            from sync_service import SyncService
            self.db = Database()
            self.config = ConfigManager()
            self.sync_service = SyncService()
            self._initialized = True
    
    def _should_run(self):
        if not self._initialized:
            return False
        sync_time = self.config.get('sync_time', '02:00')
        
        try:
            hour, minute = map(int, sync_time.split(':'))
            now = datetime.now()
            
            if now.date() != self._last_check_date:
                self._today_executed = False
                self._last_check_date = now.date()
            
            if self._today_executed:
                return False
            
            if now.hour == hour and now.minute == minute:
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
    
    def _scheduler_loop(self):
        self._ensure_initialized()
        self._last_check_date = datetime.now().date()
        
        reset_thread = threading.Thread(target=self._daily_reset, daemon=True)
        reset_thread.start()
        
        while not self._stop_event.is_set():
            if self._stop_event.wait(60):
                break
            
            if self._should_run():
                try:
                    self.sync_service.sync_wecom_to_db()
                    self.sync_service.sync_db_to_ad()
                    self._today_executed = True
                except Exception as e:
                    pass
        
        self._is_running = False
    
    def is_running(self):
        with self._lock:
            return self._is_running
    
    def start(self):
        with self._lock:
            if self._is_running:
                return
            
            if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
                return
            
            self._stop_event.clear()
            self._today_executed = False
            self._is_running = True
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
            self.sync_service.sync_wecom_to_db()
            self.sync_service.sync_db_to_ad()
            return {'status': 'success', 'message': '手动同步完成'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

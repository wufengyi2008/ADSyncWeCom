import os
import sys
import sqlite3
import hashlib
import threading
import time

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class Database:
    _instance = None
    _conn = None
    _lock = threading.Lock()
    
    DB_FILE = os.path.join(get_app_dir(), 'data', 'sync.db')
    DB_KEY = hashlib.sha256(b'WeCom_AD_Sync_Secure_Key_2024').digest().hex()[:32]
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._conn is None:
            self._ensure_data_dir()
            self._connect()
    
    def _ensure_data_dir(self):
        data_dir = os.path.dirname(self.DB_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _connect(self):
        try:
            try:
                from pysqlcipher3 import dbapi2 as sqlite
                self._conn = sqlite.connect(self.DB_FILE, timeout=30)
                cursor = self._conn.cursor()
                cursor.execute(f"PRAGMA key='{self.DB_KEY}'")
                cursor.execute("PRAGMA cipher_compatibility = 3")
                cursor.execute("PRAGMA kdf_iter = 64000")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                self._conn.row_factory = sqlite3.Row
                self._init_tables()
            except ImportError:
                self._conn = sqlite3.connect(self.DB_FILE, check_same_thread=False, timeout=30)
                cursor = self._conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                self._conn.row_factory = sqlite3.Row
                self._init_tables()
        except Exception as e:
            raise Exception(f"数据库连接失败: {str(e)}")
    
    def _init_tables(self):
        cursor = self._conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wecom_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                parent_wecom_id TEXT,
                order_num INTEGER DEFAULT 0,
                sync_status INTEGER DEFAULT 0,
                sync_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wecom_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                account TEXT NOT NULL,
                employee_id TEXT,
                position TEXT,
                email TEXT,
                mobile TEXT,
                sync_status INTEGER DEFAULT 0,
                sync_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_department (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_wecom_id TEXT NOT NULL,
                dept_wecom_id TEXT NOT NULL,
                FOREIGN KEY(user_wecom_id) REFERENCES users(wecom_id),
                FOREIGN KEY(dept_wecom_id) REFERENCES departments(wecom_id),
                UNIQUE(user_wecom_id, dept_wecom_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                sync_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                start_time TEXT NOT NULL,
                end_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT NOT NULL,
                operator TEXT DEFAULT 'SYSTEM',
                target TEXT,
                detail TEXT,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_auth_time TEXT NOT NULL,
                duration_days INTEGER NOT NULL,
                auth_code TEXT NOT NULL,
                verified INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self._conn.commit()
    
    def execute(self, sql, params=None, retries=3):
        with self._lock:
            for attempt in range(retries):
                try:
                    cursor = self._conn.cursor()
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                    self._conn.commit()
                    return cursor
                except sqlite3.OperationalError as e:
                    if attempt < retries - 1 and 'locked' in str(e).lower():
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise
    
    def fetch_one(self, sql, params=None, retries=3):
        with self._lock:
            for attempt in range(retries):
                try:
                    cursor = self._conn.cursor()
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                    return cursor.fetchone()
                except sqlite3.OperationalError as e:
                    if attempt < retries - 1 and 'locked' in str(e).lower():
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise
    
    def fetch_all(self, sql, params=None, retries=3):
        with self._lock:
            for attempt in range(retries):
                try:
                    cursor = self._conn.cursor()
                    if params:
                        cursor.execute(sql, params)
                    else:
                        cursor.execute(sql)
                    return cursor.fetchall()
                except sqlite3.OperationalError as e:
                    if attempt < retries - 1 and 'locked' in str(e).lower():
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise
    
    def executemany(self, sql, params_list, retries=3):
        with self._lock:
            for attempt in range(retries):
                try:
                    cursor = self._conn.cursor()
                    cursor.executemany(sql, params_list)
                    self._conn.commit()
                    return cursor
                except sqlite3.OperationalError as e:
                    if attempt < retries - 1 and 'locked' in str(e).lower():
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    raise
    
    def log_operation(self, operation_type, target, detail):
        # 确保所有参数都是字符串类型
        operation_type = str(operation_type) if operation_type else ''
        target = str(target) if target else ''
        detail = str(detail) if detail else ''
        local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        self.execute(
            'INSERT INTO operation_logs (operation_type, target, detail, created_at) VALUES (?, ?, ?, ?)',
            (operation_type, target, detail, local_time)
        )
    
    def close(self):
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def __del__(self):
        self.close()

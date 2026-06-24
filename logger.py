import logging
import time
from database import Database

def get_local_time():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

class DBLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.db = Database()
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.db.execute(
                'INSERT INTO operation_logs (operation_type, target, detail, created_at) VALUES (?, ?, ?, ?)',
                ('LOG', record.levelname, log_entry, get_local_time())
            )
        except Exception:
            pass

def setup_logger(name='sync_logger'):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    file_handler = logging.FileHandler('sync.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    db_handler = DBLogHandler()
    db_handler.setLevel(logging.INFO)
    db_handler.setFormatter(formatter)
    logger.addHandler(db_handler)
    
    return logger

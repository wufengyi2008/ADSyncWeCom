from typing import Optional, Dict, Any
from database import Database

class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.db = Database()
            cls._instance._init_defaults()
        return cls._instance
    
    def _init_defaults(self) -> None:
        defaults = [
            ('wecom', 'corp_id', '', '企业微信CorpID'),
            ('wecom', 'corp_secret', '', '企业微信Secret'),
            ('wecom', 'wechat_bot_key', '', 'WeChatBot密钥'),
            ('ad', 'domain', '', 'AD域名'),
            ('ad', 'default_password', '', '用户默认密码'),
            ('ad', 'force_change_pwd', 'true', '是否强制改密码'),
            ('ad', 'system_accounts', 'Administrator,guest', '系统账号列表'),
            ('sync', 'sync_time', '02:00', '自动同步时间（HH:MM）'),
            ('sync', 'auto_sync', 'false', '启用自动同步'),
            ('sync', 'exclude_users', '', '排除的系统用户名（逗号分隔）'),
            ('sync', 'exclude_departments', '', '排除的部门名称（逗号分隔）'),
            ('sync', 'sync_departments', '', '允许同步的部门ID（逗号分隔）'),
            ('db', 'auto_backup', 'true', '自动备份'),
            ('db', 'backup_days', '7', '备份保留天数'),
            ('other', 'email_domain', '', '邮箱域名'),
        ]
        
        for category, key, value, description in defaults:
            existing = self.db.fetch_one(
                'SELECT id FROM config WHERE category = ? AND key = ?',
                (category, key)
            )
            if not existing:
                self.db.execute(
                    'INSERT INTO config (category, key, value, description) VALUES (?, ?, ?, ?)',
                    (category, key, value, description)
                )
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.db.fetch_one('SELECT category, value FROM config WHERE key = ?', (key,))
        if row:
            return row['value']
        return default
    
    def get_encrypted(self, key: str) -> Optional[str]:
        return self.get(key)
    
    def set(self, key: str, value: str) -> None:
        existing = self.db.fetch_one('SELECT category FROM config WHERE key = ?', (key,))
        category = existing['category'] if existing else 'other'
        self.set_by_category(category, key, value)
    
    def get_all_by_category(self, category: str) -> Dict[str, Dict[str, str]]:
        rows = self.db.fetch_all('SELECT key, value, description FROM config WHERE category = ?', (category,))
        result = {}
        for row in rows:
            result[row['key']] = {'value': row['value'], 'description': row['description']}
        return result
    
    def set_by_category(self, category: str, key: str, value: str, description: str = '') -> None:
        existing = self.db.fetch_one(
            'SELECT id FROM config WHERE category = ? AND key = ?',
            (category, key)
        )
        if existing:
            self.db.execute(
                'UPDATE config SET value = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ? AND key = ?',
                (value, description, category, key)
            )
        else:
            self.db.execute(
                'INSERT INTO config (category, key, value, description) VALUES (?, ?, ?, ?)',
                (category, key, value, description)
            )
    
    def get_wecom_config(self) -> Dict[str, Dict[str, str]]:
        return self.get_all_by_category('wecom')
    
    def get_ad_config(self) -> Dict[str, Dict[str, str]]:
        return self.get_all_by_category('ad')
    
    def get_sync_config(self) -> Dict[str, Dict[str, str]]:
        return self.get_all_by_category('sync')
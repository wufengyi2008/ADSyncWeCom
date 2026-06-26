import time
from typing import List, Dict, Optional, Any, Set, Tuple
from database import Database
from wecom_api import WeComAPI
from ad_manager import ADManager
from config_manager import ConfigManager
from email_service import EmailService
from password_utils import generate_secure_password, validate_password

class SyncService:
    STATUS_UNSYNCED = 0
    STATUS_SYNCED = 1
    STATUS_NEED_SYNC = 2
    STATUS_DISABLED = 3
    
    def __init__(self) -> None:
        self.db = Database()
        self.wecom_api = WeComAPI()
        self.ad_manager = ADManager()
        self.config = ConfigManager()
        self.email_service = EmailService()
    
    def _get_user_password(self) -> str:
        """
        根据密码模式获取用户密码
        - fixed: 使用固定密码
        - random: 生成随机密码
        """
        password_mode = self.config.get('password_mode', 'fixed')
        if password_mode == 'random':
            return generate_secure_password()
        else:
            default_password = self.config.get('default_password', '')
            if not validate_password(default_password):
                raise Exception('固定密码不符合安全要求（需包含大小写字母、数字、特殊符号，至少8位）')
            return default_password
    
    def check_ad_environment(self) -> Dict[str, Any]:
        return self.ad_manager.check_ad_environment()
    
    def sync_wecom_to_db(self, cancel_event=None, progress_callback=None) -> Dict[str, Any]:
        start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sync_count = 0
        error_count = 0
        
        try:
            if progress_callback:
                progress_callback(0, '正在获取部门列表...')
            
            departments = self.wecom_api.get_department_list()
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': 0}
            
            if progress_callback:
                progress_callback(10, f'获取到 {len(departments)} 个部门')
            
            users = self.wecom_api.get_all_users()
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': 0}
            
            if progress_callback:
                progress_callback(20, f'获取到 {len(users)} 个用户')
            
            user_depts = self.wecom_api.get_user_department_relation()
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': 0}
            
            exclude_users = self.config.get('exclude_users', '')
            exclude_user_list = [u.strip() for u in exclude_users.split(',') if u.strip()]
            
            exclude_depts = self.config.get('exclude_departments', '')
            exclude_dept_list = [d.strip() for d in exclude_depts.split(',') if d.strip()]
            
            total_items = len(departments) + len(users)
            processed_items = 0
            
            for dept in departments:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                if str(dept['id']) in exclude_dept_list:
                    continue
                
                existing = self.db.fetch_one(
                    'SELECT id, name, sync_status FROM departments WHERE wecom_id = ?',
                    (str(dept['id']),)
                )
                
                parent_id = str(dept.get('parentid', '0')) if dept.get('parentid') else None
                
                if existing:
                    if existing['name'] != dept['name']:
                        self.db.execute(
                            'UPDATE departments SET name = ?, parent_wecom_id = ?, sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (dept['name'], parent_id, self.STATUS_NEED_SYNC, str(dept['id']))
                        )
                        sync_count += 1
                else:
                    self.db.execute(
                        'INSERT INTO departments (wecom_id, name, parent_wecom_id, order_num, sync_status) VALUES (?, ?, ?, ?, ?)',
                        (str(dept['id']), dept['name'], parent_id, dept.get('order', 0), self.STATUS_UNSYNCED)
                    )
                    sync_count += 1
                
                processed_items += 1
                if progress_callback and total_items > 0:
                    progress = int(30 + (processed_items / total_items) * 40)
                    progress_callback(progress, f'同步部门: {dept["name"]}')
            
            if progress_callback:
                progress_callback(70, '正在同步用户...')
            
            for user in users:
                if user.get('userid') in exclude_user_list:
                    continue
                
                existing = self.db.fetch_one(
                    'SELECT id, name, position FROM users WHERE wecom_id = ?',
                    (user['userid'],)
                )
                
                email_domain = self.config.get('email_domain', '')
                email = f"{user['userid']}@{email_domain}" if email_domain else user.get('email', '')
                
                if existing:
                    needs_update = False
                    updates = []
                    
                    if existing['name'] != user['name']:
                        updates.append(('name', user['name']))
                        needs_update = True
                    if existing['position'] != user.get('position', ''):
                        updates.append(('position', user.get('position', '')))
                        needs_update = True
                    
                    if needs_update:
                        update_str = ', '.join(f'{k} = ?' for k, v in updates)
                        params = [v for k, v in updates] + [user['userid']]
                        self.db.execute(f'UPDATE users SET {update_str}, sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                                       [self.STATUS_NEED_SYNC] + params)
                        sync_count += 1
                else:
                    self.db.execute(
                        'INSERT INTO users (wecom_id, name, account, employee_id, position, email, mobile, sync_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (user['userid'], user['name'], user['userid'], user.get('employee_id', ''), 
                         user.get('position', ''), email, user.get('mobile', ''), self.STATUS_UNSYNCED)
                    )
                    sync_count += 1
                
                processed_items += 1
                if progress_callback and total_items > 0:
                    progress = int(30 + (processed_items / total_items) * 40)
                    progress_callback(progress, f'同步用户: {user["name"]}')
            
            if progress_callback:
                progress_callback(90, '正在更新用户部门关系...')
            
            self.db.execute('DELETE FROM user_department')
            for ud in user_depts:
                self.db.execute(
                    'INSERT INTO user_department (user_wecom_id, dept_wecom_id) VALUES (?, ?)',
                    (ud['user_id'], ud['dept_id'])
                )
            
            if progress_callback:
                progress_callback(100, '同步完成')
            
            status = 'SUCCESS'
            message = '企业微信同步完成'
        
        except Exception as e:
            status = 'FAILED'
            message = str(e)
            error_count += 1
        
        end_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.execute(
            'INSERT INTO sync_logs (sync_type, status, message, sync_count, error_count, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('WECOM_TO_DB', status, message, sync_count, error_count, start_time, end_time)
        )
        
        return {'status': status, 'message': message, 'sync_count': sync_count, 'error_count': error_count}
    
    def sync_dept_from_wecom(self, dept_wecom_id: str, cancel_event=None) -> Dict[str, Any]:
        start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sync_count = 0
        error_count = 0
        
        try:
            exclude_users = self.config.get('exclude_users', '')
            exclude_user_list = [u.strip() for u in exclude_users.split(',') if u.strip()]
            
            exclude_depts = self.config.get('exclude_departments', '')
            exclude_dept_list = [d.strip() for d in exclude_depts.split(',') if d.strip()]
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': 0}
            
            dept_info = self.wecom_api.get_department_info(dept_wecom_id)
            if dept_info:
                dept_name = dept_info.get('name', '')
                if not dept_name:
                    self.db.log_operation('SYNC_WARNING', 'WECOM_DEPT', f'部门 {dept_wecom_id} 缺少名称字段，已跳过')
                else:
                    existing = self.db.fetch_one(
                        'SELECT id, name, sync_status FROM departments WHERE wecom_id = ?',
                        (str(dept_wecom_id),)
                    )
                    
                    parent_id = str(dept_info.get('parentid', '0')) if dept_info.get('parentid') else None
                    
                    if existing:
                        if existing['name'] != dept_name:
                            self.db.execute(
                                'UPDATE departments SET name = ?, parent_wecom_id = ?, sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                                (dept_name, parent_id, self.STATUS_NEED_SYNC, str(dept_wecom_id))
                            )
                            sync_count += 1
                    else:
                        self.db.execute(
                            'INSERT INTO departments (wecom_id, name, parent_wecom_id, order_num, sync_status) VALUES (?, ?, ?, ?, ?)',
                            (str(dept_wecom_id), dept_name, parent_id, dept_info.get('order', 0), self.STATUS_UNSYNCED)
                        )
                        sync_count += 1
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': sync_count}
            
            simple_users = self.wecom_api.get_department_users(dept_wecom_id)
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': sync_count}
            
            for simple_user in simple_users:
                if simple_user.get('userid') in exclude_user_list:
                    continue
                
                # 获取用户详细信息（包含正确的职位信息）
                try:
                    user = self.wecom_api.get_user_detail(simple_user['userid'])
                    if user.get('errcode') != 0:
                        continue
                except Exception:
                    continue
                
                existing = self.db.fetch_one(
                    'SELECT id, name, position FROM users WHERE wecom_id = ?',
                    (user['userid'],)
                )
                
                email_domain = self.config.get('email_domain', '')
                email = f"{user['userid']}@{email_domain}" if email_domain else user.get('email', '')
                
                if existing:
                    needs_update = False
                    updates = []
                    
                    if existing['name'] != user.get('name', ''):
                        updates.append(('name', user.get('name', '')))
                        needs_update = True
                    if existing['position'] != user.get('position', ''):
                        updates.append(('position', user.get('position', '')))
                        needs_update = True
                    
                    if needs_update:
                        update_str = ', '.join(f'{k} = ?' for k, v in updates)
                        params = [v for k, v in updates] + [user['userid']]
                        self.db.execute(f'UPDATE users SET {update_str}, sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                                       [self.STATUS_NEED_SYNC] + params)
                        sync_count += 1
                else:
                    self.db.execute(
                        'INSERT INTO users (wecom_id, name, account, employee_id, position, email, mobile, sync_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (user['userid'], user.get('name', ''), user['userid'], user.get('employee_id', ''), 
                         user.get('position', ''), email, user.get('mobile', ''), self.STATUS_UNSYNCED)
                    )
                    sync_count += 1
                
                self.db.execute(
                    'INSERT OR REPLACE INTO user_department (user_wecom_id, dept_wecom_id) VALUES (?, ?)',
                    (user['userid'], str(dept_wecom_id))
                )
            
            status = 'SUCCESS'
            message = f'部门 {dept_wecom_id} 同步完成'
        
        except Exception as e:
            status = 'FAILED'
            message = str(e)
            error_count += 1
        
        end_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.execute(
            'INSERT INTO sync_logs (sync_type, status, message, sync_count, error_count, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('WECOM_DEPT_TO_DB', status, message, sync_count, error_count, start_time, end_time)
        )
        
        return {'status': status, 'message': message, 'sync_count': sync_count, 'error_count': error_count}
    
    def _generate_sam_account_name(self, name: str, employee_id: Optional[str] = None) -> str:
        existing_users = self.db.fetch_all('SELECT account FROM users WHERE name = ?', (name,))
        existing_accounts = {u['account'] for u in existing_users}
        
        base_name = self.ad_manager._clean_name(name)
        candidate = base_name
        
        if candidate not in existing_accounts:
            return candidate
        
        if employee_id:
            candidate = f"{base_name}{employee_id}"
            if candidate not in existing_accounts:
                return candidate
        
        counter = 1
        while candidate in existing_accounts:
            candidate = f"{base_name}{counter}"
            counter += 1
        
        return candidate
    
    def sync_db_to_ad(self, dept_wecom_ids: Optional[List[str]] = None, cancel_event=None, 
                      progress_callback=None, sync_users: bool = True) -> Dict[str, Any]:
        start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sync_count = 0
        error_count = 0
        
        try:
            domain = self.config.get('domain')
            force_change_pwd = self.config.get('force_change_pwd', 'true').lower() == 'true'
            password_mode = self.config.get('password_mode', 'fixed')
            
            if not domain:
                raise Exception('AD域名未配置')
            
            if password_mode == 'fixed':
                default_password = self.config.get('default_password', '')
                if not default_password:
                    raise Exception('AD配置未完成：固定密码未设置')
            
            base_dn = f"DC={domain.replace('.', ',DC=')}"
            
            exclude_users_str = self.config.get('exclude_users', '')
            exclude_users = {u.strip() for u in exclude_users_str.split(',') if u.strip()}
            
            exclude_depts_str = self.config.get('exclude_departments', '')
            exclude_dept_names = {d.strip() for d in exclude_depts_str.split(',') if d.strip()}
            
            departments = self.db.fetch_all('SELECT * FROM departments ORDER BY order_num')
            departments = [d for d in departments if d['name'] not in exclude_dept_names]
            
            allowed_depts_str = self.config.get('sync_departments', '')
            if allowed_depts_str:
                allowed_dept_ids = set(allowed_depts_str.split(','))
                departments = [d for d in departments if d['wecom_id'] in allowed_dept_ids]
            
            if dept_wecom_ids:
                dept_wecom_id_set = set(dept_wecom_ids)
                departments = [d for d in departments if d['wecom_id'] in dept_wecom_id_set]
            
            dept_dn_map = {}
            
            if progress_callback:
                if sync_users:
                    progress_callback(5, f'准备同步 {len(departments)} 个部门和用户')
                else:
                    progress_callback(5, f'准备同步 {len(departments)} 个部门')
            
            dept_name_map = {dept['wecom_id']: dept['name'] for dept in departments}
            
            for dept in departments:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                parent_id = dept['parent_wecom_id']
                parent_dn = dept_dn_map.get(parent_id, base_dn)
                
                if parent_id and parent_id not in dept_dn_map:
                    parent_dept = self.db.fetch_one('SELECT * FROM departments WHERE wecom_id = ?', (parent_id,))
                    if parent_dept:
                        parent_path = []
                        current_id = parent_id
                        while current_id:
                            p_dept = self.db.fetch_one('SELECT * FROM departments WHERE wecom_id = ?', (current_id,))
                            if not p_dept:
                                break
                            parent_path.insert(0, p_dept['name'])
                            current_id = p_dept['parent_wecom_id']
                        
                        parent_dn = base_dn
                        for p_name in parent_path:
                            parent_dn = f"OU={p_name},{parent_dn}"
                
                try:
                    result = self.ad_manager.create_ou(dept['name'], parent_dn)
                    dept_dn = f"OU={dept['name']},{parent_dn}"
                    dept_dn_map[dept['wecom_id']] = dept_dn
                    
                    if parent_id:
                        parent_group_name = self.ad_manager._clean_name(dept_name_map.get(parent_id, ''))
                        group_name = self.ad_manager._clean_name(dept['name'])
                        self.ad_manager.create_security_group(group_name, dept_dn, parent_group_name)
                    else:
                        group_name = self.ad_manager._clean_name(dept['name'])
                        self.ad_manager.create_security_group(group_name, dept_dn)
                    
                    self.db.execute(
                        'UPDATE departments SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                        (self.STATUS_SYNCED, dept['wecom_id'])
                    )
                    sync_count += 1
                except Exception as e:
                    error_count += 1
            
            if sync_users:
                total_depts = len(departments)
                users_by_dept = {}
                
                for dept in departments:
                    dept_users = self.db.fetch_all(
                        'SELECT * FROM users u JOIN user_department ud ON u.wecom_id = ud.user_wecom_id WHERE ud.dept_wecom_id = ?',
                        (dept['wecom_id'],)
                    )
                    users_by_dept[dept['wecom_id']] = dept_users
                
                total_users = sum(len(users) for users in users_by_dept.values())
                total_items = total_depts + total_users
                processed_items = total_depts
                
                for dept in departments:
                    dept_dn = dept_dn_map.get(dept['wecom_id'])
                    if not dept_dn:
                        continue
                    
                    users = users_by_dept.get(dept['wecom_id'], [])
                    group_name = self.ad_manager._clean_name(dept['name'])
                    
                    for user in users:
                        if cancel_event and cancel_event.is_set():
                            return {'success': True, 'message': '同步已取消', 'count': sync_count}
                        
                        if user['sync_status'] == self.STATUS_DISABLED:
                            continue
                        
                        if user['account'] in exclude_users:
                            continue
                        
                        sam_account_name = self._generate_sam_account_name(user['name'], user['employee_id'])
                        
                        try:
                            if progress_callback and total_items > 0:
                                progress_callback(int(35 + (processed_items / total_items) * 60), f'同步用户: {user["name"]}')
                            
                            email = user['email'] if user['email'] else f"{user['account']}@{self.config.get('email_domain', '')}"
                            
                            user_password = self._get_user_password()
                            
                            result = self.ad_manager.create_user(
                                user['name'],
                                sam_account_name,
                                dept_dn,
                                user_password,
                                email,
                                user['position'],
                                force_change_pwd
                            )
                            
                            if 'Created' in result:
                                self.ad_manager.add_user_to_group(sam_account_name, group_name)
                                self.db.execute(
                                    'UPDATE users SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                                    (self.STATUS_SYNCED, user['wecom_id'])
                                )
                                sync_count += 1
                                
                                if self.config.is_email_configured():
                                    try:
                                        self.email_service.send_account_notification(
                                            email,
                                            sam_account_name,
                                            user_password,
                                            domain
                                        )
                                    except Exception as e:
                                        self.db.log_operation('EMAIL_ERROR', 'SYNC', f'发送邮件通知失败: {user["name"]}, 错误: {str(e)}')
                            elif 'Exists' in result:
                                self.ad_manager.update_user(sam_account_name, user['name'], email, user['position'])
                                self.db.execute(
                                    'UPDATE users SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                                    (self.STATUS_SYNCED, user['wecom_id'])
                                )
                                sync_count += 1
                            
                            processed_items += 1
                        except Exception as e:
                            error_count += 1
            
            if progress_callback:
                progress_callback(100, '同步完成')
            
            status = 'SUCCESS'
            message = 'AD同步完成'
        
        except Exception as e:
            status = 'FAILED'
            message = str(e)
            error_count += 1
        
        end_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.execute(
            'INSERT INTO sync_logs (sync_type, status, message, sync_count, error_count, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('DB_TO_AD', status, message, sync_count, error_count, start_time, end_time)
        )
        
        return {'status': status, 'message': message, 'sync_count': sync_count, 'error_count': error_count}
    
    BUILTIN_SYSTEM_ACCOUNTS = {
        'administrator',
        'guest',
        'krbtgt',
        'defaultaccount',
        'wdagutilityaccount',
    }
    
    def sync_ad_status(self, cancel_event=None) -> Dict[str, Any]:
        start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sync_count = 0
        error_count = 0
        
        try:
            system_accounts_str = self.config.get('system_accounts', '')
            configured_accounts = {acc.strip().lower() for acc in system_accounts_str.split(',') if acc.strip()}
            system_accounts = self.BUILTIN_SYSTEM_ACCOUNTS.union(configured_accounts)
            
            self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'系统账号保护列表: {list(system_accounts)}')
            
            db_depts = self.db.fetch_all('SELECT wecom_id, name, sync_status FROM departments')
            self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'查询到 {len(db_depts)} 个数据库部门')
            
            ad_ous = self.ad_manager.get_all_ad_ous()
            ad_ou_names = {self.ad_manager._clean_name(ou['name']).lower() for ou in ad_ous}
            
            ad_groups = self.ad_manager.get_all_ad_groups()
            ad_group_names = {g['name'].lower() for g in ad_groups}
            
            for dept in db_depts:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                clean_dept_name = self.ad_manager._clean_name(dept['name']).lower()
                is_ou_in_ad = clean_dept_name in ad_ou_names
                is_group_in_ad = clean_dept_name in ad_group_names
                all_exists = is_ou_in_ad and is_group_in_ad
                
                dept_status = dept['sync_status']
                dept_wecom_id = dept['wecom_id']
                
                if dept_status == self.STATUS_UNSYNCED:
                    if all_exists:
                        self.db.execute(
                            'UPDATE departments SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (self.STATUS_SYNCED, dept_wecom_id)
                        )
                        sync_count += 1
                    else:
                        self.db.execute(
                            'UPDATE departments SET sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (self.STATUS_NEED_SYNC, dept_wecom_id)
                        )
                        sync_count += 1
                elif dept_status == self.STATUS_NEED_SYNC:
                    if all_exists:
                        self.db.execute(
                            'UPDATE departments SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (self.STATUS_SYNCED, dept_wecom_id)
                        )
                        sync_count += 1
                elif dept_status == self.STATUS_SYNCED:
                    if not all_exists:
                        self.db.execute(
                            'UPDATE departments SET sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (self.STATUS_NEED_SYNC, dept_wecom_id)
                        )
                        sync_count += 1
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': sync_count}
            
            db_users = self.db.fetch_all('SELECT wecom_id, name, account, sync_status FROM users WHERE sync_status != ?', (self.STATUS_DISABLED,))
            ad_users = self.ad_manager.get_all_ad_users()
            
            if cancel_event and cancel_event.is_set():
                return {'success': True, 'message': '同步已取消', 'count': sync_count}
            
            ad_sam_accounts = {user['sam_account_name'].lower() for user in ad_users}
            
            for ad_user in ad_users:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                ad_sam = ad_user['sam_account_name'].lower()
                if ad_sam in system_accounts:
                    continue
            
            db_accounts = {user['account'].lower() for user in db_users}
            db_names = {user['name'].lower() for user in db_users}
            
            for db_user in db_users:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                db_account = db_user['account'].lower()
                db_status = db_user['sync_status']
                
                is_in_ad = db_account in ad_sam_accounts or db_user['name'].lower() in ad_sam_accounts
                
                if not is_in_ad:
                    if db_status == self.STATUS_SYNCED:
                        self.db.execute(
                            'UPDATE users SET sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (self.STATUS_DISABLED, db_user['wecom_id'])
                        )
                        sync_count += 1
                    elif db_status == self.STATUS_UNSYNCED:
                        self.db.execute(
                            'UPDATE users SET sync_status = ?, updated_at = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                            (self.STATUS_NEED_SYNC, db_user['wecom_id'])
                        )
                        sync_count += 1
                elif db_status != self.STATUS_SYNCED:
                    self.db.execute(
                        'UPDATE users SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                        (self.STATUS_SYNCED, db_user['wecom_id'])
                    )
                    sync_count += 1
            
            status = 'SUCCESS'
            message = f'AD状态同步完成，处理了 {sync_count} 条记录'
        
        except Exception as e:
            status = 'FAILED'
            message = str(e)
            import traceback
            error_trace = traceback.format_exc()
            self.db.log_operation('SYNC_ERROR', 'AD_STATUS', f'AD状态同步异常: {str(e)}\n完整错误堆栈:\n{error_trace}')
            error_count += 1
        
        end_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.execute(
            'INSERT INTO sync_logs (sync_type, status, message, sync_count, error_count, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('AD_STATUS', status, message, sync_count, error_count, start_time, end_time)
        )
        
        return {'status': status, 'message': message, 'sync_count': sync_count, 'error_count': error_count}
    
    def sync_department_users_to_ad(self, dept_wecom_id: str, cancel_event=None) -> Dict[str, Any]:
        start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sync_count = 0
        error_count = 0
        
        try:
            dept = self.db.fetch_one('SELECT * FROM departments WHERE wecom_id = ?', (dept_wecom_id,))
            if not dept:
                raise Exception('部门不存在')
            
            self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'开始同步部门: {dept["name"]}(ID: {dept_wecom_id})')
            
            domain = self.config.get('domain')
            base_dn = f"DC={domain.replace('.', ',DC=')}"
            force_change_pwd = self.config.get('force_change_pwd', 'true').lower() == 'true'
            password_mode = self.config.get('password_mode', 'fixed')
            
            if password_mode == 'fixed':
                default_password = self.config.get('default_password', '')
                if not default_password:
                    raise Exception('AD配置未完成：固定密码未设置')
            
            parent_dn = base_dn
            if dept['parent_wecom_id']:
                parent_dept = self.db.fetch_one('SELECT name FROM departments WHERE wecom_id = ?', (dept['parent_wecom_id'],))
                if parent_dept:
                    parent_dn = f"OU={parent_dept['name']},{base_dn}"
            
            dept_dn = f"OU={dept['name']},{parent_dn}"
            
            self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'创建部门OU: {dept_dn}')
            self.ad_manager.create_ou(dept['name'], parent_dn)
            
            group_name = self.ad_manager._clean_name(dept['name'])
            self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'创建安全组: {group_name} 在 {dept_dn}')
            self.ad_manager.create_security_group(group_name, dept_dn)
            
            users = self.db.fetch_all(
                'SELECT * FROM users u JOIN user_department ud ON u.wecom_id = ud.user_wecom_id WHERE ud.dept_wecom_id = ?',
                (dept_wecom_id,)
            )
            
            self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'该部门有 {len(users)} 个用户需要同步')
            
            for user in users:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                sam_account_name = self._generate_sam_account_name(user['name'], user['employee_id'])
                email = user['email'] if user['email'] else f"{user['account']}@{self.config.get('email_domain', '')}"
                
                try:
                    self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'创建AD用户: {user["name"]}, SAM={sam_account_name}, DN={dept_dn}')
                    
                    user_password = self._get_user_password()
                    
                    result = self.ad_manager.create_user(
                        user['name'],
                        sam_account_name,
                        dept_dn,
                        user_password,
                        email,
                        user['position'],
                        force_change_pwd
                    )
                    
                    self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'AD创建用户结果: {result}')
                    
                    if 'Created' in result:
                        self.db.log_operation('SYNC_DEBUG', 'DEPT_USERS', f'用户 {sam_account_name} 已添加到组 {group_name}')
                        self.ad_manager.add_user_to_group(sam_account_name, group_name)
                        
                        if self.config.is_email_configured():
                            try:
                                self.email_service.send_account_notification(
                                    email,
                                    sam_account_name,
                                    user_password,
                                    domain
                                )
                            except Exception as e:
                                self.db.log_operation('EMAIL_ERROR', 'DEPT_USERS', f'发送邮件通知失败: {user["name"]}, 错误: {str(e)}')
                    
                    self.db.execute(
                        'UPDATE users SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                        (self.STATUS_SYNCED, user['wecom_id'])
                    )
                    sync_count += 1
                except Exception as e:
                    self.db.log_operation('SYNC_ERROR', 'DEPT_USERS', f'同步用户 {user["name"]} 失败: {str(e)}')
                    error_count += 1
            
            self.db.execute(
                'UPDATE departments SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                (self.STATUS_SYNCED, dept_wecom_id)
            )
            
            status = 'SUCCESS'
            message = f'部门用户同步完成，成功 {sync_count} 个，失败 {error_count} 个'
        
        except Exception as e:
            status = 'FAILED'
            message = str(e)
            self.db.log_operation('SYNC_ERROR', 'DEPT_USERS', f'部门用户同步异常: {str(e)}')
            error_count += 1
        
        end_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.execute(
            'INSERT INTO sync_logs (sync_type, status, message, sync_count, error_count, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('DEPT_USERS_TO_AD', status, message, sync_count, error_count, start_time, end_time)
        )
        
        return {'status': status, 'message': message, 'sync_count': sync_count, 'error_count': error_count}
    
    def sync_selected_users_to_ad(self, user_wecom_ids: List[str], cancel_event=None) -> Dict[str, Any]:
        start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sync_count = 0
        error_count = 0
        
        try:
            force_change_pwd = self.config.get('force_change_pwd', 'true').lower() == 'true'
            password_mode = self.config.get('password_mode', 'fixed')
            
            if password_mode == 'fixed':
                default_password = self.config.get('default_password', '')
                if not default_password:
                    raise Exception('AD配置未完成：固定密码未设置')
            
            self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'准备同步 {len(user_wecom_ids)} 个用户')
            
            for user_id in user_wecom_ids:
                if cancel_event and cancel_event.is_set():
                    return {'success': True, 'message': '同步已取消', 'count': sync_count}
                
                user = self.db.fetch_one('SELECT * FROM users WHERE wecom_id = ?', (user_id,))
                if not user:
                    self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'用户 {user_id} 在数据库中不存在')
                    continue
                
                self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'准备同步用户: {user["name"]}({user["account"]})')
                
                dept_relation = self.db.fetch_one('SELECT dept_wecom_id FROM user_department WHERE user_wecom_id = ?', (user_id,))
                if not dept_relation:
                    self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'用户 {user["name"]} 没有部门关系，跳过')
                    continue
                
                dept = self.db.fetch_one('SELECT * FROM departments WHERE wecom_id = ?', (dept_relation['dept_wecom_id'],))
                if not dept:
                    self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'部门 {dept_relation["dept_wecom_id"]} 不存在，跳过')
                    continue
                
                ou_exists, actual_ou_dn = self.ad_manager.check_ou_exists(dept['name'])
                if not ou_exists:
                    self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'部门OU不存在: {dept["name"]}，请先执行部门同步')
                    self.db.execute(
                        'UPDATE users SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                        (self.STATUS_NEED_SYNC, user_id)
                    )
                    continue
                
                dept_dn = actual_ou_dn
                
                sam_account_name = self._generate_sam_account_name(user['name'], user['employee_id'])
                email = user['email'] if user['email'] else f"{user['account']}@{self.config.get('email_domain', '')}"
                
                try:
                    user_password = self._get_user_password()
                    
                    result = self.ad_manager.create_user(
                        user['name'],
                        sam_account_name,
                        dept_dn,
                        user_password,
                        email,
                        user['position'],
                        force_change_pwd
                    )
                    
                    self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'AD创建用户结果: {result}')
                    
                    if 'Created' in result:
                        group_name = self.ad_manager._clean_name(dept['name'])
                        self.ad_manager.add_user_to_group(sam_account_name, group_name)
                        self.db.log_operation('SYNC_DEBUG', 'SELECTED_USERS', f'用户 {sam_account_name} 已添加到组 {group_name}')
                        
                        if self.config.is_email_configured():
                            try:
                                self.email_service.send_account_notification(
                                    email,
                                    sam_account_name,
                                    user_password,
                                    self.config.get('domain', '')
                                )
                            except Exception as e:
                                self.db.log_operation('EMAIL_ERROR', 'SELECTED_USERS', f'发送邮件通知失败: {user["name"]}, 错误: {str(e)}')
                    
                    self.db.execute(
                        'UPDATE users SET sync_status = ?, sync_time = CURRENT_TIMESTAMP WHERE wecom_id = ?',
                        (self.STATUS_SYNCED, user_id)
                    )
                    sync_count += 1
                except Exception as e:
                    self.db.log_operation('SYNC_ERROR', 'SELECTED_USERS', f'同步用户 {user["name"]} 失败: {str(e)}')
                    error_count += 1
            
            status = 'SUCCESS'
            message = f'选中用户同步完成，成功 {sync_count} 个，失败 {error_count} 个'
        
        except Exception as e:
            status = 'FAILED'
            message = str(e)
            self.db.log_operation('SYNC_ERROR', 'SELECTED_USERS', f'选中用户同步异常: {str(e)}')
            error_count += 1
        
        end_time = time.strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.execute(
            'INSERT INTO sync_logs (sync_type, status, message, sync_count, error_count, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ('SELECTED_USERS_TO_AD', status, message, sync_count, error_count, start_time, end_time)
        )
        
        return {'status': status, 'message': message, 'sync_count': sync_count, 'error_count': error_count}
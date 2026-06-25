import time
import threading
import base64
import json
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from database import Database
from hardware_info import HardwareInfo

class AuthExpiredError(Exception):
    pass

class AuthInvalidError(Exception):
    pass

class NetworkUnavailableError(Exception):
    pass

class SerialNumberMismatchError(Exception):
    pass

class AuthManager:
    NTP_SERVERS = [
        'ntp.ntsc.ac.cn',
        'time.windows.com', 
        'pool.ntp.org'
    ]
    
    def __init__(self):
        self.db = Database()
        self._auth_check_thread = None
        self._stop_event = threading.Event()
        self._hardware_info = HardwareInfo()
    
    def get_network_time(self):
        try:
            import ntplib
            client = ntplib.NTPClient()
            
            for server in self.NTP_SERVERS:
                try:
                    response = client.request(server, version=3, timeout=5)
                    return datetime.fromtimestamp(response.tx_time)
                except:
                    continue
            
            raise NetworkUnavailableError('所有NTP服务器都不可达，请检查网络连接')
        except ImportError:
            return datetime.now()
    
    def _derive_key(self, password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))
    
    def get_serial_number(self):
        try:
            serial, _ = self._hardware_info.generate_serial_number()
            return serial
        except Exception as e:
            return None
    
    def verify_auth_code(self, code):
        try:
            decoded = base64.b64decode(code)
            
            salt = decoded[:16]
            iv = decoded[16:32]
            tag = decoded[-16:]
            ciphertext = decoded[32:-16]
            
            password = self._get_internal_password()
            key = self._derive_key(password, salt)
            
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            decryptor.authenticate_additional_data(b'')
            payload = decryptor.update(ciphertext) + decryptor.finalize_with_tag(tag)
            
            data = json.loads(payload.decode('utf-8'))
            
            return {
                'first_auth_time': data['first_auth_time'],
                'duration_days': data['duration_days'],
                'serial_number': data.get('serial_number', None)
            }
        except Exception as e:
            raise AuthInvalidError('授权码无效')
    
    def _get_internal_password(self):
        return 'wecom_ad_sync_internal_key_2026'
    
    def is_authorized(self):
        auth_record = self.db.fetch_one('SELECT * FROM auth ORDER BY id DESC LIMIT 1')
        
        if not auth_record:
            return False
        
        try:
            try:
                network_time = self.get_network_time()
            except NetworkUnavailableError:
                network_time = datetime.now()
            
            first_auth_time = datetime.fromisoformat(auth_record['first_auth_time'])
            duration_days = auth_record['duration_days']
            
            expire_time = first_auth_time + timedelta(days=duration_days)
            
            if network_time > expire_time:
                return False
            
            stored_serial = auth_record['serial_number'] if 'serial_number' in auth_record.keys() else None
            if stored_serial:
                current_serial = self.get_serial_number()
                if current_serial != stored_serial:
                    return False
            
            return True
        except Exception as e:
            return False
    
    def activate(self, code):
        auth_data = self.verify_auth_code(code)
        
        first_auth_time = datetime.fromisoformat(auth_data['first_auth_time'])
        duration_days = auth_data['duration_days']
        auth_serial_number = auth_data.get('serial_number')
        
        network_time = self.get_network_time()
        expire_time = first_auth_time + timedelta(days=duration_days)
        
        if network_time > expire_time:
            raise AuthExpiredError('授权码已过期')
        
        current_serial = self.get_serial_number()
        
        if auth_serial_number:
            if current_serial != auth_serial_number:
                raise SerialNumberMismatchError('序列号不匹配，请使用正确的授权码')
        else:
            auth_serial_number = current_serial
        
        self.db.execute(
            'INSERT INTO auth (first_auth_time, duration_days, auth_code, verified, serial_number) VALUES (?, ?, ?, ?, ?)',
            (auth_data['first_auth_time'], duration_days, code, 1, auth_serial_number)
        )
        
        return True
    
    def get_remaining_days(self):
        auth_info = self.get_auth_info()
        if not auth_info:
            return 0
        return auth_info.get('remaining_days', 0)
    
    def get_auth_info(self):
        auth_record = self.db.fetch_one('SELECT * FROM auth ORDER BY id DESC LIMIT 1')
        
        if not auth_record:
            return None
        
        try:
            try:
                network_time = self.get_network_time()
            except NetworkUnavailableError:
                network_time = datetime.now()
            
            first_auth_time = datetime.fromisoformat(auth_record['first_auth_time'])
            duration_days = auth_record['duration_days']
            expire_time = first_auth_time + timedelta(days=duration_days)
            
            remaining_delta = expire_time - network_time
            total_seconds = int(remaining_delta.total_seconds())
            
            if total_seconds <= 0:
                remaining_days = 0
                remaining_hours = 0
            else:
                remaining_days = total_seconds // (24 * 3600)
                remaining_hours = (total_seconds % (24 * 3600)) // 3600
                if remaining_days == 0 and remaining_hours == 0 and total_seconds > 0:
                    remaining_hours = 1
            
            serial_number = auth_record['serial_number'] if 'serial_number' in auth_record.keys() else None
            
            return {
                'authorized': True,
                'first_auth_time': first_auth_time,
                'expire_time': expire_time,
                'duration_days': duration_days,
                'remaining_days': max(0, remaining_days),
                'remaining_hours': max(0, remaining_hours),
                'remaining_total_hours': max(0, total_seconds // 3600),
                'serial_number': serial_number
            }
        except Exception as e:
            return None
    
    def _periodic_check(self, callback=None):
        while not self._stop_event.is_set():
            if self._stop_event.wait(24 * 60 * 60):
                break
            
            if not self.is_authorized():
                if callback:
                    callback()
                break
    
    def start_periodic_check(self, callback=None):
        if self._auth_check_thread is None or not self._auth_check_thread.is_alive():
            self._stop_event.clear()
            self._auth_check_thread = threading.Thread(
                target=self._periodic_check,
                args=(callback,),
                daemon=True
            )
            self._auth_check_thread.start()
    
    def stop_periodic_check(self):
        self._stop_event.set()
        if self._auth_check_thread and self._auth_check_thread.is_alive():
            self._auth_check_thread.join(timeout=5)
        self._auth_check_thread = None
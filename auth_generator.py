import sys
import time
import base64
import json
from datetime import datetime
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:
    print("tkinter not available, running in CLI mode")
    tk = None

class AuthCodeGenerator:
    INTERNAL_PASSWORD = 'wecom_ad_sync_internal_key_2026'
    
    def _derive_key(self, password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))
    
    def generate(self, duration_days, password=None):
        if password is None:
            password = self.INTERNAL_PASSWORD
        try:
            import ntplib
            client = ntplib.NTPClient()
            ntp_servers = ['ntp.ntsc.ac.cn', 'time.windows.com', 'pool.ntp.org']
            
            for server in ntp_servers:
                try:
                    response = client.request(server, version=3, timeout=5)
                    current_time = datetime.fromtimestamp(response.tx_time)
                    break
                except:
                    continue
            else:
                current_time = datetime.now()
        except ImportError:
            current_time = datetime.now()
        
        first_auth_time = current_time.isoformat()
        
        payload = json.dumps({
            'first_auth_time': first_auth_time,
            'duration_days': duration_days
        }).encode('utf-8')
        
        salt = bytes([int(time.time()) % 256 for _ in range(16)])
        iv = bytes([int(time.time() * 1000) % 256 for _ in range(16)])
        
        key = self._derive_key(password, salt)
        
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(b'')
        
        ciphertext = encryptor.update(payload) + encryptor.finalize()
        tag = encryptor.tag
        
        encoded = base64.b64encode(salt + iv + ciphertext + tag).decode('utf-8')
        
        return encoded, first_auth_time

class GUIGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("授权码生成器")
        self.root.geometry("400x300")
        
        self.generator = AuthCodeGenerator()
        
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="授权天数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.duration_entry = ttk.Entry(main_frame, width=20)
        self.duration_entry.grid(row=0, column=1, pady=5)
        self.duration_entry.insert(0, "365")
        
        generate_btn = ttk.Button(main_frame, text="生成授权码", command=self.generate)
        generate_btn.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Label(main_frame, text="授权码:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.result_text = tk.Text(main_frame, height=4, width=40)
        self.result_text.grid(row=3, column=0, columnspan=2, pady=5)
        
        copy_btn = ttk.Button(main_frame, text="复制授权码", command=self.copy_to_clipboard)
        copy_btn.grid(row=4, column=0, columnspan=2, pady=5)
        
        ttk.Label(main_frame, text="生效时间:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.time_label = ttk.Label(main_frame, text="")
        self.time_label.grid(row=5, column=1, pady=5)
    
    def generate(self):
        try:
            duration = int(self.duration_entry.get())
            
            code, first_time = self.generator.generate(duration, None)
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, code)
            self.time_label.config(text=first_time)
            
            messagebox.showinfo("成功", "授权码生成成功")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def copy_to_clipboard(self):
        try:
            code = self.result_text.get(1.0, tk.END).strip()
            if code:
                self.root.clipboard_clear()
                self.root.clipboard_append(code)
                messagebox.showinfo("成功", "授权码已复制到剪贴板")
            else:
                messagebox.showwarning("警告", "没有可复制的授权码")
        except Exception as e:
            messagebox.showerror("错误", str(e))

def main():
    if len(sys.argv) >= 2:
        duration = int(sys.argv[1])
        password = sys.argv[2] if len(sys.argv) >= 3 else None
        
        generator = AuthCodeGenerator()
        code, first_time = generator.generate(duration, password)
        
        print(f"授权码: {code}")
        print(f"生效时间: {first_time}")
    elif tk:
        root = tk.Tk()
        app = GUIGenerator(root)
        root.mainloop()
    else:
        print("用法: python auth_generator.py <天数> [密码]")
        sys.exit(1)

if __name__ == "__main__":
    main()

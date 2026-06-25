import sys
import tkinter as tk
from tkinter import messagebox, ttk

from auth import AuthManager, NetworkUnavailableError, AuthExpiredError, AuthInvalidError, SerialNumberMismatchError
from gui import MainWindow

def main():
    try:
        
        skip_auth = len(sys.argv) > 1 and sys.argv[1] == '--skip-auth'
        
        auth_manager = AuthManager()
        
        if not skip_auth:
            try:
                network_time = auth_manager.get_network_time()
            except NetworkUnavailableError as e:
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("网络错误", str(e))
                root.destroy()
                sys.exit(1)
            
            if not auth_manager.is_authorized():
                root = tk.Tk()
                root.withdraw()
                
                result = show_auth_dialog(root, auth_manager)
                
                if not result:
                    root.destroy()
                    sys.exit(0)
        
        root = tk.Tk()
        app = MainWindow(root)
        
        def on_auth_expired():
            messagebox.showerror("授权过期", "您的授权已过期，请联系管理员获取新的授权码")
            root.quit()
        
        auth_manager.start_periodic_check(callback=on_auth_expired)
        
        root.mainloop()
        
        auth_manager.stop_periodic_check()
        
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("启动错误", f"程序启动失败: {str(e)}")
        root.destroy()
        sys.exit(1)

def show_auth_dialog(parent, auth_manager):
    dialog = tk.Toplevel(parent)
    dialog.title("授权验证")
    dialog.geometry("450x220")
    dialog.grab_set()
    
    result = [False]
    
    serial_number = auth_manager.get_serial_number()
    
    ttk.Label(dialog, text="本机序列号:").pack(pady=5)
    
    serial_frame = ttk.Frame(dialog)
    serial_frame.pack(pady=5)
    
    serial_label = ttk.Label(serial_frame, text=serial_number if serial_number else "无法获取")
    serial_label.pack(side=tk.LEFT)
    
    def copy_serial():
        if serial_number:
            dialog.clipboard_clear()
            dialog.clipboard_append(serial_number)
    
    ttk.Button(serial_frame, text="📋", command=copy_serial, width=2).pack(side=tk.LEFT)
    
    ttk.Label(dialog, text="请输入授权码:").pack(pady=10)
    
    code_entry = ttk.Entry(dialog, width=60)
    code_entry.pack(pady=5)
    
    def on_ok():
        code = code_entry.get().strip()
        
        if not code:
            messagebox.showwarning("警告", "请输入授权码")
            return
        
        try:
            auth_manager.activate(code)
            result[0] = True
            dialog.destroy()
        except AuthInvalidError:
            messagebox.showerror("错误", "授权码无效")
        except AuthExpiredError:
            messagebox.showerror("错误", "授权码已过期")
        except SerialNumberMismatchError:
            messagebox.showerror("错误", "序列号不匹配，请使用正确的授权码")
        except NetworkUnavailableError:
            messagebox.showerror("错误", "网络不可达，无法验证授权码。请检查网络连接后重试。")
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def on_cancel():
        dialog.destroy()
    
    button_frame = ttk.Frame(dialog)
    button_frame.pack(pady=10)
    
    ttk.Button(button_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)
    
    dialog.wait_window()
    
    return result[0]

if __name__ == "__main__":
    main()

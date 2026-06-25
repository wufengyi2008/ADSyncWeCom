import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
from datetime import datetime
from database import Database
from config_manager import ConfigManager
from sync_service import SyncService
from scheduler import SyncScheduler

class ProgressDialog:
    def __init__(self, parent, title, message):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x120")
        self.dialog.minsize(350, 100)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self.progress_label = ttk.Label(self.dialog, text=message, style='Status.TLabel')
        self.progress_label.pack(pady=12)
        
        self.progress_bar = ttk.Progressbar(self.dialog, orient="horizontal", length=350, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=12, pady=8)
        self.progress_bar['value'] = 0
        
        self.dialog.update()
        self.center_window()
    
    def center_window(self):
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
    
    def set_message(self, message):
        self.progress_label.config(text=message)
        self.dialog.update()
    
    def set_progress(self, value):
        self.progress_bar['value'] = value
        self.dialog.update()
    
    def close(self):
        self.dialog.grab_release()
        self.dialog.destroy()

class MainWindow:
    STATUS_COLORS = {
        0: '#6C757D',  # 未同步 - 灰色
        1: '#198754',  # 已同步 - 绿色
        2: '#F59E0B',  # 需同步 - 橙色
        3: '#DC3545'   # 已禁用 - 红色
    }
    
    STATUS_LABELS = {
        0: '未同步',
        1: '已同步',
        2: '需同步',
        3: '已禁用'
    }
    
    def __init__(self, root):
        self.root = root
        self.root.title("企业微信-AD域同步工具")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        
        self._setup_styles()
        
        self.db = Database()
        self.config = ConfigManager()
        self.sync_service = SyncService()
        self.scheduler = SyncScheduler()
        
        self.selected_dept = None
        self.selected_users = []
        
        self.sync_lock = threading.Lock()
        self.sync_cancel_event = threading.Event()
        
        self._create_menu()
        self._create_panels()
        
        self.root.after(100, self._init_scheduler)
        
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
    
    def _on_close(self):
        self.scheduler.stop()
        self.root.destroy()
    
    def _init_scheduler(self):
        def delayed_init():
            auto_sync = self.config.get('auto_sync', 'false').lower() == 'true'
            self.scheduler.set_on_sync_complete_callback(self._on_auto_sync_complete)
            if auto_sync:
                self.scheduler.start()
            self.root.after(0, self._update_next_sync_display)
            self.root.after(0, self._schedule_next_sync_refresh)
        
        threading.Thread(target=delayed_init, daemon=True).start()
    
    def _on_auto_sync_complete(self):
        self.root.after(0, self._update_stats)
    
    def _schedule_next_sync_refresh(self):
        self._update_next_sync_display()
        self.root.after(60000, self._schedule_next_sync_refresh)
    
    def _setup_styles(self):
        style = ttk.Style()
        
        style.theme_use('clam')
        
        style.configure('Header.TLabel', font=('Microsoft YaHei', 12, 'bold'), foreground='#2C3E50')
        style.configure('Title.TLabel', font=('Microsoft YaHei', 10, 'bold'), foreground='#34495E')
        style.configure('Stat.TLabel', font=('Microsoft YaHei', 11, 'bold'))
        style.configure('Status.TLabel', font=('Microsoft YaHei', 9))
        
        style.configure('Action.TButton', padding=6, font=('Microsoft YaHei', 9))
        style.map('Action.TButton',
                  background=[('active', '#E8F5E9'), ('pressed', '#C8E6C9')],
                  foreground=[('active', '#2E7D32')])
        
        style.configure('Card.TFrame', background='#FFFFFF', relief='solid', borderwidth=1)
        style.configure('Panel.TFrame', background='#F8FAFC')
        
        style.configure('Treeview', font=('Microsoft YaHei', 9), rowheight=24)
        style.configure('Treeview.Heading', font=('Microsoft YaHei', 9, 'bold'), background='#E2E8F0')
        style.map('Treeview', foreground=[])
        style.map('Treeview', background=[('selected', '#1E90FF')])
        
        style.configure('StatusBar.TLabel', font=('Microsoft YaHei', 9), background='#E2E8F0')
    
    def _create_menu(self):
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)
        
        sync_menu = tk.Menu(menubar, tearoff=0)
        sync_menu.add_command(label="企微全量同步", command=self._sync_wecom)
        sync_menu.add_command(label="企微部门同步", command=self._sync_wecom_dept)
        sync_menu.add_command(label="AD状态同步", command=self._sync_ad_status)
        sync_menu.add_separator()
        sync_menu.add_command(label="AD全量同步", command=self._sync_all_to_ad)
        sync_menu.add_command(label="选中部门同步", command=self._sync_dept_to_ad)
        sync_menu.add_command(label="选中用户同步", command=self._sync_selected_users)
        menubar.add_cascade(label="同步", menu=sync_menu)
        
        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="企业微信配置", command=lambda: ConfigDialog(self.root, self.config, self.db, 0))
        config_menu.add_command(label="AD域配置", command=lambda: ConfigDialog(self.root, self.config, self.db, 1))
        config_menu.add_command(label="同步设置", command=lambda: ConfigDialog(self.root, self.config, self.db, 2))
        config_menu.add_command(label="数据库配置", command=lambda: ConfigDialog(self.root, self.config, self.db, 3))
        menubar.add_cascade(label="配置", menu=config_menu)
        
        log_menu = tk.Menu(menubar, tearoff=0)
        log_menu.add_command(label="同步日志", command=self._show_sync_logs)
        log_menu.add_command(label="操作日志", command=self._show_operation_logs)
        log_menu.add_separator()
        log_menu.add_command(label="导出日志", command=self._export_logs)
        menubar.add_cascade(label="日志", menu=log_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def _create_panels(self):
        main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        left_panel = ttk.Frame(main_frame, width=320, style='Panel.TFrame')
        main_frame.add(left_panel, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)
        
        self._create_local_sync_toolbar(left_panel)
        self._create_dept_tree(left_panel)
        
        right_panel = ttk.Frame(main_frame, width=780, style='Panel.TFrame')
        main_frame.add(right_panel, weight=3)
        
        right_panel.grid_rowconfigure(2, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        self._create_stats_panel(right_panel)
        self._create_ad_sync_toolbar(right_panel)
        self._create_user_panel(right_panel)
    
    def _create_stats_panel(self, parent):
        stats_frame = ttk.LabelFrame(parent, text="同步统计", style='Card.TFrame')
        stats_frame.grid(row=0, column=0, sticky=tk.W+tk.E, padx=8, pady=12)
        
        stats_row = ttk.Frame(stats_frame)
        stats_row.pack(fill=tk.X, padx=10, pady=4)
        
        self.stats_labels = {}
        stats = [
            ('部门', 'dept_total', '#2C3E50'),
            ('已同步', 'dept_synced', '#198754'),
            ('用户', 'user_total', '#2C3E50'),
            ('已同步', 'user_synced', '#198754'),
            ('未同步', 'user_unsynced', '#6C757D'),
            ('需同步', 'user_needsync', '#F59E0B'),
            ('已禁用', 'user_disabled', '#DC3545'),
        ]
        
        for i, (label_text, key, color) in enumerate(stats):
            ttk.Label(stats_row, text=label_text, font=('微软雅黑', 12)).pack(side=tk.LEFT, padx=(4 if i > 0 else 0), pady=1)
            self.stats_labels[key] = ttk.Label(stats_row, text='0', font=('微软雅黑', 12, 'bold'))
            self.stats_labels[key].config(foreground=color)
            self.stats_labels[key].pack(side=tk.LEFT, padx=2, pady=2)
            if i < len(stats) - 1:
                ttk.Label(stats_row, text='|', foreground='#E2E8F0', font=('微软雅黑', 12)).pack(side=tk.LEFT, padx=3)
        
        self._update_stats()
    
    def _create_local_sync_toolbar(self, parent):
        toolbar = ttk.LabelFrame(parent, text="本地同步", style='Card.TFrame')
        toolbar.grid(row=0, column=0, sticky=tk.W+tk.E, padx=8, pady=(8, 0))
        
        toolbar_row = ttk.Frame(toolbar)
        toolbar_row.pack(fill=tk.X, padx=8, pady=4)
        
        self.btn_wecom_full = ttk.Button(toolbar_row, text="企微全量同步", command=self._sync_wecom, style='Action.TButton', width=12)
        self.btn_wecom_full.pack(side=tk.LEFT, padx=2)
        self.btn_dept = ttk.Button(toolbar_row, text="企微部门同步", command=self._sync_wecom_dept, style='Action.TButton', width=12)
        self.btn_dept.pack(side=tk.LEFT, padx=2)
        self.btn_ad_status = ttk.Button(toolbar_row, text="AD状态同步", command=self._sync_ad_status, style='Action.TButton', width=12)
        self.btn_ad_status.pack(side=tk.LEFT, padx=2)
    
    def _create_ad_sync_toolbar(self, parent):
        toolbar = ttk.LabelFrame(parent, text="AD同步", style='Card.TFrame')
        toolbar.grid(row=1, column=0, sticky=tk.W+tk.E, padx=8, pady=(0, 8))
        
        toolbar_row = ttk.Frame(toolbar)
        toolbar_row.pack(fill=tk.X, padx=8, pady=4)
        
        self.btn_all_to_ad = ttk.Button(toolbar_row, text="AD全量同步", command=self._sync_all_to_ad, style='Action.TButton', width=12)
        self.btn_all_to_ad.pack(side=tk.LEFT, padx=3)
        self.btn_dept_to_ad = ttk.Button(toolbar_row, text="选中部门同步", command=self._sync_dept_to_ad, style='Action.TButton', width=12)
        self.btn_dept_to_ad.pack(side=tk.LEFT, padx=3)
        self.btn_user_to_ad = ttk.Button(toolbar_row, text="选中用户同步", command=self._sync_selected_users, style='Action.TButton', width=12)
        self.btn_user_to_ad.pack(side=tk.LEFT, padx=3)
        
        self.auto_sync_var = tk.BooleanVar()
        self.auto_sync_var.set(self.config.get('auto_sync', 'false').lower() == 'true')
        self.auto_sync_checkbox = ttk.Checkbutton(toolbar_row, text="启用自动同步", variable=self.auto_sync_var, command=self._toggle_auto_sync)
        self.auto_sync_checkbox.pack(side=tk.LEFT, padx=8)
        
        self.next_sync_label = ttk.Label(toolbar_row, text="", style='Status.TLabel')
        self.next_sync_label.pack(side=tk.LEFT, padx=4)
    
    def _set_sync_buttons_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.btn_wecom_full.config(state=state)
        self.btn_dept.config(state=state)
        self.btn_ad_status.config(state=state)
        self.btn_all_to_ad.config(state=state)
        self.btn_dept_to_ad.config(state=state)
        self.btn_user_to_ad.config(state=state)
    
    def _update_stats(self):
        dept_total = self.db.fetch_one('SELECT COUNT(*) FROM departments')['COUNT(*)']
        dept_synced = self.db.fetch_one('SELECT COUNT(*) FROM departments WHERE sync_status = 1')['COUNT(*)']
        
        user_total = self.db.fetch_one('SELECT COUNT(*) FROM users')['COUNT(*)']
        user_synced = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 1')['COUNT(*)']
        user_unsynced = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 0')['COUNT(*)']
        user_needsync = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 2')['COUNT(*)']
        user_disabled = self.db.fetch_one('SELECT COUNT(*) FROM users WHERE sync_status = 3')['COUNT(*)']
        
        self.stats_labels['dept_total'].config(text=str(dept_total))
        self.stats_labels['dept_synced'].config(text=str(dept_synced))
        self.stats_labels['user_total'].config(text=str(user_total))
        self.stats_labels['user_synced'].config(text=str(user_synced))
        self.stats_labels['user_unsynced'].config(text=str(user_unsynced))
        self.stats_labels['user_needsync'].config(text=str(user_needsync))
        self.stats_labels['user_disabled'].config(text=str(user_disabled))
    
    def _update_next_sync_display(self):
        if self.scheduler.is_running():
            next_sync = self.scheduler._get_next_sync_time()
            if next_sync:
                now = datetime.now()
                time_diff = (next_sync - now).total_seconds()
                hours = int(time_diff // 3600)
                minutes = int((time_diff % 3600) // 60)
                self.next_sync_label.config(text=f"下次同步: {next_sync.strftime('%m-%d %H:%M')} ({hours}小时{minutes}分钟后)")
            else:
                self.next_sync_label.config(text="下次同步: 计算中...")
        else:
            self.next_sync_label.config(text="自动同步未启用")
    
    def _on_config_changed(self, old_auto_sync, old_sync_time, new_auto_sync, new_sync_time):
        if old_sync_time != new_sync_time:
            if hasattr(self, 'sync_time_label'):
                self.sync_time_label.config(text=f"同步时间: {new_sync_time}")
        
        if old_auto_sync != new_auto_sync:
            if hasattr(self, 'auto_sync_var'):
                self.auto_sync_var.set(new_auto_sync)
        
        if self.scheduler.is_running():
            if old_sync_time != new_sync_time:
                self.scheduler._sync_time = new_sync_time
                self.scheduler._calculate_next_sync_time()
        
        self._update_next_sync_display()
    
    def _toggle_auto_sync(self):
        if hasattr(self, 'auto_sync_checkbox'):
            self.auto_sync_checkbox.config(state=tk.DISABLED)
        
        try:
            auto_sync = self.auto_sync_var.get()
            self.config.set_by_category('sync', 'auto_sync', str(auto_sync), '启用自动同步')
            
            if auto_sync:
                self.scheduler.start()
                messagebox.showinfo("提示", "自动同步已启用")
            else:
                self.scheduler.stop()
                messagebox.showinfo("提示", "自动同步已禁用")
            
            self._update_next_sync_display()
        except Exception as e:
            messagebox.showerror("错误", str(e))
        finally:
            if hasattr(self, 'auto_sync_checkbox'):
                self.auto_sync_checkbox.config(state=tk.NORMAL)
    
    def _sync_wecom_dept(self):
        if not self.selected_dept:
            messagebox.showwarning("警告", "请选择部门")
            return
        
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        dept_info = self.db.fetch_one('SELECT name FROM departments WHERE wecom_id = ?', (self.selected_dept,))
        dept_name = dept_info['name'] if dept_info else self.selected_dept
        
        progress_dialog = ProgressDialog(self.root, "企业微信部门同步", f"正在同步部门「{dept_name}」...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                result = self.sync_service.sync_dept_from_wecom(self.selected_dept, cancel_event=self.sync_cancel_event)
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _create_dept_tree(self, parent):
        dept_frame = ttk.LabelFrame(parent, text="部门结构", style='Card.TFrame')
        dept_frame.grid(row=1, column=0, sticky=tk.W+tk.E+tk.N+tk.S, padx=8, pady=8)
        
        self.dept_tree = ttk.Treeview(dept_frame, columns=('status',), show='tree headings')
        self.dept_tree.heading('#0', text='部门名称')
        self.dept_tree.heading('status', text='状态')
        self.dept_tree.column('status', width=70)
        
        scrollbar = ttk.Scrollbar(dept_frame, orient="vertical", command=self.dept_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.dept_tree.configure(yscrollcommand=scrollbar.set)
        self.dept_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        self.dept_tree.bind('<<TreeviewSelect>>', self._on_dept_select)
        
        self.dept_tree.tag_configure('0', foreground='#6C757D')
        self.dept_tree.tag_configure('1', foreground='#198754')
        self.dept_tree.tag_configure('2', foreground='#F59E0B')
        self.dept_tree.tag_configure('3', foreground='#DC3545')
        
        self._load_dept_tree()
    
    def _load_dept_tree(self):
        for item in self.dept_tree.get_children():
            self.dept_tree.delete(item)
        
        depts = self.db.fetch_all('SELECT * FROM departments ORDER BY order_num')
        dept_dict = {d['wecom_id']: d for d in depts}
        
        root_depts = [d for d in depts if not d['parent_wecom_id'] or d['parent_wecom_id'] == '0']
        
        for dept in root_depts:
            self._add_dept_node(dept, dept_dict, '')
    
    def _add_dept_node(self, dept, dept_dict, parent):
        status = dept['sync_status']
        status_label = self.STATUS_LABELS.get(status, '未知')
        
        node = self.dept_tree.insert(parent, 'end', text=dept['name'], values=(status_label,), tags=(str(status),))
        
        children = [d for d in dept_dict.values() if d['parent_wecom_id'] == dept['wecom_id']]
        for child in children:
            self._add_dept_node(child, dept_dict, node)
    
    def _create_user_panel(self, parent):
        user_frame = ttk.LabelFrame(parent, text="用户列表", style='Card.TFrame')
        user_frame.grid(row=2, column=0, sticky=tk.W+tk.E+tk.N+tk.S, padx=8, pady=(0, 8))
        parent.grid_rowconfigure(2, weight=1)
        
        tree_frame = ttk.Frame(user_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        
        self.user_tree = ttk.Treeview(tree_frame, columns=('name', 'account', 'position', 'email', 'status'), show='headings')
        self.user_tree.heading('name', text='姓名')
        self.user_tree.heading('account', text='账号')
        self.user_tree.heading('position', text='职位')
        self.user_tree.heading('email', text='邮箱')
        self.user_tree.heading('status', text='状态')
        self.user_tree.column('name', width=100)
        self.user_tree.column('account', width=120)
        self.user_tree.column('position', width=120)
        self.user_tree.column('email', width=200)
        self.user_tree.column('status', width=80)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.user_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.user_tree.configure(yscrollcommand=scrollbar.set)
        self.user_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        self.user_tree.bind('<<TreeviewSelect>>', self._on_user_select)
    
    def _load_users(self, dept_wecom_id=None):
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        if dept_wecom_id:
            users = self.db.fetch_all(
                'SELECT u.* FROM users u JOIN user_department ud ON u.wecom_id = ud.user_wecom_id WHERE ud.dept_wecom_id = ?',
                (dept_wecom_id,)
            )
        else:
            users = self.db.fetch_all('SELECT * FROM users')
        
        for user in users:
            status = user['sync_status']
            color = self.STATUS_COLORS.get(status, '#808080')
            status_label = self.STATUS_LABELS.get(status, '未知')
            tag_name = f'row_{status}'
            
            self.user_tree.tag_configure(tag_name, foreground=color)
            self.user_tree.insert('', 'end', values=(
                user['name'],
                user['account'],
                user['position'] or '',
                user['email'] or '',
                status_label
            ), tags=(tag_name,))
    
    def _on_dept_select(self, event):
        selection = self.dept_tree.selection()
        if selection:
            item = self.dept_tree.item(selection[0])
            depts = self.db.fetch_all('SELECT * FROM departments WHERE name = ?', (item['text'],))
            if depts:
                self.selected_dept = depts[0]['wecom_id']
                self._load_users(self.selected_dept)
            else:
                self.selected_dept = None
                self._load_users()
        else:
            self.selected_dept = None
            self._load_users()
    
    def _on_user_select(self, event):
        selection = self.user_tree.selection()
        self.selected_users = []
        for item in selection:
            values = self.user_tree.item(item)['values']
            user = self.db.fetch_one('SELECT wecom_id FROM users WHERE account = ?', (values[1],))
            if user:
                self.selected_users.append(user['wecom_id'])
    
    def _cancel_sync(self):
        self.sync_cancel_event.set()

    def _enable_buttons_safe(self, enabled):
        self.root.after(0, lambda: self._set_sync_buttons_enabled(enabled))
    
    def _sync_wecom(self):
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        progress_dialog = ProgressDialog(self.root, "企业微信同步", "正在同步企业微信数据...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                def progress_callback(progress, message):
                    progress_dialog.set_message(message)
                    progress_dialog.set_progress(progress)
                
                result = self.sync_service.sync_wecom_to_db(
                    cancel_event=self.sync_cancel_event,
                    progress_callback=progress_callback
                )
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_dept_tree()
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _sync_all_to_ad(self):
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        progress_dialog = ProgressDialog(self.root, "AD全量同步", "正在检测AD环境...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                ad_check = self.sync_service.check_ad_environment()
                if not ad_check['success']:
                    raise Exception(ad_check['message'])
                
                def progress_callback(progress, message):
                    progress_dialog.set_message(message)
                    progress_dialog.set_progress(progress)
                
                progress_dialog.set_message("正在同步到AD...")
                progress_dialog.set_progress(10)
                
                result = self.sync_service.sync_db_to_ad(
                    cancel_event=self.sync_cancel_event,
                    progress_callback=progress_callback
                )
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_dept_tree()
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _sync_ad_status(self):
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        progress_dialog = ProgressDialog(self.root, "AD状态同步", "正在检测AD环境...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                ad_check = self.sync_service.check_ad_environment()
                if not ad_check['success']:
                    raise Exception(ad_check['message'])
                
                progress_dialog.set_message("正在同步AD状态...")
                progress_dialog.set_progress(10)
                
                result = self.sync_service.sync_ad_status(cancel_event=self.sync_cancel_event)
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_dept_tree()
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"状态同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _sync_dept_to_ad(self):
        if not self.selected_dept:
            messagebox.showwarning("警告", "请选择部门")
            return
        
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        progress_dialog = ProgressDialog(self.root, "部门同步到AD", "正在检测AD环境...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                ad_check = self.sync_service.check_ad_environment()
                if not ad_check['success']:
                    raise Exception(ad_check['message'])
                
                progress_dialog.set_message("正在同步部门到AD...")
                progress_dialog.set_progress(10)
                
                result = self.sync_service.sync_db_to_ad([self.selected_dept], cancel_event=self.sync_cancel_event, sync_users=False)
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_dept_tree()
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _sync_dept_users(self):
        if not self.selected_dept:
            messagebox.showwarning("警告", "请选择部门")
            return
        
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        progress_dialog = ProgressDialog(self.root, "部门用户同步", "正在检测AD环境...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                ad_check = self.sync_service.check_ad_environment()
                if not ad_check['success']:
                    raise Exception(ad_check['message'])
                
                progress_dialog.set_message("正在同步部门用户...")
                progress_dialog.set_progress(10)
                
                result = self.sync_service.sync_department_users_to_ad(self.selected_dept, cancel_event=self.sync_cancel_event)
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _sync_selected_users(self):
        if not self.selected_users:
            messagebox.showwarning("警告", "请选择用户")
            return
        
        if not self.sync_lock.acquire(blocking=False):
            messagebox.showwarning("提示", "正在同步中，请等待完成")
            return
        
        self._set_sync_buttons_enabled(False)
        
        progress_dialog = ProgressDialog(self.root, "用户同步", "正在检测AD环境...")
        
        def sync():
            try:
                self.sync_cancel_event.clear()
                
                ad_check = self.sync_service.check_ad_environment()
                if not ad_check['success']:
                    raise Exception(ad_check['message'])
                
                progress_dialog.set_message("正在同步选中用户...")
                progress_dialog.set_progress(10)
                
                result = self.sync_service.sync_selected_users_to_ad(self.selected_users, cancel_event=self.sync_cancel_event)
                
                if self.sync_cancel_event.is_set():
                    progress_dialog.close()
                    self.root.after(0, lambda: messagebox.showinfo("提示", "同步已取消"))
                else:
                    progress_dialog.set_message("同步完成")
                    progress_dialog.set_progress(100)
                    time.sleep(0.5)
                    self._load_users(self.selected_dept)
                    self._update_stats()
                    progress_dialog.close()
                    self.root.after(0, lambda msg=result['message']: messagebox.showinfo("提示", f"同步完成: {msg}"))
            except Exception as e:
                progress_dialog.close()
                self.root.after(0, lambda msg=str(e): messagebox.showerror("错误", msg))
            finally:
                self.sync_cancel_event.clear()
                self.sync_lock.release()
                self._enable_buttons_safe(True)
        
        threading.Thread(target=sync, daemon=True).start()
    
    def _refresh_users(self):
        self._load_users(self.selected_dept)
    
    def _show_config(self):
        ConfigDialog(self.root, self.config, self.db)
    
    def _show_about(self):
        from auth import AuthManager
        auth_manager = AuthManager()
        auth_info = auth_manager.get_auth_info()
        serial_number = auth_manager.get_serial_number()
        
        if auth_info and auth_info.get('authorized'):
            expire_time = auth_info['expire_time']
            expire_str = expire_time.strftime('%Y-%m-%d %H:%M:%S')
            remaining_days = auth_info['remaining_days']
            remaining_hours = auth_info['remaining_hours']
            
            if remaining_days > 0:
                remaining_str = f"剩余 {remaining_days} 天"
            else:
                total_hours = auth_info['remaining_total_hours']
                remaining_str = f"剩余 {total_hours} 小时"
            
            auth_status = f"已授权到 {expire_str}（{remaining_str}）"
        else:
            auth_status = "未授权"
        
        serial_display = serial_number if serial_number else "无法获取"
        
        about_text = f"""企业微信-AD域同步工具
版本: 1.0

序列号: {serial_display}
授权状态: {auth_status}
联系方式: 13539742634

功能说明:
- 从企业微信同步通讯录到本地数据库
- 从本地数据库同步用户到AD域
- 支持手动和自动同步模式
- 支持部门和用户同步状态管理"""
        
        messagebox.showinfo("关于", about_text)
    
    def _export_logs(self):
        ExportLogDialog(self.root, self.db)
    
    def _show_sync_logs(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("同步日志")
        dialog.geometry("1000x600")
        dialog.minsize(900, 500)
        
        logs = self.db.fetch_all('SELECT * FROM sync_logs ORDER BY created_at DESC LIMIT 100')
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        columns = ('id', 'sync_type', 'status', 'message', 'sync_count', 'error_count', 'start_time', 'end_time')
        tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')
        
        tree.heading('id', text='ID')
        tree.heading('sync_type', text='同步类型')
        tree.heading('status', text='状态')
        tree.heading('message', text='消息')
        tree.heading('sync_count', text='同步数')
        tree.heading('error_count', text='错误数')
        tree.heading('start_time', text='开始时间')
        tree.heading('end_time', text='结束时间')
        
        tree.column('id', width=50, stretch=False)
        tree.column('sync_type', width=100, stretch=False)
        tree.column('status', width=60, stretch=False)
        tree.column('message', width=300)
        tree.column('sync_count', width=60, stretch=False)
        tree.column('error_count', width=60, stretch=False)
        tree.column('start_time', width=130, stretch=False)
        tree.column('end_time', width=130, stretch=False)
        
        for log in logs:
            message = log['message'] if log['message'] else ''
            tree.insert('', 'end', values=(
                log['id'],
                log['sync_type'],
                log['status'],
                message[:200] + '...' if len(message) > 200 else message,
                log['sync_count'],
                log['error_count'],
                log['start_time'],
                log['end_time']
            ))
        
        v_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        tree.configure(xscrollcommand=h_scrollbar.set)
        
        tree.pack(fill=tk.BOTH, expand=True)
        
        detail_frame = ttk.LabelFrame(dialog, text="详细信息")
        detail_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
        
        detail_text = tk.Text(detail_frame, height=12, wrap=tk.WORD)
        detail_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        def show_detail(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                values = item['values']
                log_id = values[0]
                log = self.db.fetch_one('SELECT * FROM sync_logs WHERE id = ?', (log_id,))
                if log:
                    detail_text.delete('1.0', tk.END)
                    detail_text.insert('1.0', f"ID: {log['id']}\n同步类型: {log['sync_type']}\n状态: {log['status']}\n消息: {log['message']}\n同步数: {log['sync_count']}\n错误数: {log['error_count']}\n开始时间: {log['start_time']}\n结束时间: {log['end_time']}\n创建时间: {log['created_at']}")
        
        tree.bind('<<TreeviewSelect>>', show_detail)
    
    def _show_operation_logs(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("操作日志")
        dialog.geometry("1000x600")
        dialog.minsize(900, 500)
        
        logs = self.db.fetch_all('SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 100')
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        columns = ('id', 'operation_type', 'operator', 'target', 'detail', 'created_at')
        tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')
        
        tree.heading('id', text='ID')
        tree.heading('operation_type', text='操作类型')
        tree.heading('operator', text='操作者')
        tree.heading('target', text='目标')
        tree.heading('detail', text='详情')
        tree.heading('created_at', text='时间')
        
        tree.column('id', width=50, stretch=False)
        tree.column('operation_type', width=100, stretch=False)
        tree.column('operator', width=80, stretch=False)
        tree.column('target', width=100, stretch=False)
        tree.column('detail', width=400)
        tree.column('created_at', width=130, stretch=False)
        
        for log in logs:
            detail = log['detail'] if log['detail'] else ''
            tree.insert('', 'end', values=(
                log['id'],
                log['operation_type'],
                log['operator'],
                log['target'],
                detail[:300] + '...' if len(detail) > 300 else detail,
                log['created_at']
            ))
        
        v_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        tree.configure(xscrollcommand=h_scrollbar.set)
        
        tree.pack(fill=tk.BOTH, expand=True)
        
        detail_frame = ttk.LabelFrame(dialog, text="详细信息")
        detail_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
        
        detail_text = tk.Text(detail_frame, height=12, wrap=tk.WORD)
        detail_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        def show_detail(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                values = item['values']
                log_id = values[0]
                log = self.db.fetch_one('SELECT * FROM operation_logs WHERE id = ?', (log_id,))
                if log:
                    detail_text.delete('1.0', tk.END)
                    detail_text.insert('1.0', f"ID: {log['id']}\n操作类型: {log['operation_type']}\n操作者: {log['operator']}\n目标: {log['target']}\n时间: {log['created_at']}\n\n详情:\n{log['detail']}")
        
        tree.bind('<<TreeviewSelect>>', show_detail)

class ConfigDialog:
    def __init__(self, parent, config, db, default_tab=0):
        self.parent = parent
        self.config = config
        self.db = db
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("系统配置")
        self.dialog.geometry("700x600")
        
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self._create_wecom_tab(notebook)
        self._create_ad_tab(notebook)
        self._create_sync_tab(notebook)
        self._create_database_tab(notebook)
        
        if 0 <= default_tab < 4:
            notebook.select(default_tab)
        
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="保存", command=self._save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _create_wecom_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="企业微信")
        
        ttk.Label(frame, text="CorpID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.corp_id_entry = ttk.Entry(frame, width=50)
        self.corp_id_entry.grid(row=0, column=1, padx=5, pady=5)
        self.corp_id_entry.insert(0, self.config.get('corp_id', ''))
        
        ttk.Label(frame, text="CorpSecret:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.corp_secret_entry = ttk.Entry(frame, width=50)
        self.corp_secret_entry.grid(row=1, column=1, padx=5, pady=5)
        self.corp_secret_entry.insert(0, self.config.get('corp_secret', ''))
        
        ttk.Label(frame, text="WeChatBot Key:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.bot_key_entry = ttk.Entry(frame, width=50)
        self.bot_key_entry.grid(row=2, column=1, padx=5, pady=5)
        self.bot_key_entry.insert(0, self.config.get('wechat_bot_key', ''))
    
    def _create_ad_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="AD域")
        
        ttk.Label(frame, text="域名:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.domain_entry = ttk.Entry(frame, width=50)
        self.domain_entry.grid(row=0, column=1, padx=5, pady=5)
        self.domain_entry.insert(0, self.config.get('domain', ''))
        
        ttk.Label(frame, text="默认密码:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.password_entry = ttk.Entry(frame, width=50)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)
        self.password_entry.insert(0, self.config.get('default_password', ''))
        
        ttk.Label(frame, text="强制改密码:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.force_change_var = tk.BooleanVar()
        self.force_change_var.set(self.config.get('force_change_pwd', 'true').lower() == 'true')
        ttk.Checkbutton(frame, variable=self.force_change_var).grid(row=2, column=1, padx=5, pady=5)
    
    def _create_sync_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="同步设置")
        
        ttk.Label(frame, text="同步时间(HH:MM):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.sync_time_entry = ttk.Entry(frame, width=10)
        self.sync_time_entry.grid(row=0, column=1, padx=5, pady=5)
        self.sync_time_entry.insert(0, self.config.get('sync_time', '02:00'))
        
        ttk.Label(frame, text="启用自动同步:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.auto_sync_var = tk.BooleanVar()
        self.auto_sync_var.set(self.config.get('auto_sync', 'false').lower() == 'true')
        ttk.Checkbutton(frame, variable=self.auto_sync_var).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame, text="排除系统用户(逗号分隔):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.exclude_users_entry = ttk.Entry(frame, width=60)
        self.exclude_users_entry.grid(row=2, column=1, padx=5, pady=5)
        self.exclude_users_entry.insert(0, self.config.get('exclude_users', ''))
        
        ttk.Label(frame, text="排除部门名称(逗号分隔):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.exclude_depts_entry = ttk.Entry(frame, width=60)
        self.exclude_depts_entry.grid(row=3, column=1, padx=5, pady=5)
        self.exclude_depts_entry.insert(0, self.config.get('exclude_departments', ''))

        ttk.Label(frame, text="邮箱域名:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.email_domain_entry = ttk.Entry(frame, width=30)
        self.email_domain_entry.grid(row=4, column=1, padx=5, pady=5)
        self.email_domain_entry.insert(0, self.config.get('email_domain', ''))
        
        ttk.Label(frame, text="允许同步的部门:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        
        sync_depts_container = ttk.Frame(frame)
        sync_depts_container.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)
        
        self.sync_depts_canvas = tk.Canvas(sync_depts_container, width=450, height=300)
        self.sync_depts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(sync_depts_container, orient="vertical", command=self.sync_depts_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.sync_depts_canvas.configure(yscrollcommand=scrollbar.set)
        self.sync_depts_inner_frame = ttk.Frame(self.sync_depts_canvas)
        self.sync_depts_canvas.create_window((0, 0), window=self.sync_depts_inner_frame, anchor="nw")
        
        self._load_sync_depts_tree()
        
        
    
    def _load_sync_depts_tree(self):
        for widget in self.sync_depts_inner_frame.winfo_children():
            widget.destroy()
        
        depts = self.db.fetch_all('SELECT wecom_id, name, parent_wecom_id FROM departments ORDER BY order_num')
        
        saved_depts = self.config.get('sync_departments', '')
        saved_dept_ids = set(saved_depts.split(',') if saved_depts else [])
        
        dept_dict = {}
        root_depts = []
        
        for dept in depts:
            dept_dict[dept['wecom_id']] = {
                'name': dept['name'],
                'parent_id': dept['parent_wecom_id'],
                'children': []
            }
        
        for dept_id, dept_info in dept_dict.items():
            parent_id = dept_info['parent_id']
            if parent_id and parent_id in dept_dict:
                dept_dict[parent_id]['children'].append(dept_id)
            else:
                root_depts.append(dept_id)
        
        self.sync_dept_vars = {}
        
        def add_nodes(parent_frame, dept_ids, level=0, row=0):
            current_row = row
            for dept_id in dept_ids:
                dept_info = dept_dict[dept_id]
                
                var = tk.BooleanVar()
                var.set(dept_id in saved_dept_ids)
                self.sync_dept_vars[dept_id] = var
                
                inner_frame = ttk.Frame(parent_frame)
                inner_frame.grid(row=current_row, column=0, sticky=tk.W)
                
                indent = level * 20
                ttk.Checkbutton(inner_frame, variable=var).grid(row=0, column=0, padx=(indent, 5), sticky=tk.W)
                ttk.Label(inner_frame, text=dept_info['name']).grid(row=0, column=1, sticky=tk.W)
                
                current_row += 1
                
                if dept_info['children']:
                    current_row = add_nodes(parent_frame, dept_info['children'], level + 1, current_row)
            
            return current_row
        
        add_nodes(self.sync_depts_inner_frame, root_depts)
        
        self.sync_depts_inner_frame.update_idletasks()
        self.sync_depts_canvas.config(scrollregion=self.sync_depts_canvas.bbox("all"))
    
    def _create_database_tab(self, notebook):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="数据库")
        
        ttk.Label(frame, text="数据库文件:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.db_path_label = ttk.Label(frame, text=self.config.get('db_path', 'data/sync.db'))
        self.db_path_label.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame, text="自动备份:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.auto_backup_var = tk.BooleanVar()
        self.auto_backup_var.set(self.config.get('auto_backup', 'true').lower() == 'true')
        ttk.Checkbutton(frame, variable=self.auto_backup_var).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(frame, text="备份保留天数:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.backup_days_entry = ttk.Entry(frame, width=10)
        self.backup_days_entry.grid(row=2, column=1, padx=5, pady=5)
        self.backup_days_entry.insert(0, self.config.get('backup_days', '7'))
    
    def _save(self):
        try:
            old_auto_sync = self.config.get('auto_sync', 'false').lower() == 'true'
            old_sync_time = self.config.get('sync_time', '02:00')
            
            self.config.set_by_category('wecom', 'corp_id', self.corp_id_entry.get(), '企业微信CorpID')
            self.config.set_by_category('wecom', 'corp_secret', self.corp_secret_entry.get(), '企业微信Secret')
            self.config.set_by_category('wecom', 'wechat_bot_key', self.bot_key_entry.get(), 'WeChatBot密钥')
            
            self.config.set_by_category('ad', 'domain', self.domain_entry.get(), 'AD域名')
            self.config.set_by_category('ad', 'default_password', self.password_entry.get(), '用户默认密码')
            self.config.set_by_category('ad', 'force_change_pwd', str(self.force_change_var.get()), '是否强制改密码')
            
            self.config.set_by_category('sync', 'sync_time', self.sync_time_entry.get(), '自动同步时间')
            self.config.set_by_category('sync', 'auto_sync', str(self.auto_sync_var.get()), '启用自动同步')
            self.config.set_by_category('sync', 'exclude_users', self.exclude_users_entry.get(), '排除的系统用户名')
            self.config.set_by_category('sync', 'exclude_departments', self.exclude_depts_entry.get(), '排除的部门名称')
            
            sync_depts = ','.join([dept_id for dept_id, var in self.sync_dept_vars.items() if var.get()])
            self.config.set_by_category('sync', 'sync_departments', sync_depts, '允许同步的部门ID')
            
            self.config.set_by_category('other', 'email_domain', self.email_domain_entry.get(), '邮箱域名')
            
            self.config.set_by_category('db', 'auto_backup', str(self.auto_backup_var.get()), '自动备份')
            self.config.set_by_category('db', 'backup_days', self.backup_days_entry.get(), '备份保留天数')
            
            new_auto_sync = self.auto_sync_var.get()
            new_sync_time = self.sync_time_entry.get()
            
            if self.parent and hasattr(self.parent, '_on_config_changed'):
                self.parent._on_config_changed(old_auto_sync, old_sync_time, new_auto_sync, new_sync_time)
            
            messagebox.showinfo("成功", "配置保存成功")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("错误", str(e))

class ExportLogDialog:
    def __init__(self, parent, db):
        self.db = db
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("导出日志")
        self.dialog.geometry("600x400")
        self.dialog.minsize(550, 350)
        
        main_frame = ttk.Frame(self.dialog, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        log_type_frame = ttk.LabelFrame(main_frame, text="日志类型")
        log_type_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.log_type_var = tk.StringVar(value="all")
        ttk.Radiobutton(log_type_frame, text="全部", variable=self.log_type_var, value="all").pack(side=tk.LEFT, padx=10, pady=5)
        ttk.Radiobutton(log_type_frame, text="同步日志", variable=self.log_type_var, value="sync").pack(side=tk.LEFT, padx=10, pady=5)
        ttk.Radiobutton(log_type_frame, text="操作日志", variable=self.log_type_var, value="operation").pack(side=tk.LEFT, padx=10, pady=5)
        
        filter_frame = ttk.LabelFrame(main_frame, text="筛选条件")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        id_frame = ttk.Frame(filter_frame)
        id_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(id_frame, text="ID区间:").pack(side=tk.LEFT, padx=5)
        self.id_start_entry = ttk.Entry(id_frame, width=10)
        self.id_start_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(id_frame, text="至").pack(side=tk.LEFT, padx=5)
        self.id_end_entry = ttk.Entry(id_frame, width=10)
        self.id_end_entry.pack(side=tk.LEFT, padx=5)
        
        date_frame = ttk.Frame(filter_frame)
        date_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(date_frame, text="日期区间:").pack(side=tk.LEFT, padx=5)
        self.date_start_entry = ttk.Entry(date_frame, width=15)
        self.date_start_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="至").pack(side=tk.LEFT, padx=5)
        self.date_end_entry = ttk.Entry(date_frame, width=15)
        self.date_end_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="(格式: YYYY-MM-DD)").pack(side=tk.LEFT, padx=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="导出", command=self._export).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _export(self):
        try:
            log_type = self.log_type_var.get()
            
            id_start = self.id_start_entry.get().strip()
            id_end = self.id_end_entry.get().strip()
            date_start = self.date_start_entry.get().strip()
            date_end = self.date_end_entry.get().strip()
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt")],
                initialfile="logs.txt"
            )
            
            if not file_path or not file_path.strip():
                messagebox.showinfo("提示", "导出已取消")
                return
            
            logs = []
            
            if log_type in ('all', 'sync'):
                query = 'SELECT * FROM sync_logs'
                params = []
                conditions = []
                
                if id_start:
                    conditions.append('id >= ?')
                    params.append(int(id_start))
                if id_end:
                    conditions.append('id <= ?')
                    params.append(int(id_end))
                if date_start:
                    conditions.append("created_at >= ?")
                    params.append(f"{date_start} 00:00:00")
                if date_end:
                    conditions.append("created_at <= ?")
                    params.append(f"{date_end} 23:59:59")
                
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                query += ' ORDER BY id DESC'
                
                sync_logs = self.db.fetch_all(query, params if params else None)
                logs.extend([('sync', log) for log in sync_logs])
            
            if log_type in ('all', 'operation'):
                query = 'SELECT * FROM operation_logs'
                params = []
                conditions = []
                
                if id_start:
                    conditions.append('id >= ?')
                    params.append(int(id_start))
                if id_end:
                    conditions.append('id <= ?')
                    params.append(int(id_end))
                if date_start:
                    conditions.append("created_at >= ?")
                    params.append(f"{date_start} 00:00:00")
                if date_end:
                    conditions.append("created_at <= ?")
                    params.append(f"{date_end} 23:59:59")
                
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                query += ' ORDER BY id DESC'
                
                operation_logs = self.db.fetch_all(query, params if params else None)
                logs.extend([('operation', log) for log in operation_logs])
            
            logs.sort(key=lambda x: x[1]['id'], reverse=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("日志导出\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"导出类型: {log_type}\n")
                f.write(f"ID范围: {id_start if id_start else '不限'} - {id_end if id_end else '不限'}\n")
                f.write(f"日期范围: {date_start if date_start else '不限'} - {date_end if date_end else '不限'}\n")
                f.write(f"导出数量: {len(logs)}\n")
                f.write("-" * 40 + "\n\n")
                
                for log_type, log in logs:
                    f.write("=" * 60 + "\n")
                    f.write(f"ID: {log['id']}\n")
                    if log_type == 'sync':
                        f.write(f"类型: 同步日志\n")
                        f.write(f"同步类型: {log['sync_type']}\n")
                        f.write(f"状态: {log['status']}\n")
                        f.write(f"消息: {log['message'] or ''}\n")
                        f.write(f"同步数: {log['sync_count']}\n")
                        f.write(f"错误数: {log['error_count']}\n")
                        f.write(f"开始时间: {log['start_time'] or ''}\n")
                        f.write(f"结束时间: {log['end_time'] or ''}\n")
                    else:
                        f.write(f"类型: 操作日志\n")
                        f.write(f"操作类型: {log['operation_type']}\n")
                        f.write(f"操作者: {log['operator'] or ''}\n")
                        f.write(f"目标: {log['target'] or ''}\n")
                        f.write(f"详情: {log['detail'] or ''}\n")
                    f.write(f"创建时间: {log['created_at']}\n")
                    f.write("-" * 40 + "\n\n")
            
            messagebox.showinfo("导出成功", f"日志已导出到: {file_path}")
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("错误", f"输入格式错误: {str(e)}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

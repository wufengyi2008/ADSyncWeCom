# -*- coding: utf-8 -*-
"""
gui.py - 图形用户界面模块，提供可视化的同步管理界面

作者：怡悦2011
日期：2026
"""
import tkinter as tk

from tkinter import ttk, messagebox, scrolledtext

import logging

import sys

import threading

from datetime import datetime

from typing import Dict, List

from threading import Lock

# ====================  ====================

# TF-8

if sys.stdin is not None:

    sys.stdin.reconfigure(encoding='utf-8')

if sys.stdout is not None:

    sys.stdout.reconfigure(encoding='utf-8')

# ====================  ====================

logging.basicConfig(

    level=logging.INFO,

    format='%(asctime)s - %(levelname)s - %(message)s'

)

logger = logging.getLogger(__name__)

# ====================  ====================

from database import Database

from sync_to_db import sync_wecom_to_db, get_department_tree, get_department_users

from wecom_api import WeComAPI

from ad_sync import ADSync

class DatabaseLogHandler(logging.Handler):

    def __init__(self, db: Database, module: str = 'GUI'):
        super().__init__()
        self.db = db
        self.module = module

    def emit(self, record: logging.LogRecord):
        try:
            log_level = record.levelname
            message = record.getMessage()
            details = None

            if record.exc_info:
                details = self.format(record)

            if self.db:
                self.db.insert_operation_log(log_level, self.module, message, details)
                print(f"[{log_level}] {message}")

        except Exception:
            self.handleError(record)

def setup_database_logging(db: Database, module: str = 'GUI'):
    logger.handlers.clear()

    db_handler = DatabaseLogHandler(db, module)
    db_handler.setLevel(logging.INFO)
    db_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(db_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

class SyncGUI:

    def __init__(self, config: Dict):

        self.config = config

        self.db = Database(config.get('database_path', 'sync.db'))

        setup_database_logging(self.db, 'GUI')

        # API
        self.wecom = None
        try:
            self.wecom = WeComAPI(config['wecom']['corpid'], config['wecom']['corpsecret'])
            logger.info("企业微信API初始化成功")
        except Exception as e:
            error_msg = f"企业微信API初始化失败: {str(e)}"
            logger.error(error_msg)
            # 分析常见错误原因
            error_details = ""
            if "60020" in str(e) or "not allow to access" in str(e).lower():
                error_details = "\n原因：当前IP不在企业微信应用的白名单中，请在企业微信管理后台添加IP白名单"
            elif "40013" in str(e):
                error_details = "\n原因：CorpID无效，请检查配置文件中的CorpID"
            elif "40001" in str(e):
                error_details = "\n原因：CorpSecret无效，请检查配置文件中的CorpSecret"
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                error_details = "\n原因：网络连接失败，请检查网络连接或代理设置"
            messagebox.showerror("API初始化失败", error_msg + error_details)

        # AD同步实例
        self.ad_sync = ADSync(
            config.get('ad_domain', config['domain']),  # AD域
            config['default_password'],                   # 默认密码
            config['exclude_departments'],               # 排除的部门
            config['exclude_accounts'],                  # 排除的账号
            config.get('force_change_password', True),    # 是否强制改密码
            db=self.db                                   # 数据库实例
        )

        # ==================== 初始化 ====================

        self.selection_lock = Lock()

        self.selected_dept_id = None    # D

        self.selected_user_id = None    # D

        # ==================== 创建界面 ====================

        self.root = tk.Tk()

        self.root.title("企业微信-AD同步管理系统")

        self.root.geometry("1000x700")  # 

        self.create_widgets()

        self.load_department_tree()

    def create_widgets(self):

        self.main_frame = ttk.Frame(self.root, padding="10")

        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.top_frame = ttk.Frame(self.main_frame)

        self.top_frame.pack(fill=tk.X, pady=5)

        self.sync_btn = ttk.Button(self.top_frame, text="同步全部企业微信数据", command=self.sync_wecom_data)

        self.sync_btn.pack(side=tk.LEFT, padx=5)

        self.sync_dept_only_btn = ttk.Button(self.top_frame, text="同步选中部门数据", command=self.sync_selected_dept_data, state=tk.DISABLED)

        self.sync_dept_only_btn.pack(side=tk.LEFT, padx=5)

        self.refresh_btn = ttk.Button(self.top_frame, text="刷新列表", command=self.load_department_tree)

        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        self.sync_status_btn = ttk.Button(self.top_frame, text="同步用户状态", command=self.sync_user_status)

        self.sync_status_btn.pack(side=tk.LEFT, padx=5)

        self.stat_frame = ttk.Frame(self.top_frame)

        self.stat_frame.pack(side=tk.RIGHT)

        self.stat_labels = []

        stats = [('部门', 'total_departments', 'synced_departments'), 

                 ('用户', 'total_users', 'synced_users')]

        for label, total_key, synced_key in stats:

            frame = ttk.Frame(self.stat_frame)

            frame.pack(side=tk.LEFT, padx=15)

            total_label = ttk.Label(frame, text=f"{label}:")

            total_label.pack(side=tk.LEFT)

            self.stat_labels.append(ttk.Label(frame, text=f"0/0"))

            self.stat_labels[-1].pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(self.top_frame, text="就绪")

        self.status_label.pack(side=tk.RIGHT, padx=10)

        self.progress_label = ttk.Label(self.top_frame, text="")

        self.progress_label.pack(side=tk.RIGHT, padx=10)

        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)

        self.paned_window.pack(fill=tk.BOTH, expand=True, pady=5)

        self.left_frame = ttk.Frame(self.paned_window, width=300)

        self.paned_window.add(self.left_frame, weight=1)

        self.tree_frame = ttk.Frame(self.left_frame)

        self.tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree_label = ttk.Label(self.tree_frame, text="部门树")

        self.tree_label.pack(pady=5)

        self.department_tree = ttk.Treeview(self.tree_frame, columns=('status',), show='tree headings')

        self.department_tree.heading('#0', text='部门名称')

        self.department_tree.heading('status', text='状态')

        self.department_tree.column('status', width=80, anchor=tk.CENTER)

        self.department_tree.pack(fill=tk.BOTH, expand=True)

        self.department_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.department_tree.yview)

        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.department_tree.configure(yscrollcommand=self.tree_scroll.set)

        self.right_frame = ttk.Frame(self.paned_window, width=500)

        self.paned_window.add(self.right_frame, weight=2)

        self.tab_control = ttk.Notebook(self.right_frame)

        self.tab_control.pack(fill=tk.BOTH, expand=True)

        self.users_tab = ttk.Frame(self.tab_control)

        self.tab_control.add(self.users_tab, text='部门成员')

        self.style = ttk.Style()

        self.style.theme_use('default')

        # Treeview

        self.style.configure('Treeview', 

            background='white',

            foreground='black',

            rowheight=25,

            fieldbackground='white'

        )

        self.style.map('Treeview',

            background=[('selected', '#4a8cff')],

            foreground=[('selected', 'white')]

        )

        self.user_list = ttk.Treeview(self.users_tab, columns=('name', 'userid', 'alias', 'position', 'email', 'status'), show='headings')

        self.user_list.heading('name', text='姓名')

        self.user_list.heading('userid', text='工号')

        self.user_list.heading('alias', text='账号')

        self.user_list.heading('position', text='职位')

        self.user_list.heading('email', text='邮箱')

        self.user_list.heading('status', text='同步状态')

        self.user_list.column('name', width=100)

        self.user_list.column('userid', width=100)

        self.user_list.column('alias', width=80)

        self.user_list.column('position', width=120)

        self.user_list.column('email', width=220)

        self.user_list.column('status', width=100)

        self.user_list.tag_configure('synced', foreground='green')

        self.user_list.tag_configure('syncing', foreground='orange')

        self.user_list.tag_configure('disabled', foreground='gray')

        self.user_list.tag_configure('unsynced', foreground='black')

        self.user_list.pack(fill=tk.BOTH, expand=True)

        self.user_scroll = ttk.Scrollbar(self.users_tab, orient=tk.VERTICAL, command=self.user_list.yview)

        self.user_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.user_list.configure(yscrollcommand=self.user_scroll.set)

        self.log_tab = ttk.Frame(self.tab_control)

        self.tab_control.add(self.log_tab, text='操作日志')

        self.log_text = scrolledtext.ScrolledText(self.log_tab, wrap=tk.WORD, height=20)

        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.bottom_frame = ttk.Frame(self.main_frame)

        self.bottom_frame.pack(fill=tk.X, pady=5)

        self.sync_dept_btn = ttk.Button(self.bottom_frame, text="同步选中部门到AD", command=self.sync_selected_department, state=tk.DISABLED)

        self.sync_dept_btn.pack(side=tk.LEFT, padx=5)

        self.sync_user_btn = ttk.Button(self.bottom_frame, text="同步选中用户到AD", command=self.sync_selected_user, state=tk.DISABLED)

        self.sync_user_btn.pack(side=tk.LEFT, padx=5)

        self.sync_all_btn = ttk.Button(self.bottom_frame, text="同步全部到AD", command=self.sync_all_to_ad)

        self.sync_all_btn.pack(side=tk.LEFT, padx=5)

        self.selected_dept_id = None

        self.selected_user_id = None

        self.user_list.bind('<<TreeviewSelect>>', self.on_user_select)

    def set_buttons_state(self, state):

        stats = self.db.get_statistics()

        if len(self.stat_labels) >= 2:

            self.stat_labels[0].config(text=f"{stats['synced_departments']}/{stats['total_departments']}")
            self.stat_labels[1].config(text=f"{stats['synced_users']}/{stats['total_users']}")

    def load_department_tree(self):
        """加载部门树形结构到Treeview"""
        # 清空现有树
        for item in self.department_tree.get_children():
            self.department_tree.delete(item)
        
        # 获取部门树数据
        dept_tree = get_department_tree(self.db)
        
        # 递归添加部门节点
        def add_nodes(parent_item, depts):
            for dept in depts:
                # 获取部门用户数量
                user_count = len(get_department_users(self.db, dept['id']))
                
                # 获取同步状态显示
                status_text = self.get_sync_status_text(dept['sync_status'])
                status_tag = self.get_sync_status_tag(dept['sync_status'])
                
                # 添加节点（显示部门名称和人数）
                node = self.department_tree.insert(
                    parent_item,
                    tk.END,
                    id=dept['id'],
                    text=f"{dept['name']} ({user_count}人)",
                    values=(status_text,),
                    tags=(status_tag,)
                )
                
                # 递归添加子部门
                if dept.get('children'):
                    add_nodes(node, dept['children'])
        
        # 添加根部门
        add_nodes('', dept_tree)
        
        # 更新统计信息
        self.set_buttons_state(True)
        
        logger.info("部门树加载完成")

    def get_sync_status_text(self, status):
        """获取同步状态文本"""
        status_map = {
            0: '未同步',
            1: '已同步',
            2: '需同步',
            3: '已禁用'
        }
        return status_map.get(status, '未知')

    def get_sync_status_tag(self, status):
        """获取同步状态对应的标签"""
        tag_map = {
            0: 'unsynced',
            1: 'synced',
            2: 'syncing',
            3: 'disabled'
        }
        return tag_map.get(status, 'unsynced')

    def get_status_text(self, status):
        """获取用户同步状态文本（用于用户列表显示）"""
        status_map = {
            0: '未同步',
            1: '已同步',
            2: '需同步',
            3: '已禁用'
        }
        return status_map.get(status, '未知')

    def on_tree_select(self, event):

        with self.selection_lock:

            selection = self.department_tree.selection()

            if selection:

                self.selected_dept_id = int(selection[0])

                selected_dept_id = self.selected_dept_id

            else:

                self.selected_dept_id = None

                selected_dept_id = None

        if selected_dept_id:

            self.sync_dept_btn.config(state=tk.NORMAL)

            self.sync_dept_only_btn.config(state=tk.NORMAL)

            self.load_users(selected_dept_id)

        else:

            self.sync_dept_btn.config(state=tk.DISABLED)

            self.sync_dept_only_btn.config(state=tk.DISABLED)

    def on_user_select(self, event):

        with self.selection_lock:

            selection = self.user_list.selection()

            if selection:

                self.selected_user_id = int(selection[0])

                selected_user_id = self.selected_user_id

            else:

                self.selected_user_id = None

                selected_user_id = None

        if selected_user_id:

            self.sync_user_btn.config(state=tk.NORMAL)

        else:

            self.sync_user_btn.config(state=tk.DISABLED)

    def load_users(self, dept_id):

        for item in self.user_list.get_children():

            self.user_list.delete(item)

        try:

            users = get_department_users(self.db, dept_id)

            for user in users:

                status_text = self.get_status_text(user['sync_status'])

                email = f"{user['wecom_userid']}@{self.config['domain']}"

                sync_status = user['sync_status']

                if sync_status == 1:

                    tag = ('synced',)      
                elif sync_status == 2:

                    tag = ('syncing',)     
                elif sync_status == 3:

                    tag = ('disabled',)    
                else:

                    tag = ('unsynced',)    
                self.user_list.insert('', tk.END, 

                    values=(

                        user['name'],

                        user['wecom_userid'],

                        user.get('alias', '') or '',

                        user.get('position', '') or '',

                        email,

                        status_text

                    ), 

                    iid=user['id'],

                    tags=tag

                )

            self.log_message(f"加载了 {len(users)} 个用户")

        except Exception as e:

            self.log_message(f"加载用户失败: {e}")

    def sync_wecom_data(self):
        """同步企业微信数据到本地数据库"""
        if not self.wecom:
            messagebox.showerror("错误", "企业微信API未初始化\n\n请检查：\n1. 配置文件中的CorpID和CorpSecret是否正确\n2. 当前网络是否可以访问企业微信服务器")
            return

        self.set_buttons_state(False)
        self.status_label.config(text="正在同步...")
        self.progress_label.config(text="同步中...")
        self.root.update()

        def sync_in_thread():
            try:
                self.log_message("开始同步企业微信数据...")

                def update_progress(message):
                    self.root.after(0, lambda: self.progress_label.config(text=message))
                    self.root.after(0, lambda: self.log_message(message))

                # 执行同步
                result = sync_wecom_to_db(self.wecom, self.db, progress_callback=update_progress, domain=self.config['domain'])

                if result:
                    self.root.after(0, lambda: self.log_message("企业微信数据同步完成"))
                    self.root.after(0, lambda: self.load_department_tree())
                    self.root.after(0, lambda: messagebox.showinfo("成功", "数据同步成功"))
                else:
                    self.root.after(0, lambda: self.log_message("同步失败：未知错误"))
                    self.root.after(0, lambda: messagebox.showerror("错误", "同步失败，请查看日志获取详细信息"))

            except Exception as e:
                error_str = str(e)
                error_msg = f"同步失败: {error_str}"
                self.root.after(0, lambda: self.log_message(error_msg))

                # 根据错误类型提供更详细的错误信息
                title = "同步失败"
                detail = ""
                
                if "60020" in error_str or "not allow to access" in error_str.lower():
                    title = "错误 - IP限制"
                    detail = "当前IP不在企业微信应用的白名单中\n\n请联系企业微信管理员在后台添加IP白名单"
                elif "40013" in error_str:
                    title = "错误 - CorpID无效"
                    detail = "配置文件中的CorpID无效\n\n请检查config.ini中的CorpID是否正确"
                elif "40001" in error_str:
                    title = "错误 - CorpSecret无效"
                    detail = "配置文件中的CorpSecret无效\n\n请检查config.ini中的CorpSecret是否正确"
                elif "40003" in error_str:
                    title = "错误 - 用户不存在"
                    detail = "无法获取用户信息，可能是用户已被删除或权限不足"
                elif "network" in error_str.lower() or "connection" in error_str.lower() or "timeout" in error_str.lower():
                    title = "错误 - 网络连接失败"
                    detail = "无法连接到企业微信服务器\n\n请检查：\n1. 网络连接是否正常\n2. 是否需要配置代理\n3. 企业微信服务器是否正常"
                elif "ssl" in error_str.lower() or "certificate" in error_str.lower():
                    title = "错误 - SSL证书问题"
                    detail = "SSL证书验证失败\n\n可能是网络环境中的SSL代理问题"
                elif "permission" in error_str.lower() or "40014" in error_str:
                    title = "错误 - 权限不足"
                    detail = "企业微信应用权限不足\n\n请确保应用已获得通讯录读写权限"
                else:
                    detail = error_str

                self.root.after(0, lambda: messagebox.showerror(title, detail))

            finally:
                self.root.after(0, lambda: self.status_label.config(text="就绪"))
                self.root.after(0, lambda: self.progress_label.config(text=""))
                self.root.after(0, lambda: self.set_buttons_state(True))

        threading.Thread(target=sync_in_thread, daemon=True).start()

    def sync_selected_department(self):

        with self.selection_lock:

            selections = self.department_tree.selection()

            if not selections:

                return

            selected_dept_ids = [int(s) for s in selections]

        depts = []

        for dept_id in selected_dept_ids:

            dept = self.db.get_department_by_id(dept_id)

            if dept:

                depts.append(dept)

        if not depts:
            messagebox.showerror("错误", "未找到部门")
            return

        self.set_buttons_state(False)

        self.status_label.config(text=f"正在同步 {len(depts)} 个部门...")

        self.root.update()

        def sync_in_thread():

            try:

                self.log_message(f"开始同步 {len(depts)} 个部门...")

                batch_depts = []

                for dept in depts:

                    dept_path = dept['path'].split('\\') if dept['path'] else [dept['name']]

                    if len(dept_path) > 1:

                        parent_path = dept_path[:-1]

                        parent_dn = self.ad_sync.get_ou_dn(parent_path)

                    else:

                        parent_dn = f"DC={self.config['ad_domain'].replace('.', ',DC=')}"

                    batch_depts.append({

                        'id': dept['id'],

                        'name': dept['name'],

                        'parent_dn': parent_dn

                    })

                success, message = self.ad_sync.batch_create_ous(batch_depts)

                self.root.after(0, lambda: self.log_message(message))

                # 如果同步成功，更新部门状态
                if success:
                    for dept in batch_depts:
                        self.db.update_department_sync_status(dept['id'], 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        self.db.insert_sync_log('SYNC', 'DEPARTMENT', dept['id'], dept['name'], 'SUCCESS')

                self.root.after(0, lambda: self.load_department_tree())

                self.root.after(0, lambda: self.update_statistics())

                if success:

                    self.root.after(0, lambda: messagebox.showinfo("成功", f"同步了 {len(batch_depts)} 个部门"))

                else:

                    self.root.after(0, lambda: messagebox.showerror("错误", f"同步失败: {message}"))

            except Exception as e:

                self.root.after(0, lambda: self.log_message(f"同步失败: {e}"))

                self.root.after(0, lambda: messagebox.showerror("错误", f"同步失败: {e}"))

            finally:

                self.root.after(0, lambda: self.status_label.config(text="就绪"))

                self.root.after(0, lambda: self.set_buttons_state(True))

        threading.Thread(target=sync_in_thread, daemon=True).start()

    def sync_selected_dept_data(self):

        with self.selection_lock:

            if not self.selected_dept_id:

                return

            selected_dept_id = self.selected_dept_id

            dept = self.db.get_department_by_id(selected_dept_id)

        if not self.wecom:
            messagebox.showerror("错误", "企业微信API未初始化")
            return

        if not dept:
            messagebox.showerror("错误", "未选择部门")
            return

        self.set_buttons_state(False)

        self.status_label.config(text=f"正在同步 {dept['name']}...")

        self.progress_label.config(text="同步中...")

        self.root.update()

        def sync_in_thread():

            try:

                self.log_message(f"{dept['name']} 同步中...")

                dept_users = self.wecom.get_department_users(dept['wecom_dept_id'])

                self.root.after(0, lambda: self.log_message(f"{len(dept_users)} 个用户"))

                for user in dept_users:

                    userid = user['userid']

                    name = user.get('name', '')

                    alias = user.get('alias', '')

                    position = user.get('position', '')

                    email = f"{userid}@{self.config['domain']}"

                    mobile = ''

                    dept_ids = user.get('department', [])

                    dept_ids_str = ','.join(str(d) for d in dept_ids) if dept_ids else ''

                    db_user_id = self.db.insert_user(userid, name, email, mobile, dept_ids_str, alias, position)

                    if db_user_id == 0:

                        existing_user = self.db.get_user_by_wecom_id(userid)

                        if existing_user:

                            db_user_id = existing_user['id']

                    if db_user_id > 0:

                        self.db.clear_user_department(db_user_id)

                        for d_id in dept_ids:

                            db_dept = self.db.get_department_by_wecom_id(d_id)

                            if db_dept:

                                self.db.insert_user_department(db_user_id, db_dept['id'])

                self.root.after(0, lambda: self.log_message(f"部门 {dept['name']} 同步完成"))

                self.root.after(0, lambda: self.load_department_tree())

                if self.selected_dept_id:

                    self.root.after(0, lambda: self.load_users(self.selected_dept_id))

                self.root.after(0, lambda: messagebox.showinfo("成功", f"部门 {dept['name']} 同步成功"))

            except Exception as e:

                error_msg = f"同步失败: {str(e)}"

                self.root.after(0, lambda: self.log_message(error_msg))

                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))

            finally:

                self.root.after(0, lambda: self.status_label.config(text="就绪"))

                self.root.after(0, lambda: self.progress_label.config(text=""))

                self.root.after(0, lambda: self.set_buttons_state(True))

        threading.Thread(target=sync_in_thread, daemon=True).start()

    def sync_selected_user(self):

        with self.selection_lock:

            selections = self.user_list.selection()

            if not selections:

                return

            selected_user_ids = [int(s) for s in selections]

            selected_dept_id = self.selected_dept_id

        users = []

        for user_id in selected_user_ids:

            user = self.db.get_user_by_id(user_id)

            if user:

                users.append(user)

        if not users:
            messagebox.showerror("错误", "未找到用户")
            return

        self.set_buttons_state(False)

        self.status_label.config(text=f"正在同步 {len(users)} 个用户...")

        self.root.update()

        def sync_in_thread():

            try:

                self.log_message(f"{len(users)} 个用户同步中...")

                batch_users = []

                skipped_users = []

                for user in users:

                    email = user['email'] if user['email'] else f"{user['wecom_userid']}@{self.config['domain']}"

                    dept_ids = [int(d) for d in user['department_ids'].split(',')] if user['department_ids'] else []

                    target_dept = None

                    for dept_id in dept_ids:

                        dept = self.db.get_department_by_wecom_id(dept_id)

                        if dept and dept['name'] not in self.config['exclude_departments']:

                            target_dept = dept

                            break

                    if not target_dept:

                        skipped_users.append(user)

                        continue

                    dept_path = target_dept['path'].split('\\') if target_dept['path'] else [target_dept['name']]

                    ou_dn = self.ad_sync.get_ou_dn(dept_path)

                    base_name = user['name']

                    name_count[base_name] = name_count.get(base_name, 0) + 1

                    if name_count[base_name] > 1:

                        username = f"{base_name}{user['alias']}"

                    else:

                        username = base_name

                    batch_users.append({

                        'id': user['id'],

                        'username': username,

                        'display_name': user['name'],

                        'email': email,

                        'ou_dn': ou_dn,

                        'group_name': target_dept['name'],

                        'is_new': not self.ad_sync.get_user(username)

                    })

                    self.root.after(0, lambda u=user: self.log_message(f"同步用户: {u['name']}"))

                if batch_users:

                    success, message = self.ad_sync.batch_create_users(batch_users)

                    self.root.after(0, lambda: self.log_message(message))

                    # 如果同步成功，更新用户状态
                    if success:
                        for user in batch_users:
                            self.db.update_user_sync_status(user['id'], 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            self.db.update_user_ad_exists(user['id'], 1)
                            self.db.insert_sync_log('SYNC', 'USER', user['id'], user['display_name'], 'SUCCESS')

                else:

                    success = True

                    message = "同步完成"

                if selected_dept_id:

                    self.root.after(0, lambda: self.load_users(selected_dept_id))

                self.root.after(0, lambda: self.update_statistics())

                if success:

                    self.root.after(0, lambda: messagebox.showinfo("成功", f"同步了 {len(batch_users)} 个用户"))

                else:

                    self.root.after(0, lambda: messagebox.showerror("错误", f"同步失败: {message}"))

            except Exception as e:

                self.root.after(0, lambda: self.log_message(f"同步失败: {e}"))

                self.root.after(0, lambda: messagebox.showerror("错误", f"同步失败: {e}"))

            finally:

                self.root.after(0, lambda: self.status_label.config(text="就绪"))

                self.root.after(0, lambda: self.set_buttons_state(True))

        threading.Thread(target=sync_in_thread, daemon=True).start()

    def sync_user_status(self):

        if not messagebox.askyesno("确认", "确定要同步用户状态到AD吗？"):
            return

        self.set_buttons_state(False)

        self.status_label.config(text="同步用户状态...")

        self.root.update()

        def sync_in_thread():

            try:

                self.root.after(0, lambda: self.log_message("同步中..."))

                all_users = self.db.get_all_users()

                name_count = {}

                db_usernames = []

                for user in all_users:

                    base_name = user['name']

                    name_count[base_name] = name_count.get(base_name, 0) + 1

                    if name_count[base_name] > 1:

                        username = f"{base_name}{user['alias']}" if user['alias'] else base_name

                    else:

                        username = base_name

                    db_usernames.append(username)

                # AD

                success, message = self.ad_sync.sync_user_status(db_usernames)

                self.root.after(0, lambda: self.log_message(message))

                if success:

                    ad_users = self.ad_sync.get_all_enabled_users()

                    ad_usernames_lower = {u.lower() for u in ad_users}

                    synced_count = 0

                    disabled_count = 0

                    need_sync_count = 0

                    for user in all_users:

                        base_name = user['name']

                        # AD?                        current_count = sum(1 for u in all_users if u['name'] == base_name)

                        if current_count > 1:

                            username = f"{base_name}{user['alias']}" if user['alias'] else base_name

                        else:

                            username = base_name

                        # D

                        if username.lower() in ad_usernames_lower:

                            if user['sync_status'] != 1:

                                self.db.update_user_sync_status(user['id'], 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

                                synced_count += 1

                        else:
                            # 用户不在AD启用列表中
                            if user['sync_status'] == 1:
                                # 已同步过的用户现在不在AD中，标记为已禁用
                                self.db.update_user_sync_status(user['id'], 3, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                                self.db.insert_sync_log('SYNC', 'USER', user['id'], user['name'], 'DISABLED')
                                disabled_count += 1
                            elif user['sync_status'] != 2:
                                # 未同步过的用户，标记为需同步
                                self.db.update_user_sync_status(user['id'], 2)
                                need_sync_count += 1

                    self.root.after(0, lambda: self.load_department_tree())

                    result_msg = f"- {synced_count} 已同步\n- {need_sync_count} 需同步\n- {disabled_count} 已禁用"

                    self.root.after(0, lambda: self.log_message(result_msg))

                    self.root.after(0, lambda: messagebox.showinfo("同步完成", result_msg))

                else:

                    self.root.after(0, lambda: messagebox.showerror("错误", f"{message}"))

            except Exception as e:

                self.root.after(0, lambda: self.log_message(f"同步失败: {e}"))

                self.root.after(0, lambda: messagebox.showerror("错误", f"同步失败: {e}"))

            finally:

                self.root.after(0, lambda: self.status_label.config(text="就绪"))

                self.root.after(0, lambda: self.set_buttons_state(True))

        threading.Thread(target=sync_in_thread, daemon=True).start()

    def sync_all_to_ad(self):

        if not messagebox.askyesno("确认", "确定要同步所有数据到AD吗？"):

            return

        self.set_buttons_state(False)

        self.status_label.config(text="正在同步所有数据...")

        self.root.update()

        def sync_in_thread():

            try:

                departments = self.db.get_all_departments()

                users = self.db.get_all_users()

                self.root.after(0, lambda: self.log_message(f"准备同步 {len(departments)} 个部门, {len(users)} 个用户"))

                for dept in departments:

                    self.root.after(0, lambda d=dept: self.log_message(f"同步部门: {d['name']}"))

                    dept_path = dept['path'].split('\\') if dept['path'] else [dept['name']]

                    if len(dept_path) > 1:

                        parent_path = dept_path[:-1]

                        parent_dn = self.ad_sync.get_ou_dn(parent_path)

                    else:

                        parent_dn = f"DC={self.config['ad_domain'].replace('.', ',DC=')}"

                    if self.ad_sync.create_ou(dept['name'], parent_dn):

                        self.db.update_department_sync_status(dept['id'], 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

                for user in users:

                    self.root.after(0, lambda u=user: self.log_message(f": {u['name']}"))

                    email = user['email'] if user['email'] else f"{user['wecom_userid']}@{self.config['domain']}"

                    dept_ids = [int(d) for d in user['department_ids'].split(',')] if user['department_ids'] else []

                    target_dept = None

                    for dept_id in dept_ids:

                        dept = self.db.get_department_by_wecom_id(dept_id)

                        if dept and dept['name'] not in self.config['exclude_departments']:

                            target_dept = dept

                            break

                    if target_dept:

                        dept_path = target_dept['path'].split('\\') if target_dept['path'] else [target_dept['name']]

                        ou_dn = self.ad_sync.get_ou_dn(dept_path)

                        existing_user = self.ad_sync.get_user(user['wecom_userid'])

                        if existing_user:

                            self.ad_sync.update_user(user['wecom_userid'], user['name'], email, ou_dn)

                        else:

                            self.ad_sync.create_user(user['wecom_userid'], user['name'], email, ou_dn)

                        self.db.update_user_sync_status(user['id'], 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

                        self.db.update_user_ad_exists(user['id'], 1)

                self.root.after(0, lambda: self.log_message("所有数据同步完成"))

                self.root.after(0, lambda: self.load_department_tree())

                self.root.after(0, lambda: messagebox.showinfo("成功", "所有数据同步完成"))

            except Exception as e:

                self.root.after(0, lambda: self.log_message(f"同步失败: {e}"))

                self.root.after(0, lambda: messagebox.showerror("错误", f"同步失败: {e}"))

            finally:

                self.root.after(0, lambda: self.status_label.config(text="就绪"))

                self.root.after(0, lambda: self.set_buttons_state(True))

        threading.Thread(target=sync_in_thread, daemon=True).start()

    def log_message(self, message):

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")

        self.log_text.see(tk.END)

    def run(self):

        self.root.mainloop()

if __name__ == "__main__":

    from config import read_config

    try:

        config = read_config()

        gui = SyncGUI(config)

        gui.run()

    except Exception as e:

        messagebox.showerror("", f": {e}")

        logger.error(f"错误: {e}")

import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Treeview Tag Test")
root.geometry("500x300")

style = ttk.Style()
style.theme_use('clam')

tree = ttk.Treeview(root, columns=('name', 'status'), show='headings')
tree.heading('name', text='名称')
tree.heading('status', text='状态')
tree.column('name', width=200)
tree.column('status', width=100)

tree.tag_configure('status_unsynced', foreground='#6C757D')
tree.tag_configure('status_synced', foreground='#198754')
tree.tag_configure('status_needsync', foreground='#F59E0B')
tree.tag_configure('status_disabled', foreground='#DC3545')

tree.insert('', 'end', values=('张三', '未同步'), tags=('status_unsynced',))
tree.insert('', 'end', values=('李四', '已同步'), tags=('status_synced',))
tree.insert('', 'end', values=('王五', '需同步'), tags=('status_needsync',))
tree.insert('', 'end', values=('赵六', '已禁用'), tags=('status_disabled',))

tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

root.mainloop()
# -*- coding: utf-8 -*-
"""
build_exe.py - 打包脚本，使用PyInstaller生成可执行文件

作者：怡悦2011
日期：2026
"""
import PyInstaller.__main__
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))

# PyInstaller 参数配置
args = [
    # 主入口文件
    'gui.py',
    
    # 基础配置
    '--name=ADSyncWeCom',                         # 可执行文件名称
    '--onefile',                                  # 单文件模式
    '--windowed',                                 # 窗口模式（无控制台）
    '--clean',                                    # 清理之前的构建缓存
    '--noconfirm',                                # 不确认覆盖
    
    # 资源文件
    '--add-data', f'config.ini;.',                # 配置文件
    
    # 隐藏导入（PyInstaller无法自动检测的模块）
    '--hidden-import', 'database',                # 数据库模块
    '--hidden-import', 'db_base',                # 数据库基础模块
    '--hidden-import', 'db_department',          # 部门数据模块
    '--hidden-import', 'db_user',                 # 用户数据模块
    '--hidden-import', 'db_log',                  # 日志数据模块
    '--hidden-import', 'sync_to_db',              # 同步模块
    '--hidden-import', 'wecom_api',               # 企业微信API模块
    '--hidden-import', 'ad_sync',                 # AD同步模块
    '--hidden-import', 'config',                  # 配置模块
    '--hidden-import', 'utils',                    # 工具模块
    '--hidden-import', 'wechat_bot',              # 微信机器人模块
    '--hidden-import', 'tkinter',                 # GUI模块
    '--hidden-import', 'sqlite3',                 # SQLite数据库
    '--hidden-import', 'requests',                 # HTTP请求库
    '--hidden-import', 'logging.handlers',        # 日志处理器
    
    # 图标（可选）
    # '--icon=icon.ico',                          # 应用图标
    
    # 输出路径
    '--distpath', os.path.join(current_dir, 'dist'),     # 输出目录
    '--workpath', os.path.join(current_dir, 'build'),     # 工作目录
    '--specpath', current_dir,                           # spec文件目录
]

print("=" * 60)
print("ADSyncWeCom 打包程序")
print("=" * 60)
print(f"入口文件: gui.py")
print(f"输出目录: {os.path.join(current_dir, 'dist')}")
print(f"参数: {' '.join(args)}")
print("=" * 60)
print("开始打包...")
print()

# 执行PyInstaller
try:
    PyInstaller.__main__.run(args)
    
    print()
    print("=" * 60)
    print("打包完成！")
    print(f"可执行文件位置: {os.path.join(current_dir, 'dist', 'ADSyncWeCom.exe')}")
    print("=" * 60)
    
except Exception as e:
    print()
    print("=" * 60)
    print(f"打包失败: {str(e)}")
    print("=" * 60)
    sys.exit(1)

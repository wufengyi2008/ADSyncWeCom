# -*- coding: utf-8 -*-
"""
test_sync.py - 测试脚本，验证同步功能

作者：怡悦2011
日期：2026
"""
#!/usr/bin/env python

# -*- coding: utf-8 -*-

""""""

import sys

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ad_sync import ADSync

# ADSync

ad_sync = ADSync(

    domain="gf.cn",

    default_password="Gf666.888",

    exclude_departments=[],

    exclude_accounts=[],

    force_change_password=True

)


test_user = {

    'id': 1,

    'username': 'testuser001',

    'display_name': '001',

    'email': 'testuser001@fenglink.com.cn',

    'ou_dn': 'OU=,DC=gf,DC=cn',

    'group_name': '',

    'is_new': True

}

print("...")

print(f": {test_user}")


success, message = ad_sync.batch_create_users([test_user])

print(f"\n: {'' if success else ''}")

print(f"结果: {message}")

# 如果同步失败，显示日志路径
if not success:
    print("\n同步失败，请查看日志...")

    log_path = os.path.join(os.path.dirname(__file__), 'logs')

    if os.path.exists(log_path):

        import glob

        log_files = glob.glob(os.path.join(log_path, '*.log'))

        if log_files:

            latest_log = sorted(log_files)[-1]

            print(f" {latest_log}")

            with open(latest_log, 'r', encoding='utf-8') as f:

                content = f.read()

                print("\n:")

                print(content[-2000:])  # 注释000?        else:

            print("")

    else:

        print("测试完成")
        print("=" * 50)
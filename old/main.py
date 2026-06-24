# -*- coding: utf-8 -*-
"""
main.py - 主程序入口，执行企业微信到AD域的同步任务

作者：怡悦2011
日期：2026
"""
import os
import sys
import csv
import time
from datetime import datetime

sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

from utils import setup_logging, format_time_duration
from config import read_config
from wecom_api import WeComAPI
from ad_sync import ADSync
from wechat_bot import WeChatBot


def main():
    start_time = time.time()
    sync_stats = {
        'total_users': 0,
        'processed_users': 0,
        'disabled_users': [],
        'error_count': 0,
        'log_file': ''
    }

    logger, log_filename = setup_logging()
    sync_stats['log_file'] = log_filename

    try:
        config = read_config()

        bot = WeChatBot(config['webhook_url'])

        start_message = f"""## 企业微信-AD同步开始执行

> 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 域名: {config['domain']}
"""
        bot.send_message(start_message)

        wecom = WeComAPI(config['wecom']['corpid'], config['wecom']['corpsecret'])
        ad_sync = ADSync(
            config['domain'],
            config['default_password'],
            config['exclude_departments'],
            config['exclude_accounts'],
            config.get('force_change_password', True)
        )

        wecom_users = set()
        departments = wecom.get_department_list()

        for dept in departments:
            users = wecom.get_department_users(dept['id'])
            wecom_users.update(user['userid'] for user in users)

        logger.info(f"企业微信中共有 {len(wecom_users)} 个用户账户")

        dept_tree = {}
        for dept in departments:
            dept_tree[dept['id']] = {
                'name': dept['name'],
                'parentid': dept['parentid'],
                'path': []
            }

        for dept_id in dept_tree:
            path = []
            current_id = dept_id
            while current_id != 0:
                if current_id not in dept_tree:
                    break
                path.insert(0, dept_tree[current_id]['name'])
                current_id = dept_tree[current_id]['parentid']
            dept_tree[dept_id]['path'] = path

        for dept_id, dept_info in dept_tree.items():
            current_path = []
            for ou_name in dept_info['path']:
                current_path.append(ou_name)
                if len(current_path) > 1:
                    parent_path = current_path[:-1]
                    parent_dn = ad_sync.get_ou_dn(parent_path)
                else:
                    parent_dn = f"DC={config['ad_domain'].replace('.', ',DC=')}"
                ad_sync.create_ou(ou_name, parent_dn)

        logger.info("开始同步用户...")
        processed_users = set()

        user_departments = {}
        for dept_id in dept_tree:
            users = wecom.get_department_users(dept_id)
            for user in users:
                userid = user['userid']
                if userid not in user_departments:
                    user_departments[userid] = {
                        'user_info': user,
                        'departments': []
                    }
                user_departments[userid]['departments'].append(dept_tree[dept_id])

        for userid, info in user_departments.items():
            if userid in processed_users:
                continue

            user = info['user_info']
            departments = info['departments']
            username = user['userid']
            display_name = user['name']

            target_dept = None
            for dept in departments:
                if dept['path'] and dept['path'][-1] not in config['exclude_departments']:
                    target_dept = dept
                    break

            if not target_dept:
                logger.warning(f"用户 {username} ({display_name}) 所有部门都在排除列表中，跳过处理")
                processed_users.add(userid)
                continue

            ou_path = target_dept['path']
            ou_dn = ad_sync.get_ou_dn(ou_path)

            user_detail = wecom.get_user_detail(username)
            email = user_detail.get('email', '')

            if not email:
                email = f"{username}@{config['domain']}"
                logger.warning(f"用户 {display_name}({username}) 在企业微信中未设置邮箱，使用默认邮箱: {email}")

            logger.info(f"处理用户: {display_name}, 用户ID: {username}, 邮箱: {email}, 选定部门: {ou_path[-1]}")

            existing_user = ad_sync.get_user(username)
            if existing_user:
                ad_sync.update_user(
                    username,
                    display_name,
                    email,
                    ou_dn
                )
            else:
                if ad_sync.create_user(
                    username,
                    display_name,
                    email,
                    ou_dn
                ):
                    logger.info(f"成功创建用户: {username}")
                else:
                    logger.error(f"创建用户失败: {username}")
                    continue

            for dept in departments:
                if dept['path'] and dept['path'][-1] not in config['exclude_departments']:
                    ou_name = dept['path'][-1]
                    ad_sync.add_user_to_group(username, ou_name)

            processed_users.add(userid)

        sync_stats['total_users'] = len(wecom_users)
        sync_stats['processed_users'] = len(processed_users)

        logger.info(f"用户同步完成，共处理 {len(processed_users)} 个用户")

        logger.info("开始处理需要禁用的账户...")
        enabled_ad_users = ad_sync.get_all_enabled_users()
        logger.info(f"AD域控中共有 {len(enabled_ad_users)} 个启用状态的账户")

        users_to_disable = set(enabled_ad_users) - wecom_users

        if users_to_disable:
            logger.info(f"发现 {len(users_to_disable)} 个需要禁用的账户")

            disable_log_filename = f"disabled_accounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(disable_log_filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'SamAccountName',
                    'DisplayName',
                    'Mail',
                    'Created',
                    'Modified',
                    'LastLogonDate',
                    'Description',
                    'DisableTime'
                ])
                writer.writeheader()

                for username in users_to_disable:
                    user_details = ad_sync.get_user_details(username)
                    if user_details:
                        user_details['DisableTime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        for field in writer.fieldnames:
                            if field not in user_details:
                                user_details[field] = ''
                        writer.writerow(user_details)

                    ad_sync.disable_user(username)

            logger.info(f"已将禁用账户信息记录到文件: {disable_log_filename}")
            sync_stats['disabled_users'] = list(users_to_disable)
        else:
            logger.info("没有需要禁用的账户")

        end_time = time.time()
        duration = format_time_duration(end_time - start_time)

        result_message = """\1"""
        send_result = bot.send_message(result_message)
        if not send_result:
            logger.warning("发送执行结果通知失败")

        logger.info("所有同步操作已完成")

    except Exception as e:
        sync_stats['error_count'] += 1
        error_message = f"""## 企业微信-AD同步执行异常

> 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### 错误信息
{str(e)}

请检查日志文件了解详细信息。
"""
        try:
            bot.send_message(error_message)
        except:
            pass
        logger.error(f"同步过程出现错误: {str(e)}")
        raise


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
config.py - 配置文件管理模块，读取和解析配置信息

作者：怡悦2011
日期：2026
"""
import configparser
import logging
import os
import sys
from typing import Dict, List

logger = logging.getLogger(__name__)


def get_config_path() -> str:
    """获取配置文件路径，支持打包后的单文件模式"""
    # 如果是打包后的exe运行
    if hasattr(sys, '_MEIPASS'):
        # 优先检查exe所在目录的config.ini
        exe_dir = os.path.dirname(sys.executable)
        exe_config_path = os.path.join(exe_dir, 'config.ini')
        if os.path.exists(exe_config_path):
            return exe_config_path
        # 否则使用打包时嵌入的配置文件
        return os.path.join(sys._MEIPASS, 'config.ini')
    # 开发模式下使用当前目录
    return 'config.ini'


def read_config(config_path: str = None) -> Dict:
    if config_path is None:
        config_path = get_config_path()
    
    config_parser = configparser.ConfigParser()
    config_parser.read(config_path, encoding='utf-8')

    # 获取AD域配置，如果未配置则使用邮箱域名
    ad_domain = config_parser.get('Domain', 'ADDomain', fallback=None)
    if not ad_domain:
        ad_domain = config_parser.get('Domain', 'Name')
    
    config = {
        'wecom': {
            'corpid': config_parser.get('WeChat', 'CorpID'),
            'corpsecret': config_parser.get('WeChat', 'CorpSecret')
        },
        'domain': config_parser.get('Domain', 'Name'),
        'ad_domain': ad_domain,
        'exclude_departments': [d.strip() for d in config_parser.get('ExcludeDepartments', 'Names').split(',') if d.strip()],
        'exclude_accounts': [
            *[acc.strip() for acc in config_parser.get('ExcludeUsers', 'SystemAccounts').split(',') if acc.strip()],
            *[acc.strip() for acc in config_parser.get('ExcludeUsers', 'CustomAccounts').split(',') if acc.strip()]
        ],
        'webhook_url': config_parser.get('WeChatBot', 'WebhookUrl'),
        'default_password': config_parser.get('Account', 'DefaultPassword'),
        'force_change_password': config_parser.getboolean('Account', 'ForceChangePassword', fallback=True),
        'database_path': config_parser.get('Database', 'Path', fallback='sync.db')
    }

    validate_config(config)
    return config


def validate_config(config: Dict) -> None:
    errors = []

    if not config['wecom']['corpid'] or config['wecom']['corpid'] == '企业微信的CorpID':
        errors.append("请配置企业微信CorpID")

    if not config['wecom']['corpsecret'] or config['wecom']['corpsecret'] == '企业微信的应用Secret':
        errors.append("请配置企业微信CorpSecret")

    if not config['domain'] or config['domain'] == '域名(如: company.com)':
        errors.append("请配置域名")

    if not config['webhook_url'] or 'key=' not in config['webhook_url']:
        errors.append("请配置有效的企业微信机器人Webhook地址")

    if not config['default_password'] or config['default_password'] == '新建用户默认密码':
        errors.append("请配置新建用户默认密码")

    if errors:
        error_msg = "配置验证失败:\n" + "\n".join(f"- {error}" for error in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

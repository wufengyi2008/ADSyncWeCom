# -*- coding: utf-8 -*-
"""
utils.py - 工具函数模块，提供通用工具方法

作者：怡悦2011
日期：2026
"""
import logging

from datetime import datetime

def setup_logging():

    # ad_wecom_sync_YYYYMMDD_HHMMSS.log

    log_filename = f"ad_wecom_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # logging

    logging.basicConfig(

        level=logging.INFO,  # 

        format='%(asctime)s - %(levelname)s - %(message)s',  # 

        handlers=[

            # 注释- 

            logging.FileHandler(log_filename, encoding='utf-8'),

            #  - 

            logging.StreamHandler()

        ]

    )

    return logging.getLogger(__name__), log_filename

def format_time_duration(seconds: float) -> str:

    # divmod

    minutes, seconds = divmod(int(seconds), 60)  # 60?1

    hours, minutes = divmod(minutes, 60)        # 60=1


    if hours > 0:
        # 格式化输出
        return f"{hours}小时{minutes}分{seconds}秒"
    elif minutes > 0:
        # 格式化输出
        return f"{minutes}分{seconds}秒"
    else:
        # 格式化输出
        return f"{seconds}秒"

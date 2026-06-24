# -*- coding: utf-8 -*-
"""
wechat_bot.py - 企业微信机器人模块，发送消息通知

作者：怡悦2011
日期：2026
"""
import json

import logging

import requests

logger = logging.getLogger(__name__)

class WeChatBot:

    def __init__(self, webhook_url: str):

        self.webhook_url = webhook_url

        logger.info(f"企业微信机器人初始化: {webhook_url}")

    def send_message(self, content: str) -> bool:

        try:

            logger.info("发送消息中...")

            logger.debug(f"消息内容: {content}")

            # 构建消息payload
            data = {

                "msgtype": "markdown",  # 消息类型：markdown

                "markdown": {

                    "content": content

                }

            }

            # POST请求到Webhook
            response = requests.post(

                self.webhook_url,

                json=data,
                timeout=10  # 10秒超时
            )

            # 检查HTTP请求状态
            response.raise_for_status()

            # 解析JSON响应
            result = response.json()

            # 检查API响应
            if result.get('errcode') == 0:

                logger.info("消息发送成功")

                return True

            else:

                # API返回错误
                logger.error(f"API返回错误: {result}")

                return False

        except requests.RequestException as e:

            logger.error(f"HTTP请求失败: {str(e)}")

            return False

        except json.JSONDecodeError as e:

            # JSON解析失败
            logger.error(f"JSON解析失败: {str(e)}")

            return False

        except Exception as e:

            logger.error(f"未知错误: {str(e)}")

            return False

import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config_manager import ConfigManager


class EmailService:
    _instance: Optional['EmailService'] = None
    
    def __new__(cls) -> 'EmailService':
        if cls._instance is None:
            cls._instance = super(EmailService, cls).__new__(cls)
            cls._instance.config = ConfigManager()
        return cls._instance
    
    def _get_smtp_connection(self, smtp_server: str, smtp_port: int, use_ssl: bool, timeout: int = 10):
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout)
            server.starttls()
        return server
    
    def send_account_notification(self, to_email: str, username: str, password: str, domain: str) -> bool:
        if not self.config.is_email_configured():
            return False
        
        if not to_email:
            return False
        
        try:
            smtp_server = self.config.get('smtp_server', '')
            smtp_port = int(self.config.get('smtp_port', '465'))
            smtp_user = self.config.get('smtp_user', '')
            smtp_password = self.config.get('smtp_password', '')
            sender_email = self.config.get('sender_email', '')
            subject = self.config.get('email_subject', 'AD域账号开通通知')
            use_ssl = self.config.get('use_ssl', 'true').lower() == 'true'
            
            message = MIMEMultipart()
            message['From'] = sender_email
            message['To'] = to_email
            message['Subject'] = subject
            
            body = f"""尊敬的用户：

您好！您的AD域账号已成功创建。

账号信息如下：
- 用户名：{username}
- 密码：{password}
- 域名：{domain}

登录方式：
- 登录名格式：{domain}\\{username} 或 {username}@{domain}

注意事项：
1. 请在首次登录后及时修改密码
2. 请妥善保管您的账号信息，不要泄露给他人
3. 如遇问题请联系系统管理员

祝您使用愉快！

系统自动发送，请勿回复
"""
            
            message.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = self._get_smtp_connection(smtp_server, smtp_port, use_ssl, timeout=15)
            try:
                server.login(smtp_user, smtp_password)
                text = message.as_string()
                server.sendmail(sender_email, to_email, text)
            finally:
                server.quit()
            
            return True
        except Exception as e:
            try:
                from logger import Logger
                logger = Logger()
                logger.error(f'发送邮件失败: {str(e)}')
            except Exception:
                pass
            return False
    
    def test_connection(self, timeout: int = 10) -> bool:
        if not self.config.is_email_configured():
            return False
        
        try:
            smtp_server = self.config.get('smtp_server', '')
            smtp_port = int(self.config.get('smtp_port', '465'))
            smtp_user = self.config.get('smtp_user', '')
            smtp_password = self.config.get('smtp_password', '')
            use_ssl = self.config.get('use_ssl', 'true').lower() == 'true'
            
            server = self._get_smtp_connection(smtp_server, smtp_port, use_ssl, timeout=timeout)
            try:
                server.login(smtp_user, smtp_password)
            finally:
                server.quit()
            
            return True
        except Exception:
            return False
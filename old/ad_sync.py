# -*- coding: utf-8 -*-
"""
ad_sync.py - AD域同步模块，处理用户创建、更新和禁用操作

作者：怡悦2011
日期：2026
"""
import os
import sys
import json
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ADSync:
    """
    AD域同步类
    
    封装所有与Windows AD域控制器交互的操作
    
    Attributes:
        domain: AD域名称（如：gf.cn）
        default_password: 新建用户的默认密码
        exclude_departments: 排除同步的部门列表
        exclude_accounts: 排除同步的账户列表
        force_change_password: 是否强制首次登录修改密码
        _ad_initialized: AD环境是否已初始化
    """
    
    def __init__(self, domain: str, default_password: str, 
                 exclude_departments: List[str] = None, 
                 exclude_accounts: List[str] = None, 
                 force_change_password: bool = True,
                 db: 'Database' = None):
        """
        初始化AD同步模块
        
        Args:
            domain: AD域名称
            default_password: 默认密码
            exclude_departments: 排除的部门列表
            exclude_accounts: 排除的账户列表
            force_change_password: 是否强制修改密码
            db: 数据库实例（用于记录操作日志）
        """
        self.domain = domain
        self.default_password = default_password
        self.exclude_departments = exclude_departments or []
        self.exclude_accounts = exclude_accounts or []
        self.force_change_password = force_change_password
        self._ad_initialized = False
        self.db = db  # 数据库实例，用于记录PowerShell命令日志

    def check_ad_module_available(self) -> bool:
        """
        检查Active Directory PowerShell模块是否可用
        
        Returns:
            bool: 如果AD模块可用返回True，否则返回False
        """
        try:
            command = "Get-Command Get-ADUser -ErrorAction SilentlyContinue"
            success, output = self.run_powershell(command)
            if success and output:
                logger.info("Active Directory PowerShell模块已安装")
                return True
            else:
                logger.warning("Active Directory PowerShell模块未安装或不可用")
                logger.warning("请确保已安装RSAT AD PowerShell工具")
                logger.warning("Windows 10/11: 设置 -> 应用 -> 可选功能 -> 添加功能 -> RSAT: Active Directory Domain Services and Lightweight Directory Tools")
                return False
        except Exception as e:
            logger.error(f"检查AD模块时出错: {str(e)}")
            return False

    def initialize_ad(self) -> bool:
        """初始化AD环境，仅在需要时调用"""
        if self._ad_initialized:
            return True
        
        try:
            # 先检查AD模块是否可用
            if not self.check_ad_module_available():
                logger.error("AD环境初始化失败: Active Directory模块不可用")
                return False
            
            self.init_powershell_encoding()
            self.ensure_disabled_users_ou()
            self._ad_initialized = True
            logger.info("AD环境初始化成功")
            return True
        except Exception as e:
            logger.error(f"AD环境初始化失败: {e}")
            return False

    def _ensure_ad_initialized(self):
        """确保AD已初始化，如果未初始化则自动初始化"""
        if not self._ad_initialized:
            self.initialize_ad()

    @staticmethod
    def escape_powershell_string(value: str) -> str:
        """转义PowerShell字符串中的特殊字符，防止注入攻击"""
        if not value:
            return ""
        # 替换反斜杠、双引号、反引号、美元符号等特殊字符
        # 注意：单引号在PowerShell单引号字符串中需要用两个单引号转义
        escaped = value.replace('`', '``')
        escaped = escaped.replace('$', '`$')
        escaped = escaped.replace('\\', '`\\')
        escaped = escaped.replace('"', '`"')
        escaped = escaped.replace("'", "''")
        return escaped

    def init_powershell_encoding(self):
        commands = [
            "$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8",
            "chcp 65001"
        ]
        for cmd in commands:
            self.run_powershell(cmd)

    def run_powershell(self, command: str) -> tuple:
        """执行单个PowerShell命令"""
        try:
            full_command = f"""
            $ErrorActionPreference = 'Stop'
            $OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
            [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
            try {{
                {command}
            }} catch {{
                Write-Error $_.Exception.Message
                exit 1
            }}
            """
            
            # 隐藏PowerShell窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.run(
                ["powershell", "-Command", full_command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                startupinfo=startupinfo
            )
            
            # 如果失败，返回错误信息
            if process.returncode != 0:
                error_msg = process.stderr.strip() if process.stderr else process.stdout.strip()
                return False, error_msg
            
            return True, process.stdout.strip()
        except Exception as e:
            logger.error(f"执行PowerShell命令失败: {str(e)}")
            return False, str(e)

    def run_powershell_batch(self, commands: list) -> tuple:
        """批量执行多个PowerShell命令，只启动一次PowerShell进程"""
        if not commands:
            return True, ""
        
        try:
            # 将多个命令合并为一个脚本块
            commands_block = "\n".join(commands)
            
            full_command = f"""
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$errorOccurred = $false

Write-Host "开始执行批量命令..."

{commands_block}

Write-Host "批量命令执行完成"

if ($errorOccurred) {{
    exit 1
}}
"""
            
            # 将命令写入日志文件
            self._log_powershell_command(full_command)
            
            logger.info(f"批量执行 {len(commands)} 条PowerShell命令")
            
            # 隐藏PowerShell窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.run(
                ["powershell", "-Command", full_command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                startupinfo=startupinfo
            )
            
            # 如果失败，返回错误信息
            if process.returncode != 0:
                error_msg = process.stderr.strip() if process.stderr else process.stdout.strip()
                logger.error(f"批量命令执行失败: {error_msg}")
                return False, error_msg
            
            # 记录命令输出
            if process.stdout:
                logger.info(f"命令执行输出: {process.stdout.strip()}")
            
            logger.info("批量命令执行成功")
            return True, process.stdout.strip()
        except Exception as e:
            logger.error(f"执行批量PowerShell命令失败: {str(e)}")
            return False, str(e)
    
    def _log_powershell_command(self, command: str):
        """
        将PowerShell命令记录到数据库
        
        Args:
            command: PowerShell命令内容
        """
        try:
            # 计算命令数量
            command_count = command.count('Write-Host')
            
            # 格式化日志消息
            message = f"执行PowerShell批量命令 (共{command_count}条)"
            
            # 将命令详情存入数据库
            if self.db:
                self.db.insert_operation_log(
                    log_level='DEBUG',
                    module='AD_SYNC',
                    message=message,
                    details=command[:1000] if len(command) > 1000 else command  # 限制详情长度
                )
            else:
                # 如果没有数据库实例，记录到标准输出
                print(f"[DEBUG] AD_SYNC: {message}")
                print(f"[DEBUG] 命令详情: {command[:200]}...")
                
            logger.info(f"PowerShell命令已记录: {message}")
        except Exception as e:
            logger.error(f"记录PowerShell命令日志失败: {str(e)}")

    def get_ou_dn(self, ou_path: List[str]) -> str:
        escaped_path = [self.escape_powershell_string(ou) for ou in ou_path]
        return ','.join([f"OU={ou}" for ou in reversed(escaped_path)]) + f',DC={self.domain.replace(".", ",DC=")}'

    def ou_exists(self, ou_dn: str) -> bool:
        escaped_ou_dn = self.escape_powershell_string(ou_dn)
        command = f"Get-ADOrganizationalUnit -Identity '{escaped_ou_dn}' -ErrorAction SilentlyContinue"
        success, _ = self.run_powershell(command)
        return success

    def create_ou(self, ou_name: str, parent_dn: str) -> bool:
        try:
            self._ensure_ad_initialized()
            if ou_name in self.exclude_departments:
                logger.info(f"跳过创建OU: {ou_name} (在排除列表中)")
                return True

            escaped_ou_name = self.escape_powershell_string(ou_name)
            escaped_parent_dn = self.escape_powershell_string(parent_dn)

            ou_dn = f"OU={escaped_ou_name},{escaped_parent_dn}"
            
            if not self.ou_exists(ou_dn):
                command = f"""
                New-ADOrganizationalUnit `
                    -Name "{escaped_ou_name}" `
                    -Path "{escaped_parent_dn}" `
                    -ProtectedFromAccidentalDeletion $false
                """
                success, output = self.run_powershell(command)
                if success:
                    logger.info(f"创建OU成功: {ou_name}")
                else:
                    logger.error(f"创建OU失败: {ou_name}, 错误: {output}")
                    return False
            else:
                logger.info(f"OU已存在: {ou_name}")
            
            # 检查安全组是否存在，不存在则创建
            group_command = f"""
            New-ADGroup `
                -Name "{escaped_ou_name}" `
                -GroupScope Global `
                -GroupCategory Security `
                -Path "{ou_dn}" `
                -ErrorAction SilentlyContinue
            """
            group_success, group_output = self.run_powershell(group_command)
            
            if group_success or "already exists" in str(group_output).lower():
                if "already exists" in str(group_output).lower():
                    logger.info(f"安全组已存在: {ou_name}")
                else:
                    logger.info(f"创建同名安全组成功: {ou_name}")
                return True
            else:
                logger.error(f"创建安全组失败: {ou_name}, 错误: {group_output}")
                return False
        except Exception as e:
            logger.error(f"创建OU过程出错: {str(e)}")
            return False

    def get_user(self, username: str) -> Optional[dict]:
        command = f"""
        Get-ADUser -Identity '{username}' -Properties * | 
        Select-Object * |
        ConvertTo-Json
        """
        success, output = self.run_powershell(command)
        if success and output:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return None
        return None

    def check_email_exists(self, email: str, exclude_user: str = None) -> bool:
        try:
            escaped_email = self.escape_powershell_string(email)
            escaped_exclude_user = self.escape_powershell_string(exclude_user) if exclude_user else ""
            command = f"""
            Get-ADUser -Filter {{Mail -eq '{escaped_email}' -and SamAccountName -ne '{escaped_exclude_user}'}} |
            Select-Object -First 1 |
            Select-Object -ExpandProperty SamAccountName
            """
            success, output = self.run_powershell(command)
            return success and bool(output.strip())
        except Exception as e:
            logger.error(f"检查邮箱是否存在时出错: {str(e)}")
            return False

    def get_user_email(self, username: str) -> str:
        try:
            escaped_username = self.escape_powershell_string(username)
            command = f"""
            Get-ADUser -Identity '{escaped_username}' -Properties Mail |
            Select-Object -ExpandProperty Mail
            """
            success, output = self.run_powershell(command)
            return output.strip() if success and output.strip() else ""
        except Exception as e:
            logger.error(f"获取用户邮箱失败 {username}: {str(e)}")
            return ""

    def create_user(self, username: str, display_name: str, email: str, ou_dn: str, group_name: str = None) -> bool:
        try:
            self._ensure_ad_initialized()
            escaped_username = self.escape_powershell_string(username)
            escaped_display_name = self.escape_powershell_string(display_name)
            escaped_email = self.escape_powershell_string(email)
            escaped_ou_dn = self.escape_powershell_string(ou_dn)
            escaped_password = self.escape_powershell_string(self.default_password)
            
            # 构建 UserPrincipalName (UPN)，格式为 username@ad_domain
            upn = f"{username}@{self.domain}"
            escaped_upn = self.escape_powershell_string(upn)

            command = f"""
            $securePassword = ConvertTo-SecureString -String '{escaped_password}' -AsPlainText -Force
            New-ADUser `
                -SamAccountName '{escaped_username}' `
                -UserPrincipalName '{escaped_upn}' `
                -Name '{escaped_display_name}' `
                -DisplayName '{escaped_display_name}' `
                -EmailAddress '{escaped_email}' `
                -Enabled $true `
                -Path '{escaped_ou_dn}' `
                -AccountPassword $securePassword `
                -ChangePasswordAtLogon $true
            """

            success, output = self.run_powershell(command)
            if success:
                logger.info(f"创建用户成功: {username} ({display_name})")
                
                # 如果指定了部门名称，将用户添加到部门安全组
                if group_name:
                    self.add_user_to_group(username, group_name)
                
                return True
            else:
                logger.error(f"创建用户失败: {username} ({display_name}), 错误: {output}")
                return False
        except Exception as e:
            logger.error(f"创建用户过程出错: {str(e)}")
            return False

    def update_user(self, username: str, display_name: str, email: str, ou_dn: str, group_name: str = None) -> bool:
        try:
            self._ensure_ad_initialized()
            escaped_username = self.escape_powershell_string(username)
            escaped_display_name = self.escape_powershell_string(display_name)
            escaped_email = self.escape_powershell_string(email)
            escaped_ou_dn = self.escape_powershell_string(ou_dn)

            current_email = self.get_user_email(username)

            if current_email:
                logger.info(f"用户 {username} 已有邮箱 {current_email}，保持不变")
                command = f"""
                Get-ADUser -Identity '{escaped_username}' | 
                Set-ADUser `
                    -DisplayName '{escaped_display_name}'
                """
            else:
                logger.info(f"用户 {username} 无邮箱，设置新邮箱: {email}")
                command = f"""
                Get-ADUser -Identity '{escaped_username}' | 
                Set-ADUser `
                    -DisplayName '{escaped_display_name}' `
                    -EmailAddress '{escaped_email}'
                """

            success, output = self.run_powershell(command)

            if success:
                move_command = f"""
                Move-ADObject `
                    -Identity (Get-ADUser -Identity '{escaped_username}').DistinguishedName `
                    -TargetPath '{escaped_ou_dn}'
                """
                move_success, move_output = self.run_powershell(move_command)

                if move_success:
                    logger.info(f"更新用户成功: {username} ({display_name})")
                    
                    # 如果指定了部门名称，将用户添加到部门安全组
                    if group_name:
                        self.add_user_to_group(username, group_name)
                    
                    return True
                else:
                    logger.error(f"移动用户失败: {username}, 错误: {move_output}")
            else:
                logger.error(f"更新用户信息失败: {username}, 错误: {output}")
            return False
        except Exception as e:
            logger.error(f"更新用户过程出错: {str(e)}")
            return False

    def add_user_to_group(self, username: str, group_name: str) -> bool:
        try:
            self._ensure_ad_initialized()
            escaped_username = self.escape_powershell_string(username)
            escaped_group_name = self.escape_powershell_string(group_name)

            command = f"""
            Add-ADGroupMember `
                -Identity '{escaped_group_name}' `
                -Members '{escaped_username}' `
                -ErrorAction SilentlyContinue
            """
            success, output = self.run_powershell(command)

            if success:
                logger.info(f"添加用户到组成功: {username} -> {group_name}")
                return True
            else:
                logger.error(f"添加用户到组失败: {username} -> {group_name}, 错误: {output}")
                return False
        except Exception as e:
            logger.error(f"添加用户到组过程出错: {str(e)}")
            return False

    def get_all_enabled_users(self) -> List[str]:
        try:
            exclude_accounts = '|'.join([self.escape_powershell_string(acc) for acc in self.exclude_accounts])
            command = f"""
            Get-ADUser -Filter {{Enabled -eq $true}} -Properties SamAccountName |
            Where-Object {{
                $_.SamAccountName -notmatch '^({exclude_accounts})$' -and
                $_.SamAccountName -notlike '*$'
            }} |
            Select-Object -ExpandProperty SamAccountName |
            ConvertTo-Json
            """
            success, output = self.run_powershell(command)
            if success and output:
                try:
                    return json.loads(output)
                except json.JSONDecodeError:
                    logger.error("解析AD用户列表失败")
                    return []
            return []
        except Exception as e:
            logger.error(f"获取AD用户列表失败: {str(e)}")
            return []

    def is_user_active(self, username: str) -> bool:
        try:
            escaped_username = self.escape_powershell_string(username)
            command = f"""
            (Get-ADUser -Identity '{escaped_username}' -Properties Enabled).Enabled
            """
            success, output = self.run_powershell(command)
            return success and output.strip().lower() == 'true'
        except Exception as e:
            logger.error(f"检查用户状态失败 {username}: {str(e)}")
            return False

    def disable_user(self, username: str) -> bool:
        try:
            self._ensure_ad_initialized()
            if not self.ensure_disabled_users_ou():
                logger.error("无法确保 Disabled Users OU 存在，禁用用户操作可能会失败")

            if not self.is_user_active(username):
                logger.info(f"用户 {username} 已经处于禁用状态或不存在")
                return True

            escaped_username = self.escape_powershell_string(username)
            disable_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            disable_command = f"""
            $user = Get-ADUser -Identity '{escaped_username}'
            if ($user) {{
                Disable-ADAccount -Identity $user
                Set-ADUser -Identity $user `
                    -Description "Account disabled - Not found in WeChat Work - {disable_time}"
                Write-Output "Success"
            }} else {{
                Write-Error "User not found"
            }}
            """
            success, output = self.run_powershell(disable_command)

            if success and "Success" in output:
                logger.info(f"成功禁用账户: {username}")
                disabled_ou = f"OU=Disabled Users,DC={self.domain.replace('.', ',DC=')}"
                move_command = f"""
                $user = Get-ADUser -Identity '{escaped_username}'
                if ($user) {{
                    Move-ADObject -Identity $user.DistinguishedName -TargetPath '{disabled_ou}'
                    Write-Output "Moved"
                }}
                """
                move_success, _ = self.run_powershell(move_command)
                if move_success:
                    logger.info(f"已将禁用账户 {username} 移动到 Disabled Users OU")
                return True
            else:
                logger.error(f"禁用账户失败 {username}: {output}")
                return False
        except Exception as e:
            logger.error(f"禁用账户过程出错 {username}: {str(e)}")
            return False

    def get_user_details(self, username: str) -> Dict:
        try:
            command = f"""
            Get-ADUser -Identity '{username}' -Properties DisplayName, Mail, Created, Modified, LastLogonDate, Description |
            Select-Object SamAccountName, DisplayName, Mail, Created, Modified, LastLogonDate, Description |
            ConvertTo-Json
            """
            success, output = self.run_powershell(command)
            if success and output:
                try:
                    return json.loads(output)
                except json.JSONDecodeError:
                    return {}
            return {}
        except Exception as e:
            logger.error(f"获取用户详情失败: {str(e)}")
            return {}

    def sync_user_status(self, db_usernames: List[str]) -> tuple:
        """
        同步用户状态：查询AD域用户与数据库比对，禁用不在数据库中的用户
        :param db_usernames: 数据库中的用户名列表
        :return: (success, message)
        """
        self._ensure_ad_initialized()
        
        try:
            # 获取AD域中的所有启用用户（排除系统用户）
            ad_users = self.get_all_enabled_users()
            
            if not ad_users:
                return True, "未找到AD域中的用户"
            
            # 转换为小写以便比较
            db_usernames_lower = {u.lower() for u in db_usernames}
            exclude_accounts_lower = {a.lower() for a in self.exclude_accounts}
            
            # 找出AD中有但数据库中没有且不在排除列表中的用户
            users_to_disable = []
            for ad_user in ad_users:
                username_lower = ad_user.lower()
                if username_lower not in db_usernames_lower and username_lower not in exclude_accounts_lower:
                    users_to_disable.append(ad_user)
            
            if not users_to_disable:
                return True, "没有需要禁用的用户"
            
            # 批量禁用用户
            disabled_count = 0
            failed_count = 0
            
            for username in users_to_disable:
                if self.disable_user(username):
                    disabled_count += 1
                else:
                    failed_count += 1
            
            message = f"用户状态同步完成: {disabled_count} 个用户被禁用, {failed_count} 个禁用失败"
            logger.info(message)
            return True, message
            
        except Exception as e:
            error_msg = f"同步用户状态失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def batch_create_ous(self, departments: list) -> tuple:
        """批量创建多个OU和安全组，只调用一次PowerShell"""
        self._ensure_ad_initialized()
        
        commands = []
        created_count = 0
        skipped_count = 0
        
        for dept in departments:
            ou_name = dept['name']
            parent_dn = dept['parent_dn']
            
            if ou_name in self.exclude_departments:
                logger.info(f"跳过创建OU: {ou_name} (在排除列表中)")
                skipped_count += 1
                continue
            
            escaped_ou_name = self.escape_powershell_string(ou_name)
            # parent_dn 已经在 get_ou_dn 中处理过，不需要再次转义
            ou_dn = f"OU={escaped_ou_name},{parent_dn}"
            
            # 创建OU命令（使用Filter检查是否存在，避免错误）
            commands.append(f"""
$ouExists = Get-ADObject -Filter "distinguishedName -eq '{ou_dn}'" -ErrorAction SilentlyContinue
if (-not $ouExists) {{
    New-ADOrganizationalUnit -Name '{escaped_ou_name}' -Path '{parent_dn}' -ProtectedFromAccidentalDeletion $false
    Write-Host "Created OU: {ou_name}"
}} else {{
    Write-Host "OU exists: {ou_name}"
}}
""")
            
            # 创建安全组命令（使用Filter检查是否存在）
            commands.append(f"""
$groupExists = Get-ADObject -Filter "Name -eq '{escaped_ou_name}' -and objectClass -eq 'group'" -ErrorAction SilentlyContinue
if (-not $groupExists) {{
    New-ADGroup -Name '{escaped_ou_name}' -GroupScope Global -GroupCategory Security -Path '{ou_dn}'
    Write-Host "Created group: {ou_name}"
}} else {{
    Write-Host "Group exists: {ou_name}"
}}
""")
            
            # 如果不是顶级部门，设置隶属于上级安全组
            # 顶级部门的 parent_dn 是 DC=xxx 格式，子部门的 parent_dn 包含 OU=xxx
            if 'OU=' in parent_dn:
                # 从 parent_dn 中提取上级部门名称
                parent_group_name = parent_dn.split(',')[0].replace('OU=', '')
                escaped_parent_group_name = self.escape_powershell_string(parent_group_name)
                commands.append(f"""
# 将当前部门安全组添加到上级部门安全组
Add-ADGroupMember -Identity '{escaped_parent_group_name}' -Members '{escaped_ou_name}' -ErrorAction Ignore
Write-Host "Added group {ou_name} to parent group: {parent_group_name}"
""")
            
            created_count += 1
        
        if not commands:
            return True, f"没有需要创建的OU ({skipped_count} 个跳过)"
        
        success, output = self.run_powershell_batch(commands)
        
        if success:
            return True, f"批量创建完成: {created_count} 个OU/组创建成功, {skipped_count} 个跳过"
        else:
            return False, f"批量创建失败: {output}"

    def batch_create_users(self, users: list) -> tuple:
        """批量创建/更新多个用户，只调用一次PowerShell"""
        self._ensure_ad_initialized()
        
        commands = []
        created_count = 0
        updated_count = 0
        
        for user in users:
            username = user['username']
            display_name = user['display_name']
            email = user['email']
            ou_dn = user['ou_dn']
            group_name = user.get('group_name')
            
            escaped_username = self.escape_powershell_string(username)
            escaped_display_name = self.escape_powershell_string(display_name)
            escaped_email = self.escape_powershell_string(email)
            # ou_dn 已经在 get_ou_dn 中处理过，不需要再次转义
            escaped_password = self.escape_powershell_string(self.default_password)
            upn = f"{username}@{self.domain}"
            escaped_upn = self.escape_powershell_string(upn)
            
            # 检查用户是否存在并创建或更新（使用 Filter 检查，避免错误）
            commands.append(f"""
$userExists = Get-ADObject -Filter "SamAccountName -eq '{escaped_username}' -and objectClass -eq 'user'" -Properties DistinguishedName,Mail -ErrorAction SilentlyContinue
if (-not $userExists) {{
    $securePassword = ConvertTo-SecureString -String '{escaped_password}' -AsPlainText -Force
    New-ADUser -SamAccountName '{escaped_username}' -UserPrincipalName '{escaped_upn}' -Name '{escaped_display_name}' -DisplayName '{escaped_display_name}' -EmailAddress '{escaped_email}' -Enabled $true -Path '{ou_dn}' -AccountPassword $securePassword -ChangePasswordAtLogon ${str(self.force_change_password).lower()}
    Write-Host "Created user: {username}"
}} else {{
    # 更新用户信息
    Set-ADUser -Identity '{escaped_username}' -DisplayName '{escaped_display_name}' -ErrorAction SilentlyContinue
    if (-not $userExists.Mail) {{
        Set-ADUser -Identity '{escaped_username}' -EmailAddress '{escaped_email}' -ErrorAction SilentlyContinue
    }}
    
    # 检查是否需要移动用户（只有当前位置不同时才移动）
    if ($userExists.DistinguishedName -notlike "*{ou_dn}") {{
        Move-ADObject -Identity $userExists.DistinguishedName -TargetPath '{ou_dn}' -ErrorAction SilentlyContinue
        Write-Host "Moved user: {username} to OU: {ou_dn}"
    }}
    
    Write-Host "Updated user: {username}"
}}
""")
            
            # 添加到部门安全组（使用 Ignore 完全忽略错误）
            if group_name:
                escaped_group_name = self.escape_powershell_string(group_name)
                commands.append(f"""
Add-ADGroupMember -Identity '{escaped_group_name}' -Members '{escaped_username}' -ErrorAction Ignore
Write-Host "Added {username} to group: {group_name}"
""")
            
            if user.get('is_new', False):
                created_count += 1
            else:
                updated_count += 1
        
        if not commands:
            return True, "没有需要同步的用户"
        
        success, output = self.run_powershell_batch(commands)
        
        if success:
            return True, f"批量用户同步完成: {created_count} 个新建, {updated_count} 个更新"
        else:
            return False, f"批量用户同步失败: {output}"

    def ensure_disabled_users_ou(self) -> bool:
        try:
            disabled_ou = f"OU=Disabled Users,DC={self.domain.replace('.', ',DC=')}"
            if not self.ou_exists(disabled_ou):
                logger.info("Disabled Users OU 不存在，正在创建...")
                command = f"""
                New-ADOrganizationalUnit `
                    -Name "Disabled Users" `
                    -Path "DC={self.domain.replace('.', ',DC=')}" `
                    -Description "存放已禁用的用户账户" `
                    -ProtectedFromAccidentalDeletion $false
                """
                success, output = self.run_powershell(command)
                if success:
                    logger.info("成功创建 Disabled Users OU")
                    return True
                else:
                    logger.error(f"创建 Disabled Users OU 失败: {output}")
                    return False
            else:
                logger.info("Disabled Users OU 已存在")
                return True
        except Exception as e:
            logger.error(f"检查/创建 Disabled Users OU 时出错: {str(e)}")
            return False

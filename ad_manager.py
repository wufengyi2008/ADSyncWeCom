import subprocess
import re
import os
import json
import base64
from typing import List, Dict, Optional, Tuple, Any
import win32net
import win32netcon
import win32api
import win32security
from database import Database
from config_manager import ConfigManager

class ADManager:
    def __init__(self) -> None:
        self.db = Database()
        self.config = ConfigManager()
    
    def _clean_name(self, name: str) -> str:
        cleaned = name.replace(' ', '').replace('-', '').replace('_', '')
        cleaned = ''.join(c for c in cleaned if c.isalnum())
        return cleaned[:20]
    
    def _run_powershell(self, script: str) -> str:
        try:
            encoded_script = base64.b64encode(script.encode('utf-16-le')).decode('utf-8')
            
            powershell_paths = [
                r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
                r'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe',
                'powershell.exe'
            ]
            
            powershell_path = None
            for path in powershell_paths:
                if os.path.exists(path):
                    powershell_path = path
                    break
            
            if not powershell_path:
                raise Exception('无法找到PowerShell可执行文件')
            
            command = [powershell_path, '-EncodedCommand', encoded_script]
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                startupinfo=startupinfo
            )
            
            stdout = result.stdout if result.stdout else ''
            stderr = result.stderr if result.stderr else ''
            
            self._log_command(script, result.returncode, stdout, stderr)
            
            if result.returncode != 0:
                error_msg = f'PowerShell执行失败 (路径: {powershell_path}, 返回码: {result.returncode})'
                if stderr:
                    error_msg += f': {stderr}'
                else:
                    error_msg += ': 无错误信息'
                raise Exception(error_msg)
            
            return stdout
        except subprocess.TimeoutExpired:
            self._log_command(script, -1, '', 'PowerShell命令执行超时')
            raise Exception('PowerShell命令执行超时')
        except Exception as e:
            self._log_command(script, -1, '', str(e))
            raise e
    
    def _log_command(self, script: str, return_code: int, stdout: str, stderr: str) -> None:
        stdout_text = stdout[:500] if stdout else ''
        stderr_text = stderr[:500] if stderr else ''
        self.db.log_operation('AD_COMMAND', 'PowerShell', f'Script: {script[:200]}\nReturnCode: {return_code}\nStdout: {stdout_text}\nStderr: {stderr_text}')
    
    def test_connection(self) -> bool:
        domain = self.config.get('domain')
        if not domain:
            raise Exception('AD域配置未完成')
        
        script = f'''
            try {{
                Get-ADDomain -Identity {domain} -ErrorAction Stop
                Write-Output "Success"
            }} catch {{
                Write-Error $_.Exception.Message
            }}
        '''
        result = self._run_powershell(script)
        return 'Success' in result
    
    def check_ad_environment(self) -> Dict[str, Any]:
        domain = self.config.get('domain')
        if not domain:
            return {'success': False, 'message': 'AD域配置未完成，请先配置AD域名'}
        
        try:
            script = '$env:USERDNSDOMAIN'
            result = self._run_powershell(script)
            
            if result and result.strip():
                user_domain = result.strip()
                if user_domain.upper() == domain.upper() or domain.upper() in user_domain.upper():
                    return {'success': True, 'message': f'AD域环境检测成功: 当前用户已加入域 {user_domain}'}
                else:
                    return {'success': True, 'message': f'AD域环境检测成功: 当前用户加入的域为 {user_domain}'}
            else:
                script = 'nltest /dsgetdc:' + domain
                result = self._run_powershell(script)
                
                if result and 'DC=' in result:
                    return {'success': True, 'message': 'AD域环境检测成功: 成功找到域控制器'}
                else:
                    return {'success': False, 'message': 'AD域环境检测失败: 无法检测到AD域环境，请确认计算机已加入域'}
        except Exception as e:
            return {'success': False, 'message': f'AD域环境检测失败: {str(e)}'}
    
    def create_ou(self, ou_name: str, parent_dn: str) -> str:
        script = f'''
            $ouPath = "OU={ou_name},{parent_dn}"
            if (-not (Get-ADOrganizationalUnit -Filter {{Name -eq "{ou_name}"}} -SearchBase "{parent_dn}" -ErrorAction SilentlyContinue)) {{
                New-ADOrganizationalUnit -Name "{ou_name}" -Path "{parent_dn}" -ProtectedFromAccidentalDeletion $false
                Write-Output "Created"
            }} else {{
                Write-Output "Exists"
            }}
        '''
        return self._run_powershell(script)
    
    def create_security_group(self, group_name: str, parent_dn: str, member_of: Optional[str] = None) -> str:
        script = f'''
            $groupPath = "CN={group_name},{parent_dn}"
            if (-not (Get-ADGroup -Filter {{Name -eq "{group_name}"}} -SearchBase "{parent_dn}" -ErrorAction SilentlyContinue)) {{
                New-ADGroup -Name "{group_name}" -SamAccountName "{group_name}" -GroupCategory Security -GroupScope Global -Path "{parent_dn}"
                Write-Output "Created"
            }} else {{
                Write-Output "Exists"
            }}
        '''
        result = self._run_powershell(script)
        
        if member_of and 'Created' in result:
            self.add_group_to_group(group_name, member_of, parent_dn)
        
        return result
    
    def add_group_to_group(self, child_group: str, parent_group: str, parent_dn: str) -> str:
        script = f'''
            $child = Get-ADGroup -Filter {{Name -eq "{child_group}"}} -SearchBase "{parent_dn}"
            $parent = Get-ADGroup -Filter {{Name -eq "{parent_group}"}}
            if ($child -and $parent) {{
                Add-ADGroupMember -Identity $parent -Members $child
                Write-Output "Added"
            }}
        '''
        return self._run_powershell(script)
    
    def create_user(self, name: str, sam_account_name: str, parent_dn: str, password: str, 
                   email: Optional[str] = None, position: Optional[str] = None, 
                   force_change_pwd: bool = True) -> str:
        escaped_password = password.replace('"', '\\"')
        change_pwd_at_logon = '$true' if force_change_pwd else '$false'
        
        email_param = f'-EmailAddress "{email}"' if email else ''
        display_name_param = f'-DisplayName "{name}"'
        
        script = f'''
            $password = ConvertTo-SecureString "{escaped_password}" -AsPlainText -Force
            
            $existingUser = Get-ADUser -Filter {{SamAccountName -eq "{sam_account_name}"}} -ErrorAction SilentlyContinue
            if (-not $existingUser) {{
                try {{
                    New-ADUser -Name "{name}" -SamAccountName "{sam_account_name}" -UserPrincipalName "{sam_account_name}@{self.config.get("domain")}" -AccountPassword $password -Enabled $true -ChangePasswordAtLogon {change_pwd_at_logon} -Path "{parent_dn}" {display_name_param} {email_param} -ErrorAction Stop
                    $newUser = Get-ADUser -Identity "{sam_account_name}" -ErrorAction Stop
                    Write-Output "Created at: $($newUser.DistinguishedName)"
                }} catch {{
                    $errorMsg = $_.Exception.Message
                    Write-Error "CreateUserError: $errorMsg"
                    Write-Output "Failed: $errorMsg"
                }}
            }} else {{
                Write-Output "Exists at: $($existingUser.DistinguishedName)"
            }}
        '''
        result = self._run_powershell(script)
        
        if 'Created' in result and 'Failed' not in result:
            if position:
                self.update_user_attribute(sam_account_name, 'Title', position)
        
        return result
    
    def get_ou_dn(self, ou_name: str) -> Optional[str]:
        script = f'''
            try {{
                $ou = Get-ADOrganizationalUnit -Filter {{Name -eq "{ou_name}"}} -ErrorAction Stop
                Write-Output $ou.DistinguishedName
            }} catch {{
                Write-Output ""
            }}
        '''
        result = self._run_powershell(script).strip()
        return result if result else None
    
    def check_ou_exists(self, ou_name: str) -> Tuple[bool, Optional[str]]:
        ou_dn = self.get_ou_dn(ou_name)
        if ou_dn:
            return True, ou_dn
        return False, None
    
    def update_user(self, sam_account_name: str, name: Optional[str] = None, 
                    email: Optional[str] = None, position: Optional[str] = None) -> str:
        updates = []
        if name:
            updates.append(f'-Name "{name}"')
        if email:
            updates.append(f'-EmailAddress "{email}"')
        if position:
            updates.append(f'-Title "{position}"')
        
        if not updates:
            return 'No changes'
        
        update_str = ' '.join(updates)
        script = f'''
            Set-ADUser -Identity "{sam_account_name}" {update_str}
            Write-Output "Updated"
        '''
        return self._run_powershell(script)
    
    def update_user_attribute(self, sam_account_name: str, attribute: str, value: str) -> str:
        escaped_value = value.replace('"', '\\"')
        script = f'''
            Set-ADUser -Identity "{sam_account_name}" -Replace @{{{attribute}="{escaped_value}"}}
            Write-Output "Updated"
        '''
        return self._run_powershell(script)
    
    def disable_user(self, sam_account_name: str) -> str:
        script = f'''
            Disable-ADAccount -Identity "{sam_account_name}"
            Write-Output "Disabled"
        '''
        return self._run_powershell(script)
    
    def move_user_to_disabled_ou(self, sam_account_name: str, disabled_ou_dn: str) -> str:
        script = f'''
            Move-ADObject -Identity (Get-ADUser "{sam_account_name}") -TargetPath "{disabled_ou_dn}"
            Write-Output "Moved"
        '''
        return self._run_powershell(script)
    
    def add_user_to_group(self, sam_account_name: str, group_name: str) -> str:
        script = f'''
            Add-ADGroupMember -Identity "{group_name}" -Members "{sam_account_name}"
            Write-Output "Added"
        '''
        return self._run_powershell(script)
    
    def get_all_ad_users(self) -> List[Dict[str, str]]:
        users = []
        try:
            domain = self.config.get('domain', '')
            if not domain:
                self.db.log_operation('SYNC_ERROR', 'AD_STATUS', 'AD域配置未完成')
                return []
            
            level = 2
            resume_handle = 0
            
            while True:
                try:
                    data = win32net.NetUserEnum(domain, level, win32netcon.FILTER_NORMAL_ACCOUNT, resume_handle)
                    user_info = data[0]
                    resume_handle = data[2]
                    
                    for user in user_info:
                        sam_account_name = user.get('name', '')
                        full_name = user.get('full_name', '')
                        if sam_account_name:
                            users.append({
                                'sam_account_name': sam_account_name,
                                'name': full_name
                            })
                    
                    if resume_handle == 0:
                        break
                except Exception:
                    break
            
            self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'使用pywin32成功获取 {len(users)} 个AD用户')
            return users
            
        except Exception as e:
            self.db.log_operation('SYNC_ERROR', 'AD_STATUS', f'获取AD用户失败: {str(e)}')
            return []
    
    def get_all_ad_groups(self) -> List[Dict[str, str]]:
        script = '''
            Get-ADGroup -Filter * -Properties Name, SamAccountName | Select-Object Name, SamAccountName
        '''
        try:
            result = self._run_powershell(script)
            self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'安全组查询原始输出: {result[:500]}')
        except Exception as e:
            self.db.log_operation('SYNC_ERROR', 'AD_STATUS', f'获取AD安全组失败: {str(e)}')
            return []
        
        groups = []
        lines = result.strip().split('\n')
        self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'安全组查询解析行数: {len(lines)}, 跳过前3行后剩余: {len(lines[3:]) if len(lines) > 3 else 0}')
        
        for line in lines[3:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                groups.append({
                    'name': parts[1].strip(),
                    'sam_account_name': parts[0].strip()
                })
        
        self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'安全组解析结果: {len(groups)} 个安全组')
        return groups
    
    def get_all_ad_ous(self) -> List[Dict[str, str]]:
        script = '''
            Get-ADOrganizationalUnit -Filter * -Properties Name, DistinguishedName | Select-Object Name, DistinguishedName
        '''
        try:
            result = self._run_powershell(script)
            self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'OU查询原始输出: {result[:500]}')
        except Exception as e:
            self.db.log_operation('SYNC_ERROR', 'AD_STATUS', f'获取AD OU失败: {str(e)}')
            return []
        
        ous = []
        lines = result.strip().split('\n')
        self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'OU查询解析行数: {len(lines)}, 跳过前3行后剩余: {len(lines[3:]) if len(lines) > 3 else 0}')
        
        for line in lines[3:]:
            line = line.strip()
            if not line:
                continue
            
            match = re.match(r'^(.+?)\s+(OU=|DC=)', line)
            if match:
                ou_name = match.group(1).strip()
                dn_start = match.start(2)
                dn = line[dn_start:].strip()
                ous.append({
                    'name': ou_name,
                    'dn': dn
                })
        
        ou_list_str = '\n'.join([f"  {ou['name']} -> {self._clean_name(ou['name']).lower()}" for ou in ous])
        self.db.log_operation('SYNC_DEBUG', 'AD_STATUS', f'OU解析结果: {len(ous)} 个OU\n{ou_list_str}')
        return ous
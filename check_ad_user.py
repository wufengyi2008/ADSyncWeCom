import subprocess
import sys

# 检查AD中是否有叶莉用户
script = '''
Import-Module ActiveDirectory
Get-ADUser -Filter {Name -like "*叶莉*"} | Select-Object Name, SamAccountName, DistinguishedName
'''

powershell_path = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'

result = subprocess.run(
    [powershell_path, '-Command', script],
    capture_output=True,
    text=True,
    timeout=30
)

print("Stdout:")
print(result.stdout)
print("\nStderr:")
print(result.stderr)
print("\nReturnCode:", result.returncode)
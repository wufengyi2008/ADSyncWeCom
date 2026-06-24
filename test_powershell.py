import subprocess

def test_powershell():
    script = '''
        $result = @{}
        $result['DomainAvailable'] = $false
        $result['ErrorMessage'] = ""
        
        $currentDomain = $env:USERDNSDOMAIN
        if ($currentDomain -and $currentDomain -ne "") {
            $result['DomainAvailable'] = $true
            $result['ErrorMessage'] = "当前用户已加入域: $currentDomain"
        }
        
        $result | ConvertTo-Json
    '''
    
    encoded_script = script.encode('utf-16-le').hex()
    powershell_path = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    command = [powershell_path, '-EncodedCommand', encoded_script]
    
    print(f"Command: {command}")
    print(f"Encoded script length: {len(encoded_script)}")
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            startupinfo=startupinfo
        )
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == '__main__':
    test_powershell()
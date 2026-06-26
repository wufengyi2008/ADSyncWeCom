import subprocess
import sys
import os

def build_main():
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'ADSyncWeCom',
        '--hidden-import', 'sync_service',
        '--hidden-import', 'ad_manager',
        '--hidden-import', 'wecom_api',
        '--hidden-import', 'config_manager',
        '--hidden-import', 'database',
        '--hidden-import', 'logger',
        '--hidden-import', 'auth',
        '--hidden-import', 'gui',
        '--hidden-import', 'hardware_info',
        '--hidden-import', 'email_service',
        '--hidden-import', 'password_utils',
        '--hidden-import', 'pysqlcipher3',
        'main.py'
    ]
    
    if os.path.exists('icon.ico'):
        cmd.insert(5, '--icon')
        cmd.insert(6, 'icon.ico')
    
    subprocess.run(cmd, check=True)

def build_auth_generator():
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'AuthGenerator',
        'auth_generator.py'
    ]
    
    subprocess.run(cmd, check=True)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'auth':
        build_auth_generator()
    else:
        build_main()

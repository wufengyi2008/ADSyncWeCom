import subprocess
import hashlib
import platform

class HardwareInfo:
    def __init__(self):
        self.cpu_info = ""
        self.motherboard_info = ""
        self.disk_info = ""
        self.mac_address = ""
    
    def _run_command(self, cmd):
        try:
            result = subprocess.run(cmd, capture_output=True, shell=True)
            raw_output = result.stdout
            
            encodings = ['utf-8', 'gbk', 'gb2312', 'cp1252']
            output = ""
            
            for encoding in encodings:
                try:
                    output = raw_output.decode(encoding).strip()
                    break
                except:
                    continue
            
            return output
        except Exception:
            return ""
    
    def get_cpu_info(self):
        if platform.system() == "Windows":
            output = self._run_command('wmic cpu get ProcessorId /value')
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('ProcessorId='):
                    return line.split('=')[1].strip()
        return ""
    
    def get_motherboard_info(self):
        if platform.system() == "Windows":
            output = self._run_command('wmic baseboard get SerialNumber /value')
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('SerialNumber='):
                    return line.split('=')[1].strip()
        return ""
    
    def get_disk_info(self):
        if platform.system() == "Windows":
            output = self._run_command('wmic diskdrive get SerialNumber /value')
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('SerialNumber='):
                    return line.split('=')[1].strip()
        return ""
    
    def get_mac_address(self):
        if platform.system() == "Windows":
            output = self._run_command('wmic nic get MACAddress /value')
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('MACAddress=') and ':' in line:
                    return line.split('=')[1].strip()
        return ""
    
    def collect_all_info(self):
        self.cpu_info = self.get_cpu_info()
        self.motherboard_info = self.get_motherboard_info()
        self.disk_info = self.get_disk_info()
        self.mac_address = self.get_mac_address()
    
    def generate_serial_number(self):
        self.collect_all_info()
        
        raw_data = f"{self.cpu_info}{self.motherboard_info}{self.disk_info}{self.mac_address}"
        
        if not raw_data or raw_data.isspace():
            fallback_data = f"{platform.node()}{platform.processor()}{platform.system()}{platform.version()}"
            if fallback_data and not fallback_data.isspace():
                raw_data = fallback_data
            else:
                raise Exception("无法获取硬件信息")
        
        first_hash = hashlib.sha256(raw_data.encode('utf-8')).hexdigest()
        
        second_hash = hashlib.sha384(first_hash.encode('utf-8')).hexdigest()
        
        third_hash = hashlib.md5(second_hash.encode('utf-8')).hexdigest()
        
        serial = third_hash[:16].upper()
        
        formatted_serial = '-'.join([serial[i:i+4] for i in range(0, len(serial), 4)])
        
        return formatted_serial, {
            'cpu': self.cpu_info,
            'motherboard': self.motherboard_info,
            'disk': self.disk_info,
            'mac': self.mac_address
        }

if __name__ == "__main__":
    hw = HardwareInfo()
    try:
        serial, details = hw.generate_serial_number()
        print(f"生成的序列号: {serial}")
        print("硬件详情:")
        print(f"  CPU: {details['cpu']}")
        print(f"  主板: {details['motherboard']}")
        print(f"  硬盘: {details['disk']}")
        print(f"  MAC: {details['mac']}")
    except Exception as e:
        print(f"错误: {e}")
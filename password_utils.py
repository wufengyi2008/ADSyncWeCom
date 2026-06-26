import random
import string


def generate_secure_password(length: int = 12) -> str:
    """
    生成符合安全要求的随机密码
    - 包含大小写字母
    - 包含数字
    - 包含特殊符号
    - 至少8位（默认12位）
    """
    if length < 8:
        length = 8
    
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(special_chars),
    ]
    
    all_chars = lowercase + uppercase + digits + special_chars
    for _ in range(length - 4):
        password.append(random.choice(all_chars))
    
    random.shuffle(password)
    
    return ''.join(password)


def validate_password(password: str) -> bool:
    """
    验证密码是否符合安全要求
    - 至少8位
    - 包含大小写字母
    - 包含数字
    - 包含特殊符号
    """
    if len(password) < 8:
        return False
    
    has_lower = any(c in string.ascii_lowercase for c in password)
    has_upper = any(c in string.ascii_uppercase for c in password)
    has_digit = any(c in string.digits for c in password)
    special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    has_special = any(c in special_chars for c in password)
    
    return has_lower and has_upper and has_digit and has_special
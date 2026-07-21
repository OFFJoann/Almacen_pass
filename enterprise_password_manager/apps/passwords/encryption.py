import os
import base64
import hashlib
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from django.conf import settings


def derive_key(master_key: bytes, salt: bytes) -> bytes:
    kdf = Argon2id(
        salt=salt,
        length=32,
        memory_cost=19456,
        iterations=2,
        lanes=1,
    )
    return kdf.derive(master_key)


def encrypt_data(plaintext: str, master_key: bytes = None) -> dict:
    if master_key is None:
        master_key = settings.SECRET_KEY.encode()[:32].ljust(32, b'\0')
    salt = os.urandom(16)
    key = derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return {
        'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
        'nonce': base64.b64encode(nonce).decode('utf-8'),
        'salt': base64.b64encode(salt).decode('utf-8'),
    }


def decrypt_data(ciphertext: str, nonce: str, salt: str, master_key: bytes = None) -> str:
    if master_key is None:
        master_key = settings.SECRET_KEY.encode()[:32].ljust(32, b'\0')
    key = derive_key(master_key, base64.b64decode(salt))
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(
        base64.b64decode(nonce),
        base64.b64decode(ciphertext),
        None
    )
    return plaintext.decode('utf-8')


def encrypt_field(plaintext: str) -> dict:
    return encrypt_data(plaintext)


def decrypt_field(ciphertext: str, nonce: str, salt: str) -> str:
    return decrypt_data(ciphertext, nonce, salt)


def generate_password(length=20, use_upper=True, use_lower=True, use_digits=True,
                       use_symbols=True, exclude_similar=False, exclude_ambiguous=False):
    import secrets
    import string

    chars = ''
    if use_upper:
        chars += string.ascii_uppercase
    if use_lower:
        chars += string.ascii_lowercase
    if use_digits:
        chars += string.digits
    if use_symbols:
        chars += string.punctuation

    if exclude_similar:
        for c in 'il1Lo0O':
            chars = chars.replace(c, '')

    if exclude_ambiguous:
        for c in '{}[]()/\\\'"`~,;:.<>':
            chars = chars.replace(c, '')

    if not chars:
        chars = string.ascii_letters + string.digits

    password = ''.join(secrets.choice(chars) for _ in range(length))
    return password


def generate_passphrase(num_words=4, separator='-'):
    import secrets
    word_list = [
        'alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf',
        'hotel', 'india', 'juliett', 'kilo', 'lima', 'mike', 'november',
        'oscar', 'papa', 'quebec', 'romeo', 'sierra', 'tango', 'uniform',
        'victor', 'whiskey', 'xray', 'yankee', 'zulu',
        'cloud', 'storm', 'river', 'mountain', 'forest', 'ocean', 'desert',
        'eagle', 'hawk', 'wolf', 'bear', 'falcon', 'phoenix', 'dragon',
        'ruby', 'sapphire', 'emerald', 'diamond', 'amber', 'jade', 'opal',
        'crimson', 'azure', 'golden', 'silver', 'bronze', 'ivory', 'violet',
    ]
    words = [secrets.choice(word_list) for _ in range(num_words)]
    return separator.join(words)


def calculate_entropy(password):
    import re
    import math
    charset = 0
    if re.search(r'[a-z]', password):
        charset += 26
    if re.search(r'[A-Z]', password):
        charset += 26
    if re.search(r'[0-9]', password):
        charset += 10
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        charset += 32
    if charset == 0:
        return 0
    return round(len(password) * math.log2(charset), 2)


def password_strength(password):
    entropy = calculate_entropy(password)
    if entropy >= 128:
        return {'label': 'Muy Fuerte', 'level': 5, 'color': 'dark', 'min': 128, 'entropy': entropy}
    elif entropy >= 80:
        return {'label': 'Fuerte', 'level': 4, 'color': 'success', 'min': 80, 'entropy': entropy}
    elif entropy >= 60:
        return {'label': 'Buena', 'level': 3, 'color': 'info', 'min': 60, 'entropy': entropy}
    elif entropy >= 36:
        return {'label': 'Débil', 'level': 2, 'color': 'warning', 'min': 36, 'entropy': entropy}
    else:
        return {'label': 'Muy Débil', 'level': 1, 'color': 'danger', 'min': 0, 'entropy': entropy}


def strength_percentage(entropy):
    max_entropy = 140
    return min(100, round((entropy / max_entropy) * 100))


def check_hibp(password):
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        resp = requests.get(f'https://api.pwnedpasswords.com/range/{prefix}', timeout=10)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if line.startswith(suffix):
                    count = int(line.split(':')[1])
                    return count
        return 0
    except (requests.RequestException, ValueError, IndexError):
        return 0

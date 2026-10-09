import hmac
import hashlib
import time
from typing import Optional

SECRET_KEY = "retro_topup_super_secret_key_2026_bd"

def hash_password(password: str, salt: str = "retro_salt_2026") -> str:
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def create_admin_token(username: str, expires_in_sec: int = 86400 * 7) -> str:
    """Create a signed session token: username:expire_ts:signature"""
    expire_ts = int(time.time()) + expires_in_sec
    payload = f"{username}:{expire_ts}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"

def verify_admin_token(token: Optional[str]) -> Optional[str]:
    """Verify signed session token. Returns username if valid, else None."""
    if not token:
        return None
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, expire_ts_str, signature = parts
        expire_ts = int(expire_ts_str)
        if time.time() > expire_ts:
            return None # expired
        payload = f"{username}:{expire_ts}"
        expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return username
        return None
    except Exception:
        return None

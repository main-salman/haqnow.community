from datetime import datetime, timedelta
import secrets
import hashlib
import jwt
import pyotp
from passlib.context import CryptContext
from .config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(code: str, secret: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def create_jwt(payload: dict) -> str:
    settings = get_settings()
    to_encode = {
        **payload,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_exp_minutes),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")


def generate_api_key() -> tuple[str, str]:
    """Generate API key and return (raw_key, hash_for_storage)"""
    raw_key = f"hc_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify API key against stored hash"""
    computed_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return computed_hash == stored_hash



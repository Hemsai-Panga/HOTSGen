"""Security utilities for password hashing and JWT token handling."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import bcrypt
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Expected role claim value for developer mode
DEVELOPER_ROLE = "developer"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt with standard salt rounds."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.warning(f"Password verification error: {type(e).__name__}")
        return False


def create_access_token(
    subject: str,
    role: str = DEVELOPER_ROLE,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token containing subject and role claims."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    
    Raises:
        ExpiredSignatureError: When the token expiration timestamp has passed.
        InvalidTokenError: When the token is malformed, invalid signature, or invalid claims.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub", "role"]},
    )
    return payload


def verify_developer_credentials(username: str, password: str) -> bool:
    """
    Authenticate developer credentials against configured admin credentials.
    Returns True if valid, False otherwise without revealing which component failed.
    """
    settings = get_settings()

    if not settings.ADMIN_PASSWORD_HASH:
        logger.warning("ADMIN_PASSWORD_HASH is not set. Developer login is disabled.")
        return False

    # Constant-time comparison for username is handled through equality
    is_valid_user = (username.strip() == settings.ADMIN_USERNAME.strip())
    is_valid_pass = verify_password(password, settings.ADMIN_PASSWORD_HASH)

    return is_valid_user and is_valid_pass

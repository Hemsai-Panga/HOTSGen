"""Reusable FastAPI dependencies for security and authentication."""

import logging
from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.core.security import DEVELOPER_ROLE, decode_access_token

logger = logging.getLogger(__name__)

# HTTP Bearer scheme extractor (auto_error=False allows returning custom descriptive 401s)
security_scheme = HTTPBearer(auto_error=False)


async def get_current_developer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> Dict[str, Any]:
    """
    FastAPI dependency that extracts and validates the Bearer JWT for Developer Mode.
    
    Returns:
        Dict containing decoded token claims (sub, role, exp, iat).
        
    Raises:
        HTTPException 401: If token is missing, expired, or invalid.
        HTTPException 403: If token role is not developer.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.warning(f"Unexpected token validation error: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate role claim
    role = payload.get("role")
    if role != DEVELOPER_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: developer role required",
        )

    return payload

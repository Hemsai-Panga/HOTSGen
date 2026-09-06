"""Authentication API routes for Developer Mode."""

from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import create_access_token, verify_developer_credentials

router = APIRouter()


class LoginRequest(BaseModel):
    """Schema for developer login request."""
    username: str = Field(..., description="Developer username")
    password: str = Field(..., description="Developer password")


class TokenResponse(BaseModel):
    """Schema for successful authentication response."""
    access_token: str
    token_type: str = "bearer"


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Developer Login",
    description="Authenticate with developer credentials to receive a JWT access token.",
)
def login(login_data: LoginRequest) -> Any:
    """Validate credentials and issue signed JWT access token for developer."""
    is_valid = verify_developer_credentials(
        username=login_data.username,
        password=login_data.password,
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=login_data.username.strip())
    return TokenResponse(access_token=access_token, token_type="bearer")

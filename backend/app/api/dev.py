"""Protected Developer Mode routes."""

from typing import Any, Dict
from fastapi import APIRouter, Depends

from app.api.deps import get_current_developer

router = APIRouter()


@router.get(
    "/test",
    summary="Verify Developer Authentication",
    description="Protected test endpoint requiring a valid developer JWT.",
)
def test_developer_access(
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> Dict[str, Any]:
    """Test endpoint confirming that the caller has authenticated developer permissions."""
    return {
        "status": "success",
        "message": "Developer access verified",
        "developer": current_developer.get("sub"),
        "role": current_developer.get("role"),
    }

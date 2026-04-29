from typing import Optional

from fastapi import Depends
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.custom_router import ProtectedRouter
from app.core.livekit import generate_subscriber_token

router = ProtectedRouter()


class LiveKitTokenRequest(BaseModel):
    tenant_id: str
    viewer_id: Optional[str] = None


class LiveKitTokenResponse(BaseModel):
    token: str
    livekit_url: str


@router.post("/token", response_model=LiveKitTokenResponse)
def get_livekit_token(
    body: LiveKitTokenRequest,
    current_user: dict = Depends(ProtectedRouter.inject_current_user),
):
    """Generate a LiveKit subscriber token for a tenant room."""
    viewer_id = body.viewer_id or current_user.get("email", "viewer")
    token = generate_subscriber_token(body.tenant_id, viewer_id)
    return LiveKitTokenResponse(
        token=token,
        livekit_url=get_settings().LIVEKIT_URL,
    )

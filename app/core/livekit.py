import hashlib
import time
import uuid

import jwt

from app.core.config import get_settings


def _short_identity(prefix: str, identifier: str, max_len: int = 250) -> str:
    candidate = f"{prefix}_{identifier}" if prefix else identifier
    if len(candidate) <= max_len:
        return candidate
    digest = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"{prefix}_{digest}" if prefix else digest


def _make_token(identity: str, room: str, can_publish: bool, can_subscribe: bool) -> str:
    settings = get_settings()
    iat = int(time.time())
    payload = {
        "jti": str(uuid.uuid4()),
        "iat": iat,
        "nbf": iat,
        "exp": iat + settings.LIVEKIT_TOKEN_TTL,
        "iss": settings.LIVEKIT_API_KEY,
        "sub": identity,
        "video": {
            "roomJoin": True,
            "room": room,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
        },
    }
    return jwt.encode(payload, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def generate_subscriber_token(tenant_id: str, viewer_id: str) -> str:
    identity = _short_identity(f"{tenant_id}_viewer", viewer_id)
    return _make_token(identity, room=tenant_id, can_publish=False, can_subscribe=True)


def generate_publisher_token(tenant_id: str, camera_id: str) -> str:
    identity = _short_identity(f"nexa_pub_{tenant_id}", camera_id)
    return _make_token(identity, room=tenant_id, can_publish=True, can_subscribe=True)

from app.core.ws_manager import connectionmanager
from app.features.auth.api import get_current_user_ws
from fastapi import WebSocket, WebSocketDisconnect, status, APIRouter


router = APIRouter(prefix="/ws")

async def authenticate_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    try:
        # adjust if your function expects request instead of token
        user = await get_current_user_ws(token=token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    return user

@router.websocket("/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):

    user = await authenticate_ws(websocket)
    if not user:
        return

    # enforce tenant isolation
    if str(user.get("tenant_id")) != tenant_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await connectionmanager.connect(tenant_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await connectionmanager.disconnect(tenant_id, websocket)

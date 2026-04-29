from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.features.auth.api import router as auth_router
from app.features.management.api import router as management_router
from app.features.cameras.api import router as cameras_router
from app.features.stream.api import router as stream_router


def create_app() -> FastAPI:
    app = FastAPI(title="Camera RBAC API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router,       prefix="/api/v1/auth",       tags=["auth"])
    app.include_router(management_router, prefix="/api/v1/management", tags=["management"])
    app.include_router(cameras_router,    prefix="/api/v1/cameras",    tags=["cameras"])
    app.include_router(stream_router,     prefix="/api/v1/livekit",    tags=["livekit"])

    return app


app = create_app()

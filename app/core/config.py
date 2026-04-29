import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Camera RBAC API"

    # MongoDB
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB: str  = os.getenv("MONGO_DB",  "camera_rbac")

    # JWT
    SECRET_KEY: str                = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    ALGORITHM: str                 = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # MinIO
    MINIO_ENDPOINT: str    = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str  = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY: str  = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_SECURE: bool     = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET: str      = os.getenv("MINIO_BUCKET", "cameras")
    MINIO_URL_EXPIRES_SECONDS: int = int(os.getenv("MINIO_URL_EXPIRES_SECONDS", "1800"))

    # LiveKit
    LIVEKIT_API_KEY: str    = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")
    LIVEKIT_URL: str        = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    LIVEKIT_TOKEN_TTL: int  = int(os.getenv("LIVEKIT_TOKEN_TTL", "3600"))


@lru_cache
def get_settings() -> Settings:
    return Settings()

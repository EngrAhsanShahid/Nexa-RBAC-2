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

    # Frontend / CORS
    FRONTEND_ORIGINS: str = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000")

    # Auth cookie
    COOKIE_NAME: str = os.getenv("COOKIE_NAME", "access_token")
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", "localhost")
    COOKIE_PATH: str = os.getenv("COOKIE_PATH", "/api/v1")
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "strict").lower()
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    COOKIE_MAX_AGE: int = int(
        os.getenv("COOKIE_MAX_AGE", str(int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")) * 60))
    )

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
    
    ### change here
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.100.11:9093")
    KAFKA_ALERTS_TOPIC: str = os.getenv("KAFKA_ALERTS_TOPIC", "alerts")
    KAFKA_GROUP_ID: str = os.getenv("KAFKA_GROUP_ID", "frontend_ws_2")

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]
@lru_cache
def get_settings() -> Settings:
    return Settings()
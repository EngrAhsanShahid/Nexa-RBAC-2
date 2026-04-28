from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import get_settings

settings = get_settings()

# Single shared client (PyMongo is thread-safe by default)
_client = MongoClient(settings.MONGO_URI)
_db     = _client[settings.MONGO_DB]


def get_db() -> Database:
    """
    FastAPI dependency — inject MongoDB database instance.

    Usage:
        def endpoint(db: Database = Depends(get_db)):
    """
    return _db

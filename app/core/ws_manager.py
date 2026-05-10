### change here
from app.core.config import get_settings
from app.core.connection_manager import ConnectionManager

### change here
settings = get_settings()
connectionmanager = ConnectionManager(
### change here
    bootstrap_server=settings.KAFKA_BOOTSTRAP_SERVERS,
    topic=settings.KAFKA_ALERTS_TOPIC,
    group_id=settings.KAFKA_GROUP_ID, ### unique group id for each frontend instance to ensure each instance gets all messages
)
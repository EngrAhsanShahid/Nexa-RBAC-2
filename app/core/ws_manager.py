from app.core.connection_manager import ConnectionManager

connectionmanager = ConnectionManager(
    bootstrap_server="192.168.100.4:9093",
    topic="alerts"
)
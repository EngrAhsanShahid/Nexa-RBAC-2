import asyncio
import json
from confluent_kafka import Consumer


class ConnectionManager:
    def __init__(self, bootstrap_server, topic, group_id="frontend_ws"):
        # single client per tenant
        self.active_connections: dict[str, any] = {}

        self.conf = {
            "bootstrap.servers": bootstrap_server,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
        }

        self.topic = topic
        self.consumer = Consumer(self.conf)
        self.consumer.subscribe([self.topic])

    async def connect(self, tenant_id: str, websocket):
        await websocket.accept()

        # safely replace existing connection
        old_ws = self.active_connections.get(tenant_id)
        if old_ws:
            try:
                await old_ws.close(code=1000)
            except:
                pass

        self.active_connections[tenant_id] = websocket

    async def disconnect(self, tenant_id: str, websocket):
        # remove only if same socket
        if self.active_connections.get(tenant_id) == websocket:
            self.active_connections.pop(tenant_id, None)

    async def broadcast(self, data: dict):
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            return

        ws = self.active_connections.get(tenant_id)
        if not ws:
            return

        try:
            await ws.send_json(data)
        except Exception:
            # cleanup broken connection
            self.active_connections.pop(tenant_id, None)

    async def kafka_listener(self):
        loop = asyncio.get_running_loop()

        while True:
            msg = await loop.run_in_executor(None, self.consumer.poll, 1.0)

            if msg is None:
                continue

            if msg.error():
                print(f"[Kafka Error] {msg.error()}")
                continue

            try:
                data = json.loads(msg.value().decode("utf-8"))
                await self.broadcast(data)
            except Exception as e:
                print(f"[Processing Error] {e}")

    def close(self):
        self.consumer.close()
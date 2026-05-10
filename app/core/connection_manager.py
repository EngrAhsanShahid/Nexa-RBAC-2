import asyncio
import json
### change here
from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from app.features.websocket.schemas import Alert_ws_schema


class ConnectionManager:
    def __init__(self, bootstrap_server, topic, group_id="frontend_ws_2"):
        # single client per tenant
        self.active_connections: dict[str, any] = {}

        self.conf = {
            "bootstrap.servers": bootstrap_server,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
        }

        self.topic = topic
        self.consumer = Consumer(self.conf)
        ### change here
        self._ensure_topic()
        self.consumer.subscribe([self.topic])

    ### change here
    def _ensure_topic(self):
        admin_client = AdminClient({"bootstrap.servers": self.conf["bootstrap.servers"]})

        try:
            metadata = self.consumer.list_topics(timeout=5)
            topic_metadata = metadata.topics.get(self.topic)

            if topic_metadata is not None and topic_metadata.error is None:
                return

            futures = admin_client.create_topics([
                NewTopic(self.topic, num_partitions=1, replication_factor=1)
            ])
            futures[self.topic].result(timeout=10)

        except KafkaException as exc:
            error = exc.args[0] if exc.args else None
            if error and error.code() == KafkaError.TOPIC_ALREADY_EXISTS:
                return

            print(f"[Kafka Setup Error] {exc}")

        except Exception as exc:
            print(f"[Kafka Setup Error] {exc}")

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
            payload = Alert_ws_schema.model_validate(data)
            await ws.send_json(payload.model_dump())
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
                ### change here
                if msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    await asyncio.sleep(2)
                    continue

                print(f"[Kafka Error] {msg.error()}")
                continue

            try:
                data = json.loads(msg.value().decode("utf-8"))
                await self.broadcast(data)
            except Exception as e:
                print(f"[Processing Error] {e}")

    def close(self):
        self.consumer.close()
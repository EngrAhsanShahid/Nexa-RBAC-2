from confluent_kafka import Consumer
import json

conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-group',
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf)
consumer.subscribe(["alerts"])

print("Listening for messages...")

try:
    while True:
        msg = consumer.poll(1.0)

        if msg is None:
            continue
        if msg.error():
            print(f"Error: {msg.error()}")
            continue

        data = json.loads(msg.value().decode('utf-8'))
        print(f"Received: {data}")

except KeyboardInterrupt:
    pass
finally:
    consumer.close()
import json
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "vehicle-events",
    bootstrap_servers="localhost:9092",
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    group_id="track4-consumer-clean",
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("Listening for vehicle events...")
print("Press Ctrl+C to stop.\n")

for message in consumer:
    event = message.value

    print("New vehicle event received:")
    print(json.dumps(event, indent=2))
    print("-" * 50)
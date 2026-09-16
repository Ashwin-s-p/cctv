import json
from kafka import KafkaProducer

# Connect to Kafka
producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

# Dummy vehicle event
event = {
    "event_id": "EVT_000002",
    "camera_id": "CAM_01",
    "vehicle_id": "track_0002",
    "plate_number": "MH12AB1234",
    "timestamp": "2026-09-10T10:00:08Z",
    "confidence": 0.963
}

# Send event to Kafka topic
producer.send("vehicle-events", event)

# Make sure message is sent
producer.flush()

print("Vehicle event sent successfully!")
print(json.dumps(event, indent=2))

producer.close()
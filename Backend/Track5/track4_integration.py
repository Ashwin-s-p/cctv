import json
import urllib.request

from track5_analytics import analyze_vehicle_events

TRACK4_API = "http://127.0.0.1:8000/events"
ROAD_SEGMENTS_FILE = "integration_road_segments.json"


def fetch_track4_events():
    with urllib.request.urlopen(TRACK4_API, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data["events"]


def load_road_segments():
    with open(ROAD_SEGMENTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    print("=" * 70)
    print("TRACK 4 → TRACK 5 INTEGRATION")
    print("=" * 70)
    print()

    print(f"Fetching events from: {TRACK4_API}")
    events = fetch_track4_events()

    print(f"Received {len(events)} vehicle event(s) from Track 4")
    print()

    print(f"Loading road segments from: {ROAD_SEGMENTS_FILE}")
    road_segments = load_road_segments()

    print(f"Loaded {len(road_segments)} road segment(s)")
    print()

    print("Running Track 5 analytics...")
    print()

    result = analyze_vehicle_events(
        events,
        road_segments
    )

    print("=" * 70)
    print("TRACK 5 ANALYTICS RESULT")
    print("=" * 70)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
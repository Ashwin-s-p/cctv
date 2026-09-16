"""Track 5 trajectory and traffic analytics.

The module consumes the ``vehicle_events`` JSON contract produced by Track 4.
It deliberately has no database, web framework, message broker, or frontend
dependencies so the data source can later be replaced by a Track 4 API client.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


Event = Mapping[str, Any]
Point = dict[str, Any]
RoadSegment = Mapping[str, Any]


def _number(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value}") from exc


def haversine_km(first: Point, second: Point) -> float:
    """Return the great-circle distance between two latitude/longitude points."""
    earth_radius_km = 6371.0088
    lat1, lon1 = math.radians(float(first["latitude"])), math.radians(float(first["longitude"]))
    lat2, lon2 = math.radians(float(second["latitude"])), math.radians(float(second["longitude"]))
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def _validate_event(event: Event) -> None:
    for field in ("vehicle_id", "timestamp", "latitude", "longitude"):
        if field not in event:
            raise ValueError(f"vehicle event is missing required field: {field}")
    _timestamp(event["timestamp"])
    latitude = _number(event["latitude"], "latitude")
    longitude = _number(event["longitude"], "longitude")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude is outside valid bounds")


def _point(event: Event) -> Point:
    result: Point = {
        "latitude": float(event["latitude"]),
        "longitude": float(event["longitude"]),
        "timestamp": event["timestamp"],
    }
    for field in ("camera_id", "road_segment_id", "area"):
        if event.get(field) is not None:
            result[field] = event[field]
    return result


def _nearest_segment(point: Point, road_segments: Sequence[RoadSegment]) -> RoadSegment | None:
    if not road_segments:
        return None
    latitude, longitude = float(point["latitude"]), float(point["longitude"])
    # Equirectangular distance is sufficient for nearest-road matching over a city.
    scale = math.cos(math.radians(latitude))

    def distance(segment: RoadSegment) -> float:
        segment_lat = float(segment["latitude"])
        segment_lon = float(segment["longitude"])
        return math.hypot((longitude - segment_lon) * scale, latitude - segment_lat)

    return min(road_segments, key=distance)


def map_match(point: Point, road_segments: Sequence[RoadSegment]) -> dict[str, Any]:
    """Attach the nearest supplied road segment to a trajectory point."""
    segment = _nearest_segment(point, road_segments)
    if segment is None:
        return {}
    return {
        "road_segment_id": segment["road_segment_id"],
        **({"road_name": segment["road_name"]} if segment.get("road_name") else {}),
        **({"area": segment["area"]} if segment.get("area") else {}),
    }


def reconstruct_trajectories(events: Iterable[Event], road_segments: Sequence[RoadSegment] = ()) -> list[dict[str, Any]]:
    """Group events by vehicle, sort them, map-match points, and calculate speed."""
    grouped: defaultdict[str, list[Event]] = defaultdict(list)
    for event in events:
        _validate_event(event)
        grouped[str(event["vehicle_id"])].append(event)

    trajectories: list[dict[str, Any]] = []
    for vehicle_id, vehicle_events in sorted(grouped.items()):
        ordered = sorted(vehicle_events, key=lambda event: _timestamp(event["timestamp"]))
        points: list[Point] = []
        total_distance = 0.0
        speeds: list[float] = []
        for event in ordered:
            point = _point(event)
            matched = map_match(point, road_segments)
            if matched:
                point.update(matched)
            if points:
                seconds = (_timestamp(point["timestamp"]) - _timestamp(points[-1]["timestamp"])).total_seconds()
                distance = haversine_km(points[-1], point)
                total_distance += distance
                if seconds > 0:
                    speeds.append(distance / seconds * 3600)
            points.append(point)
        result: dict[str, Any] = {
            "vehicle_id": vehicle_id,
            "trajectory": points,
            "average_speed_kmh": round(sum(speeds) / len(speeds), 2) if speeds else 0.0,
            "distance_km": round(total_distance, 2),
        }
        plate_numbers = {str(event["plate_number"]) for event in ordered if event.get("plate_number")}
        if len(plate_numbers) == 1:
            result["plate_number"] = next(iter(plate_numbers))
        trajectories.append(result)
    return trajectories


def traffic_density(trajectories: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Count unique vehicles observed on each matched road segment."""
    vehicles_by_segment: defaultdict[str, set[str]] = defaultdict(set)
    for trajectory in trajectories:
        for point in trajectory["trajectory"]:
            segment_id = point.get("road_segment_id")
            if segment_id:
                vehicles_by_segment[str(segment_id)].add(str(trajectory["vehicle_id"]))
    return [
        {"road_segment_id": segment_id, "vehicle_count": len(vehicles)}
        for segment_id, vehicles in sorted(vehicles_by_segment.items())
    ]


def od_analysis(trajectories: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Count origin-to-destination movements using matched areas or segments."""
    movements: defaultdict[tuple[str, str], int] = defaultdict(int)
    for trajectory in trajectories:
        points = trajectory["trajectory"]
        if not points:
            continue
        origin = points[0].get("area") or points[0].get("road_segment_id")
        destination = points[-1].get("area") or points[-1].get("road_segment_id")
        if origin and destination:
            movements[(str(origin), str(destination))] += 1
    return [
        {"origin": origin, "destination": destination, "vehicle_count": count}
        for (origin, destination), count in sorted(movements.items())
    ]


def analyze_vehicle_events(
    events: Iterable[Event], road_segments: Sequence[RoadSegment] = ()
) -> dict[str, Any]:
    """Produce the Track 5 JSON response from Track 4 vehicle events."""
    trajectories = reconstruct_trajectories(events, road_segments)
    return {
        "trajectories": trajectories,
        "traffic_density": traffic_density(trajectories),
        "od_analysis": od_analysis(trajectories),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Track 4 vehicle_events JSON.")
    parser.add_argument("events", type=Path, help="JSON file containing an array of vehicle events")
    parser.add_argument("--roads", type=Path, help="Optional JSON file containing road segment points")
    args = parser.parse_args()
    events = json.loads(args.events.read_text(encoding="utf-8"))
    roads = json.loads(args.roads.read_text(encoding="utf-8")) if args.roads else []
    print(json.dumps(analyze_vehicle_events(events, roads), indent=2))


if __name__ == "__main__":
    main()

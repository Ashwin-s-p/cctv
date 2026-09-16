# Track 5: Trajectory + Traffic Analytics Engine

This module consumes the dummy `vehicle_events` JSON contract from Track 4 and
returns trajectory, map-matched road, speed, density, and origin/destination
analytics. It uses only the Python standard library; a future Track 4 API or
PostGIS adapter can provide the same event dictionaries.

```powershell
python .\track5_analytics.py .\dummy_vehicle_events.json --roads .\dummy_road_segments.json
```

Each event requires `vehicle_id`, `timestamp`, `latitude`, and `longitude`.
`plate_number`, `camera_id`, and other Track 4 fields are preserved where
available. Road data contains representative segment points with
`road_segment_id`, `latitude`, and `longitude`; map matching attaches the
nearest segment.

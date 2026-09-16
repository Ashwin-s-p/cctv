-- ============================================
-- ANPR TRACK 4 DATABASE SCHEMA
-- PostgreSQL + PostGIS
-- ============================================

-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================
-- 1. CAMERAS
-- ============================================

CREATE TABLE IF NOT EXISTS cameras (
    camera_id VARCHAR(50) PRIMARY KEY,
    camera_name VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location GEOGRAPHY(POINT, 4326),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2. VEHICLE EVENTS
-- ============================================

CREATE TABLE IF NOT EXISTS vehicle_events (
    event_id VARCHAR(100) PRIMARY KEY,

    camera_id VARCHAR(50) NOT NULL,

    vehicle_id VARCHAR(100) NOT NULL,

    plate_number VARCHAR(20),

    timestamp TIMESTAMPTZ NOT NULL,

    latitude DOUBLE PRECISION,

    longitude DOUBLE PRECISION,

    location GEOGRAPHY(POINT, 4326),

    vehicle_type VARCHAR(50),

    confidence DOUBLE PRECISION,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_camera
        FOREIGN KEY (camera_id)
        REFERENCES cameras(camera_id),

    CONSTRAINT confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

-- ============================================
-- 3. BLACKLIST
-- ============================================

CREATE TABLE IF NOT EXISTS blacklist (
    plate_number VARCHAR(20) PRIMARY KEY,

    reason TEXT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 4. INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_vehicle_events_plate
ON vehicle_events(plate_number);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_timestamp
ON vehicle_events(timestamp);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_camera
ON vehicle_events(camera_id);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_vehicle
ON vehicle_events(vehicle_id);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_location
ON vehicle_events
USING GIST(location);

CREATE INDEX IF NOT EXISTS idx_cameras_location
ON cameras
USING GIST(location);

-- ============================================
-- 5. TRIGGER FUNCTION
-- Automatically creates GIS point
-- ============================================

CREATE OR REPLACE FUNCTION update_vehicle_location()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL
       AND NEW.longitude IS NOT NULL THEN

        NEW.location :=
            ST_SetSRID(
                ST_MakePoint(NEW.longitude, NEW.latitude),
                4326
            )::geography;

    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 6. TRIGGER
-- ============================================

DROP TRIGGER IF EXISTS vehicle_location_trigger
ON vehicle_events;

CREATE TRIGGER vehicle_location_trigger
BEFORE INSERT OR UPDATE
ON vehicle_events
FOR EACH ROW
EXECUTE FUNCTION update_vehicle_location();

-- ============================================
-- DONE
-- ============================================
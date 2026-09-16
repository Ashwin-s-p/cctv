
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg2
import redis


app = FastAPI(
    title="ANPR Track 4 API",
    description="PostgreSQL + PostGIS + Redis backend for ANPR Track 4",
    version="1.0.0"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="anpr_db",
        user="anpr_user",
        password="anpr_password"
    )


# ============================================================
# REDIS CONNECTION
# ============================================================

def get_redis_connection():
    return redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True
    )


# ============================================================
# PYDANTIC MODELS
# ============================================================

class VehicleEvent(BaseModel):
    event_id: str
    camera_id: str
    vehicle_id: str
    plate_number: Optional[str] = None
    timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    vehicle_type: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class BlacklistEntry(BaseModel):
    plate_number: str
    reason: Optional[str] = None


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "ANPR Track 4 API is running",
        "database": "PostgreSQL + PostGIS",
        "cache": "Redis"
    }


# ============================================================
# DATABASE TEST
# ============================================================

@app.get("/db-test")
def db_test():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return {
            "status": "connected",
            "database": "PostgreSQL",
            "version": version
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )


# ============================================================
# REDIS TEST
# ============================================================

@app.get("/redis-test")
def redis_test():
    try:
        r = get_redis_connection()

        response = r.ping()

        return {
            "status": "connected",
            "redis": "Redis",
            "ping": response
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Redis connection failed: {str(e)}"
        )


# ============================================================
# CREATE VEHICLE EVENT
# ============================================================

@app.post("/events", status_code=201)
def create_event(event: VehicleEvent):

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO vehicle_events (
                event_id,
                camera_id,
                vehicle_id,
                plate_number,
                timestamp,
                latitude,
                longitude,
                vehicle_type,
                confidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event.event_id,
                event.camera_id,
                event.vehicle_id,
                event.plate_number,
                event.timestamp,
                event.latitude,
                event.longitude,
                event.vehicle_type,
                event.confidence
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        # ----------------------------------------------------
        # Check Redis blacklist cache
        # ----------------------------------------------------

        blacklist_status = False

        if event.plate_number:
            r = get_redis_connection()

            if r.exists(f"blacklist:{event.plate_number}"):
                blacklist_status = True

        return {
            "message": "Vehicle event created successfully",
            "event_id": event.event_id,
            "blacklisted": blacklist_status
        }

    except psycopg2.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Event ID already exists"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create event: {str(e)}"
        )


# ============================================================
# GET ALL EVENTS
# ============================================================

@app.get("/events")
def get_events():

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                event_id,
                camera_id,
                vehicle_id,
                plate_number,
                timestamp,
                latitude,
                longitude,
                vehicle_type,
                confidence
            FROM vehicle_events
            ORDER BY timestamp DESC
            """
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        events = []

        for row in rows:
            events.append({
                "event_id": row[0],
                "camera_id": row[1],
                "vehicle_id": row[2],
                "plate_number": row[3],
                "timestamp": row[4],
                "latitude": row[5],
                "longitude": row[6],
                "vehicle_type": row[7],
                "confidence": row[8]
            })

        return {
            "count": len(events),
            "events": events
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve events: {str(e)}"
        )


# ============================================================
# GET VEHICLE TRAJECTORY
# ============================================================

@app.get("/vehicles/{vehicle_id}")
def get_vehicle_events(vehicle_id: str):

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                event_id,
                camera_id,
                vehicle_id,
                plate_number,
                timestamp,
                latitude,
                longitude,
                vehicle_type,
                confidence
            FROM vehicle_events
            WHERE vehicle_id = %s
            ORDER BY timestamp ASC
            """,
            (vehicle_id,)
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        events = []

        for row in rows:
            events.append({
                "event_id": row[0],
                "camera_id": row[1],
                "vehicle_id": row[2],
                "plate_number": row[3],
                "timestamp": row[4],
                "latitude": row[5],
                "longitude": row[6],
                "vehicle_type": row[7],
                "confidence": row[8]
            })

        return {
            "vehicle_id": vehicle_id,
            "count": len(events),
            "events": events
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve vehicle data: {str(e)}"
        )


# ============================================================
# GET EVENTS BY PLATE
# ============================================================

@app.get("/plates/{plate_number}")
def get_plate_events(plate_number: str):

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                event_id,
                camera_id,
                vehicle_id,
                plate_number,
                timestamp,
                latitude,
                longitude,
                vehicle_type,
                confidence
            FROM vehicle_events
            WHERE plate_number = %s
            ORDER BY timestamp ASC
            """,
            (plate_number,)
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        events = []

        for row in rows:
            events.append({
                "event_id": row[0],
                "camera_id": row[1],
                "vehicle_id": row[2],
                "plate_number": row[3],
                "timestamp": row[4],
                "latitude": row[5],
                "longitude": row[6],
                "vehicle_type": row[7],
                "confidence": row[8]
            })

        return {
            "plate_number": plate_number,
            "count": len(events),
            "events": events
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve plate data: {str(e)}"
        )


# ============================================================
# ADD PLATE TO BLACKLIST
# ============================================================

@app.post("/blacklist", status_code=201)
def add_blacklist(entry: BlacklistEntry):

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO blacklist (
                plate_number,
                reason,
                is_active
            )
            VALUES (%s, %s, TRUE)
            ON CONFLICT (plate_number)
            DO UPDATE SET
                reason = EXCLUDED.reason,
                is_active = TRUE
            RETURNING plate_number, reason, is_active, created_at
            """,
            (
                entry.plate_number,
                entry.reason
            )
        )

        row = cursor.fetchone()

        conn.commit()

        cursor.close()
        conn.close()

        # ----------------------------------------------------
        # Store blacklist entry in Redis
        # ----------------------------------------------------

        r = get_redis_connection()

        r.set(
            f"blacklist:{entry.plate_number}",
            entry.reason or "Blacklisted vehicle"
        )

        return {
            "message": "Plate added to blacklist",
            "plate_number": row[0],
            "reason": row[1],
            "is_active": row[2],
            "created_at": row[3],
            "redis_cached": True
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add blacklist entry: {str(e)}"
        )


# ============================================================
# GET ALL BLACKLISTED PLATES
# ============================================================

@app.get("/blacklist")
def get_blacklist():

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                plate_number,
                reason,
                is_active,
                created_at
            FROM blacklist
            WHERE is_active = TRUE
            ORDER BY created_at DESC
            """
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        blacklist = []

        for row in rows:
            blacklist.append({
                "plate_number": row[0],
                "reason": row[1],
                "is_active": row[2],
                "created_at": row[3]
            })

        return {
            "count": len(blacklist),
            "blacklist": blacklist
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve blacklist: {str(e)}"
        )


# ============================================================
# CHECK BLACKLISTED PLATE
# ============================================================

@app.get("/blacklist/{plate_number}")
def check_blacklist(plate_number: str):

    try:
        # ----------------------------------------------------
        # FIRST: Check Redis
        # ----------------------------------------------------

        r = get_redis_connection()

        cached_reason = r.get(f"blacklist:{plate_number}")

        if cached_reason is not None:
            return {
                "plate_number": plate_number,
                "reason": cached_reason,
                "is_active": True,
                "source": "redis_cache"
            }

        # ----------------------------------------------------
        # SECOND: Check PostgreSQL
        # ----------------------------------------------------

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                plate_number,
                reason,
                is_active,
                created_at
            FROM blacklist
            WHERE plate_number = %s
              AND is_active = TRUE
            """,
            (plate_number,)
        )

        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row is None:
            return {
                "plate_number": plate_number,
                "is_active": False,
                "source": "database"
            }

        # ----------------------------------------------------
        # Cache database result in Redis
        # ----------------------------------------------------

        r.set(
            f"blacklist:{plate_number}",
            row[1] or "Blacklisted vehicle"
        )

        return {
            "plate_number": row[0],
            "reason": row[1],
            "is_active": row[2],
            "created_at": row[3],
            "source": "database"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check blacklist: {str(e)}"
        )


"""
PostgreSQL Database Driver for High-Speed Incident & Photo Storage (Dokploy Integration)
Optimized for:
- Direct photo storage (Base64 JPEG / Binary) inside PostgreSQL
- Zero battery bloat
- Ultra-low latency incident archiving & instant broadcast audit logs
"""

import os
import time
import base64
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    device_type VARCHAR(64),
    location VARCHAR(255),
    ip_address VARCHAR(45),
    status VARCHAR(32) DEFAULT 'online',
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_alerts INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS incident_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    device_id VARCHAR(64),
    event_type VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    stationary_duration FLOAT DEFAULT 0.0,
    lane_corridor VARCHAR(64),
    proximity_zone VARCHAR(32),
    snapshot_filename VARCHAR(255),
    photo_base64 TEXT,
    broadcast_latency_ms FLOAT DEFAULT 4.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

class PostgresDatabase:
    def __init__(self, connection_url=None):
        self.connection_url = connection_url or os.getenv("DATABASE_URL")
        self.is_connected = False
        self.last_error = None
        self._conn = None
        if self.connection_url:
            self.connect()

    def _get_conn(self):
        """Returns a cached, auto-reconnecting PostgreSQL connection."""
        if self._conn is not None and not self._conn.closed:
            try:
                # Test connection liveness
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return self._conn
            except Exception:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

        if not self.connection_url:
            return None

        self._conn = psycopg2.connect(self.connection_url, connect_timeout=5)
        self._conn.autocommit = True
        return self._conn

    def connect(self, new_url=None):
        if new_url:
            self.connection_url = new_url
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

        if not self.connection_url:
            self.is_connected = False
            self.last_error = "No PostgreSQL connection URL provided"
            return False, self.last_error

        try:
            conn = self._get_conn()
            if not conn:
                raise Exception("Failed to establish PostgreSQL connection")
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
            self.is_connected = True
            self.last_error = None
            print(f"[PostgreSQL] Connected to Dokploy! Schema initialized for incident & photo storage.")
            return True, "Connected successfully"
        except Exception as e:
            self.is_connected = False
            self.last_error = str(e)
            return False, str(e)

    def log_incident(self, device_id, event_type, severity, duration, lane, proximity, snapshot_name, photo_url=None, photo_bytes=None, latency_ms=4.2):
        if not self.is_connected:
            return False

        # Images are stored on server disk. We store the server photo URL in the database.
        url_val = photo_url or (f"/api/photos/{snapshot_name}" if snapshot_name else "")
        b64_photo = ""
        if photo_bytes is not None and not photo_url:
            b64_photo = "data:image/jpeg;base64," + base64.b64encode(photo_bytes).decode('utf-8')

        try:
            conn = self._get_conn()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO incident_logs (device_id, event_type, severity, stationary_duration, lane_corridor, proximity_zone, snapshot_filename, photo_url, photo_base64, broadcast_latency_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (device_id, event_type, severity, float(duration or 0.0), lane, proximity, snapshot_name, url_val, b64_photo, float(latency_ms)))
                
                # Increment device total alerts
                cur.execute("""
                    UPDATE devices SET total_alerts = total_alerts + 1, last_seen = CURRENT_TIMESTAMP WHERE id = %s
                """, (device_id,))
            return True
        except Exception as e:
            print(f"[PostgreSQL Log Error] {e}")
            return False

    def sync_device(self, dev_dict):
        if not self.is_connected:
            return False

        try:
            conn = self._get_conn()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO devices (id, name, device_type, location, ip_address, status, total_alerts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = CURRENT_TIMESTAMP
                """, (
                    dev_dict.get("id"),
                    dev_dict.get("name"),
                    dev_dict.get("type"),
                    dev_dict.get("location"),
                    dev_dict.get("ip"),
                    dev_dict.get("status"),
                    dev_dict.get("alerts_count", 0)
                ))
            return True
        except Exception as e:
            print(f"[PostgreSQL Sync Error] {e}")
            return False

    def get_recent_incidents(self, limit=50):
        if not self.is_connected:
            return []

        try:
            conn = self._get_conn()
            if not conn:
                return []
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
                           device_id, event_type, severity, stationary_duration as duration,
                           lane_corridor as lane, proximity_zone as proximity, snapshot_filename,
                           COALESCE(photo_url, '/api/photos/' || snapshot_filename) as photo_url,
                           broadcast_latency_ms
                    FROM incident_logs
                    ORDER BY id DESC LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
            return rows
        except Exception as e:
            print(f"[PostgreSQL Query Error] {e}")
            return []



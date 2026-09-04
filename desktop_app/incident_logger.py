"""
Incident Logger & Persistent Storage Subsystem (Objective 6)
Stores detected highway road obstructions in SQLite database and CSV
with visual snapshot evidence for historical reporting and safety analytics.
"""

import sqlite3
import csv
import time
import os
import cv2
from pathlib import Path
import config

class IncidentDatabase:
    def __init__(self, db_dir=None):
        if db_dir is None:
            self.base_dir = config.SAMPLE_DATA_DIR
        else:
            self.base_dir = Path(db_dir)

        self.db_path = self.base_dir / "road_incidents.db"
        self.csv_path = self.base_dir / "road_incidents.csv"
        self.snapshots_dir = self.base_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        self.last_logged_time = 0
        self.min_log_interval = 3.0  # seconds to prevent duplicate logs of same incident
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                unix_time REAL,
                node_id TEXT,
                hazard_status TEXT,
                object_type TEXT,
                lane_corridor TEXT,
                stationary_duration REAL,
                proximity_zone TEXT,
                snapshot_filename TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_hazard(self, alert_info, frame=None, node_id="POLE_04", lane="LANE_1"):
        now = time.time()
        if now - self.last_logged_time < self.min_log_interval:
            return None

        self.last_logged_time = now
        time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        status = alert_info.get("status", "DANGER")
        obj_type = alert_info.get("type", "UNKNOWN")
        dur = alert_info.get("duration", 0.0)
        dist = alert_info.get("dist", "CLOSE")

        snapshot_fname = ""
        if frame is not None:
            snapshot_fname = f"incident_{int(now)}_{obj_type.replace(' ', '_')}.jpg"
            save_path = self.snapshots_dir / snapshot_fname
            cv2.imwrite(str(save_path), frame)

        # Write to SQLite
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO incidents (unix_time, node_id, hazard_status, object_type, lane_corridor, stationary_duration, proximity_zone, snapshot_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, node_id, status, obj_type, lane, dur, dist, snapshot_fname))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB Error] {e}")

        # Append to CSV
        file_exists = self.csv_path.exists()
        try:
            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "NodeID", "Status", "ObjectType", "Lane", "DurationSeconds", "Proximity", "Snapshot"])
                writer.writerow([time_str, node_id, status, obj_type, lane, round(dur, 2), dist, snapshot_fname])
        except Exception as e:
            print(f"[CSV Error] {e}")

        return snapshot_fname

    def get_recent_incidents(self, limit=20):
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, node_id, hazard_status, object_type, lane_corridor, stationary_duration, proximity_zone
                FROM incidents ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception:
            return []

    def get_summary_statistics(self):
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), AVG(stationary_duration) FROM incidents")
            total, avg_dur = cursor.fetchone()
            conn.close()
            return {"total_incidents": total or 0, "avg_duration": round(avg_dur or 0.0, 1)}
        except Exception:
            return {"total_incidents": 0, "avg_duration": 0.0}

"""
Professional Highway Road Obstruction Management System (Backend Server)
Powers the Enterprise Intelligent Transportation System (ITS) Web Portal.
Features:
- Live MJPEG Stream with AI Detection & Multi-Lane Overlays
- Real-Time REST & Telemetry Endpoints
- Dual LoRa & Wi-Fi Emergency Dispatcher
- Asset & Street Pole Telemetry Monitor
- Analytics & SQLite Evidence Archiving
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import cv2

# Project root imports
BACKEND_DIR = Path(__file__).resolve().parent
MGMT_DIR = BACKEND_DIR.parent
PROJECT_DIR = MGMT_DIR.parent
DESKTOP_DIR = PROJECT_DIR / "desktop_app"
FRONTEND_DIR = MGMT_DIR / "frontend"
sys.path.append(str(DESKTOP_DIR))
sys.path.append(str(BACKEND_DIR))

import config
from detector import RoadObstructionDetector
from incident_logger import IncidentDatabase
from network_hub import DualBroadcaster
from analytics_engine import SafetyAnalyticsEngine
from node_manager import HighwayNodeManager

detector = RoadObstructionDetector()
incident_db = IncidentDatabase()
analytics_engine = SafetyAnalyticsEngine(incident_db.db_path)
node_manager = HighwayNodeManager()
broadcaster = DualBroadcaster(
    wifi_broadcast_ip=config.DEFAULT_RECEIVER_UDP_IP,
    wifi_port=config.DEFAULT_RECEIVER_UDP_PORT
)

# Global runtime state
state_lock = threading.Lock()
latest_frame_jpeg = None
active_hazard_alert = {
    "status": "CLEAR",
    "type": "NONE",
    "dist": "SAFE",
    "duration": 0.0,
    "sound": 0,
    "lane": "LANE_1",
    "timestamp": time.time(),
    "acknowledged": False
}
is_running = True
current_camera_source = "POLE_DEMO"  # "POLE_DEMO", "DASHCAM", "LIVE_CAM", "ESP32_URL"
esp32_cam_url = config.DEFAULT_ESP32_CAM_URL

def video_inference_loop():
    """Continuously runs the AI detection engine on the active camera stream."""
    global latest_frame_jpeg, active_hazard_alert, is_running
    
    # Initialize street pole ROI
    w, h = 800, 600
    detector.set_roi([(int(px * w), int(py * h)) for px, py in config.POLE_ROI_NORMALIZED])
    
    while is_running:
        video_src = config.SAMPLE_DATA_DIR / "street_pole_demo.mp4"
        if current_camera_source == "DASHCAM":
            video_src = config.SAMPLE_DATA_DIR / "road_obstruction_demo.mp4"
            detector.set_roi([(int(px * w), int(py * h)) for px, py in config.DEFAULT_ROI_NORMALIZED])
        elif current_camera_source == "LIVE_CAM":
            video_src = 1 # Local camera index 1
        elif current_camera_source == "ESP32_URL":
            video_src = esp32_cam_url

        cap = cv2.VideoCapture(str(video_src) if isinstance(video_src, Path) else video_src)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_idx = 0

        while is_running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            t_sec = (frame_idx / fps) if current_camera_source in ["POLE_DEMO", "DASHCAM"] else None

            annotated_frame, alert_info = detector.process_frame(frame, timestamp=t_sec)
            alert_info["timestamp"] = time.time()
            alert_info["lane"] = "LANE_1"

            # Check stationary danger
            is_danger = (alert_info["status"] == "DANGER")
            node_manager.update_pole_telemetry("POLE_04", hazard_active=is_danger)
            
            if is_danger:
                vms_msg = f"! OBSTRUCTION AHEAD: {alert_info['type']} IN LANE 1 - REDUCE SPEED !"
                node_manager.set_vms_text(vms_msg)
                # Auto record to SQLite
                incident_db.log_hazard(alert_info, frame=annotated_frame, node_id="POLE_04", lane="LANE_1")
            else:
                node_manager.set_vms_text("ROAD CLEAR - MAINTAIN SAFE DISTANCE")

            # Dispatch over Dual Wi-Fi + LoRa
            broadcaster.send_alert(
                status=alert_info["status"],
                obj_type=alert_info["type"],
                dist=alert_info["dist"],
                duration=alert_info["duration"],
                sound=alert_info["sound"]
            )

            # Compress for high-speed Web MJPEG streaming
            ret_jpg, jpeg = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
            if ret_jpg:
                with state_lock:
                    latest_frame_jpeg = jpeg.tobytes()
                    active_hazard_alert = alert_info.copy()

            time.sleep(1.0 / 30.0)

        cap.release()
        time.sleep(0.3)


class ManagementAPIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. Static HTML Pages & Assets
        if path in ["/", "/index.html"]:
            self.serve_file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")
        elif path.startswith("/css/"):
            self.serve_file(FRONTEND_DIR / path.lstrip("/"), "text/css")
        elif path.startswith("/js/"):
            self.serve_file(FRONTEND_DIR / path.lstrip("/"), "application/javascript")
        elif path.startswith("/api/snapshots/"):
            filename = os.path.basename(path)
            self.serve_file(incident_db.snapshots_dir / filename, "image/jpeg")

        # 2. Live MJPEG Stream
        elif path == "/video_feed":
            self.stream_mjpeg()

        # 3. REST APIs
        elif path == "/api/status":
            with state_lock:
                data = {
                    "alert": active_hazard_alert,
                    "broadcaster": {
                        "wifi_enabled": broadcaster.wifi_enabled,
                        "lora_connected": broadcaster.lora.connected,
                        "lora_port": broadcaster.lora.port or "/dev/ttyUSB0",
                        "packets_sent": broadcaster.lora.packets_sent
                    },
                    "vms": node_manager.nodes["VMS_01"]["display_text"],
                    "server_time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            self.send_json(data)

        elif path == "/api/nodes":
            self.send_json(node_manager.get_all_nodes())

        elif path == "/api/incidents":
            records = incident_db.get_recent_incidents(50)
            formatted = [
                {
                    "timestamp": r[0],
                    "node_id": r[1],
                    "status": r[2],
                    "type": r[3],
                    "lane": r[4],
                    "duration": r[5],
                    "proximity": r[6]
                }
                for r in records
            ]
            self.send_json(formatted)

        elif path == "/api/analytics":
            kpis = analytics_engine.get_dashboard_kpis()
            charts = analytics_engine.get_charts_data()
            self.send_json({"kpis": kpis, "charts": charts})

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length).decode('utf-8') if length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except:
            req_data = {}

        if path == "/api/dispatch/lora":
            # Manual LoRa Emergency Broadcast Trigger
            lane = req_data.get("lane", "LANE_1")
            alert_type = req_data.get("type", "STALLED VEHICLE")
            payload = {
                "status": "DANGER",
                "type": alert_type,
                "dist": "IMMINENT",
                "duration": 5.0,
                "sound": 2
            }
            broadcaster.send_alert("DANGER", alert_type, "IMMINENT", 5.0, 2)
            vms_text = f"EMERGENCY BROADCAST: {alert_type.upper()} ON {lane} - REDUCE SPEED!"
            node_manager.set_vms_text(vms_text)
            self.send_json({"success": True, "message": "Emergency LoRa alert dispatched upstream!"})

        elif path == "/api/switch_camera":
            global current_camera_source, esp32_cam_url
            source = req_data.get("source", "POLE_DEMO")
            current_camera_source = source
            if "url" in req_data:
                esp32_cam_url = req_data["url"]
            self.send_json({"success": True, "source": current_camera_source})

        elif path == "/api/incidents/acknowledge":
            with state_lock:
                active_hazard_alert["acknowledged"] = True
            self.send_json({"success": True, "message": "Incident acknowledged by operator."})

        else:
            self.send_error(404, "Endpoint not found")

    def stream_mjpeg(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.end_headers()

        while is_running:
            with state_lock:
                frame_data = latest_frame_jpeg

            if frame_data is not None:
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame_data)}\r\n\r\n".encode())
                    self.wfile.write(frame_data)
                    self.wfile.write(b"\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    break
            time.sleep(0.04)

    def serve_file(self, file_path, content_type):
        p = Path(file_path)
        if p.exists() and p.is_file():
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(p.stat().st_size))
            self.end_headers()
            with open(p, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File Not Found")

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        # Mute request logs for clean terminal
        return


def start_management_platform(port=8000):
    # Start video inference worker thread
    t = threading.Thread(target=video_inference_loop, daemon=True)
    t.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), ManagementAPIHandler)
    print("=" * 72)
    print("🚦 SMART HIGHWAY ROAD OBSTRUCTION MANAGEMENT SYSTEM (ITS PLATFORM)")
    print(f"   Local Access:      http://localhost:{port}")
    print(f"   Network Access:    http://10.19.102.140:{port} (or shared hotspot IP)")
    print("=" * 72)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    start_management_platform(port)

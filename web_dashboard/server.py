"""
Web-Based Highway Monitoring Dashboard (Objective 4)
Zero-dependency HTTP & MJPEG streaming server using Python's standard library.
Enables any mobile device, tablet, or browser on the shared hotspot
to monitor live road conditions, receive real-time audio/visual alerts,
and inspect historical incident snapshots.
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

# Add desktop_app to path for detector and incident db
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DESKTOP_DIR = PROJECT_DIR / "desktop_app"
sys.path.append(str(DESKTOP_DIR))

import config
from detector import RoadObstructionDetector
from incident_logger import IncidentDatabase

detector = RoadObstructionDetector()
incident_db = IncidentDatabase()

# Global state
latest_annotated_frame = None
current_alert_state = {
    "status": "CLEAR",
    "type": "NONE",
    "dist": "SAFE",
    "duration": 0.0,
    "sound": 0,
    "timestamp": time.time()
}
frame_lock = threading.Lock()
is_running = True

def video_processing_worker():
    """Continuously processes the street pole video or camera feed."""
    global latest_annotated_frame, current_alert_state, is_running
    video_path = config.SAMPLE_DATA_DIR / "street_pole_demo.mp4"
    
    # Calibrate street pole ROI
    w, h = 800, 600
    detector.set_roi([(int(px * w), int(py * h)) for px, py in config.POLE_ROI_NORMALIZED])
    
    while is_running:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_idx = 0
        
        while is_running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            t_sec = frame_idx / fps
            
            annotated_frame, alert_info = detector.process_frame(frame, timestamp=t_sec)
            alert_info["timestamp"] = time.time()
            
            with frame_lock:
                latest_annotated_frame = annotated_frame.copy()
                current_alert_state = alert_info.copy()
            
            # Log hazards to SQLite DB if danger detected
            if alert_info["status"] == "DANGER":
                incident_db.log_hazard(alert_info, frame=annotated_frame, node_id="POLE_04", lane="LANE_1")
                
            time.sleep(1.0 / 30.0)
            
        cap.release()
        time.sleep(0.5)


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Highway Obstruction Monitoring Dashboard</title>
    <style>
        :root {
            --bg: #0d1117;
            --card-bg: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --danger: #f85149;
            --warning: #d29922;
            --success: #3fb950;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg); color: var(--text); padding: 15px; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; margin-bottom: 20px; }
        h1 { font-size: 1.3rem; color: #f0f6fc; display: flex; align-items: center; gap: 10px; }
        .badge { padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; transition: background-color 0.3s; }
        .badge-clear { background: var(--success); color: white; }
        .badge-caution { background: var(--warning); color: black; }
        .badge-danger { background: var(--danger); color: white; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
        
        .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
        
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 15px; }
        .card h2 { font-size: 1rem; color: var(--accent); margin-bottom: 12px; }
        
        .video-box { position: relative; width: 100%; border-radius: 6px; overflow: hidden; background: black; text-align: center; }
        .video-box img { width: 100%; height: auto; display: block; }
        
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
        .metric-item { background: #21262d; padding: 10px; border-radius: 6px; border: 1px solid var(--border); }
        .metric-label { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; }
        .metric-val { font-size: 1.1rem; font-weight: bold; color: #f0f6fc; margin-top: 4px; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.85rem; }
        th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: #21262d; color: var(--accent); }
        tr:hover { background: #1f242c; }
        
        .audio-toggle { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.85rem; }
    </style>
</head>
<body>
    <header>
        <h1>🚗 SMART HIGHWAY ROAD OBSTRUCTION DASHBOARD</h1>
        <div style="display: flex; gap: 15px; align-items: center;">
            <label class="audio-toggle">
                <input type="checkbox" id="audioToggle" checked> 🔊 Audio Alerts
            </label>
            <div id="statusBadge" class="badge badge-clear">SYSTEM CLEAR</div>
        </div>
    </header>

    <div class="grid">
        <div>
            <div class="card">
                <h2>📹 Live Street Pole CCTV Video Feed (Pole-04)</h2>
                <div class="video-box">
                    <img src="/video_feed" alt="Live Street Pole CCTV Stream">
                </div>
                <div class="metrics-grid">
                    <div class="metric-item">
                        <div class="metric-label">Monitored Corridor</div>
                        <div class="metric-val">Highway N-12 (Lane 1 & 2)</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Wireless Comms</div>
                        <div class="metric-val">LoRa 433MHz + Wi-Fi UDP</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Current Hazard</div>
                        <div class="metric-val" id="hazardType">NONE</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-label">Stationary Timer</div>
                        <div class="metric-val" id="stationaryTimer">0.0s</div>
                    </div>
                </div>
            </div>
        </div>

        <div>
            <div class="card">
                <h2>💾 Recent Highway Incidents (SQLite DB)</h2>
                <div style="max-height: 480px; overflow-y: auto;">
                    <table>
                        <thead>
                            <tr><th>Time</th><th>Status</th><th>Object</th><th>Duration</th></tr>
                        </thead>
                        <tbody id="incidentsBody">
                            <tr><td colspan="4" style="text-align: center; color: #8b949e;">Loading records...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Web Audio API for browser alarms
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let lastSound = 0;

        function playTone(freq, dur) {
            if (!document.getElementById('audioToggle').checked) return;
            try {
                if (audioCtx.state === 'suspended') audioCtx.resume();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + dur);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start();
                osc.stop(audioCtx.currentTime + dur);
            } catch(e) {}
        }

        async function pollTelemetry() {
            try {
                const res = await fetch('/api/alerts');
                const data = await res.json();
                
                const badge = document.getElementById('statusBadge');
                const hType = document.getElementById('hazardType');
                const sTimer = document.getElementById('stationaryTimer');

                hType.textContent = data.type;
                sTimer.textContent = data.duration.toFixed(1) + 's';

                if (data.status === 'DANGER') {
                    badge.className = 'badge badge-danger';
                    badge.textContent = 'DANGER: OBSTRUCTION';
                    if (data.sound === 2 && lastSound !== 2) {
                        playTone(2200, 0.4);
                        setTimeout(() => playTone(1800, 0.4), 250);
                    }
                } else if (data.status === 'CAUTION') {
                    badge.className = 'badge badge-caution';
                    badge.textContent = 'CAUTION: SLOW OBJECT';
                    if (data.sound === 1 && lastSound !== 1) {
                        playTone(1500, 0.2);
                    }
                } else {
                    badge.className = 'badge badge-clear';
                    badge.textContent = 'SYSTEM CLEAR';
                }
                lastSound = data.sound;
            } catch(e) {}
        }

        async function loadIncidents() {
            try {
                const res = await fetch('/api/events');
                const rows = await res.json();
                const tbody = document.getElementById('incidentsBody');
                if (rows.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #8b949e;">No incidents recorded yet.</td></tr>';
                    return;
                }
                tbody.innerHTML = rows.slice(0, 10).map(r => `
                    <tr>
                        <td>${r[0].split(' ')[1] || r[0]}</td>
                        <td style="color: ${r[2] === 'DANGER' ? '#f85149' : '#d29922'}; font-weight: bold;">${r[2]}</td>
                        <td>${r[3]}</td>
                        <td>${r[5]}s</td>
                    </tr>
                `).join('');
            } catch(e) {}
        }

        setInterval(pollTelemetry, 300);
        setInterval(loadIncidents, 2500);
        loadIncidents();
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            
        elif parsed.path == "/api/alerts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with frame_lock:
                payload = json.dumps(current_alert_state)
            self.wfile.write(payload.encode("utf-8"))
            
        elif parsed.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            records = incident_db.get_recent_incidents(15)
            self.wfile.write(json.dumps(records).encode("utf-8"))
            
        elif parsed.path == "/video_feed":
            # Motion JPEG live stream
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            
            while is_running:
                with frame_lock:
                    if latest_annotated_frame is None:
                        frame_bytes = None
                    else:
                        ret, jpeg = cv2.imencode('.jpg', latest_annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        frame_bytes = jpeg.tobytes() if ret else None
                        
                if frame_bytes is not None:
                    try:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode())
                        self.wfile.write(frame_bytes)
                        self.wfile.write(b"\r\n")
                    except (BrokenPipeError, ConnectionResetError):
                        break
                time.sleep(0.04)
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # Suppress spammy request logs
        return


def run_web_dashboard(port=5000):
    # Start video processing thread
    t = threading.Thread(target=video_processing_worker, daemon=True)
    t.start()
    
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    print("=" * 65)
    print(f"🌐 SMART HIGHWAY WEB-BASED DASHBOARD (Objective 4)")
    print(f"   Local URL:    http://localhost:{port}")
    print(f"   Hotspot URL:  http://10.19.102.140:{port} (or your hotspot IP)")
    print("=" * 65)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    run_web_dashboard(port)

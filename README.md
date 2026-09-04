# Smart IoT-Based Highway Road Obstruction Detection & Driver Alert System

An end-to-end IoT highway road safety system prototype integrating an **ESP32-CAM optical sensing unit**, an **in-cabin ESP32 driver warning receiver**, **dual wireless communication (LoRa 433MHz + Wi-Fi UDP)**, and a **minimalist professional IoT fleet management web platform** with automated **Dokploy PostgreSQL photo & event persistence**.

---

## 🌟 System Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                           STREET POLE SENSING NODE                                |
| - ESP32-CAM (Elevated at 6m overlooking Highway Corridor N-12)                    |
| - Local MJPEG Stream / Snapshot Capture (Port 81)                                 |
| - Static Road Background Modeling & Differential Subtraction (Edge CV)            |
+-----------------------------------------+-----------------------------------------+
                                          |
                        Instantaneous Alert Broadcast (<1ms)
                                          |
                    +---------------------+---------------------+
                    |                                           |
                    v (LoRa 433MHz + Wi-Fi UDP)                 v (HTTP / REST API)
+---------------------------------------+   +---------------------------------------+
|        IN-CABIN DRIVER ALERT UNIT     |   |    MINIMALIST WHITE IoT DASHBOARD     |
| - ESP32 Dual-Radio Receiver           |   | - Live Highway Video & Status         |
| - 16x2 I2C Backlit Character LCD      |   | - One-Click Road Calibration          |
| - Active Piezo Buzzer Warning         |   | - Hardware Fleet Health Monitoring    |
| - High-Intensity Warning LEDs         |   | - Dokploy PostgreSQL Photo Ledger     |
+---------------------------------------+   +-------------------+-------------------+
                                                                |
                                                                v
                                            +---------------------------------------+
                                            |       DOKPLOY POSTGRESQL DATABASE     |
                                            | - Tables: devices, incident_logs      |
                                            | - photo_base64: Photographic Evidence |
                                            +---------------------------------------+
```

---

## 🚀 Key Features

1. **Stationary Obstruction Detection**:
   - Uses static background reference modeling (`absdiff` differential subtraction against clean road baseline + morphological filtering).
   - Monitors highway lane region of interest (ROI) and flags stationary hazards persisting $> 2.5\text{s}$.
2. **Dual High-Speed Alert Dispatch**:
   - Dispatches simultaneous warning packets across **LoRa 433MHz UART** and **Wi-Fi UDP port 8888** in $< 1\text{ms}$.
3. **In-Cabin Driver Warning Unit**:
   - ESP32 hardware receiver displays warning messages on 16x2 LCD and sounds an active piezo buzzer upon detection.
4. **Minimalist Professional Web Platform**:
   - Clean, unified single-screen dashboard (white theme, zero clutter).
   - Front-and-center live video feed with overlay status badge (`LANE CLEAR` vs `OBSTRUCTION DETECTED`).
   - One-click **"🎯 Calibrate Road Background"** button.
   - Connected device monitoring with one-click **"🔊 Test Alarm"** trigger.
   - Photo evidence ledger with click-to-expand lightbox.
5. **Dokploy PostgreSQL Integration**:
   - Automatically connects to PostgreSQL and stores incident logs along with full Base64-encoded photographic evidence.

---

## 💻 Quick Start

### 1. Run the Web Management Platform
```bash
./run.sh
```
Or directly:
```bash
python3 iot_management_app/backend/server.py 9000
```
Open your browser at:
- **Local**: `http://localhost:9000`
- **Network**: `http://10.19.102.140:9000`

### 2. Configure Dokploy PostgreSQL Database
Set the connection URI in `iot_management_app/.env`:
```env
DATABASE_URL=postgresql://ike:obs1000@178.105.184.157:5600/obs
```
The server will automatically connect and synchronize tables on startup.

---

## 📁 Repository Structure

```
├── iot_management_app/
│   ├── frontend/
│   │   ├── index.html       # Clean unified highway monitor
│   │   ├── css/style.css    # Minimalist white SaaS styling
│   │   └── js/app.js        # Stream controller & real-time telemetry
│   └── backend/
│       ├── server.py        # High-speed HTTP/MJPEG streaming & REST API
│       └── postgres_db.py   # Dokploy PostgreSQL driver with connection reuse
├── desktop_app/
│   ├── detector.py          # Background subtraction & YOLO obstruction engine
│   ├── network_hub.py       # LoRa & Wi-Fi dual-packet broadcaster
│   ├── incident_logger.py   # SQLite & snapshot backup logger
│   └── config.py            # Highway lane ROI and threshold parameters
├── esp32_cam/
│   ├── esp32_cam_streamer.ino # ESP32-CAM sketch for /stream and /capture
│   └── camera_pins.h          # AI Thinker pin definitions
├── esp32_receiver/
│   └── esp32_receiver.ino     # ESP32 in-cabin driver alert receiver sketch
├── run.sh                   # One-command system launcher
└── README.md
```

---

## 🛠️ Hardware Setup

1. **Street Pole Camera Node**:
   - Board: AI Thinker ESP32-CAM (or USB/V4L2 camera on edge processor).
   - Flashed with `esp32_cam/esp32_cam_streamer.ino`.
   - Default Stream URL: `http://<ESP32_IP>:81/stream`.
2. **Driver Alert Unit**:
   - Board: ESP32 Dev Module + LoRa SX1278 (433MHz) + 16x2 I2C LCD + Active Buzzer.
   - Flashed with `esp32_receiver/esp32_receiver.ino`.
   - Listens on LoRa UART and Wi-Fi UDP port 8888.
3. **Hotspot Credentials**:
   - SSID: `RoadAlertHotspot`
   - Password: `RoadAlertPassword123`

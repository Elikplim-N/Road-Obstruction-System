# Road Obstruction Detection System Architecture

## 1. System Overview

This prototype integrates three nodes communicating over a **shared mobile or Wi-Fi hotspot**:

```
                              +-------------------------+
                              |   SHARED WI-FI HOTSPOT  |
                              |  SSID: RoadAlertHotspot |
                              |  Subnet: 192.168.43.x   |
                              +------------+------------+
                                           |
               +---------------------------+---------------------------+
               |                                                       |
               v                                                       v
+-----------------------------+                         +-----------------------------+
| ESP32-CAM Pole Node (Node 1)|                         |   ESP32 Receiver (Node 2)   |
| - Stationed on Street Pole  |                         | - IP: 192.168.43.100 (DHCP) |
|   (Elevated 4-6m CCTV view) |                         | - Upstream Warning Sign or  |
| - IP: 192.168.43.50 (DHCP)  |                         |   In-Vehicle Dashboard Unit |
| - Streams MJPEG video at    |                         | - I2C 16x2 LCD / 0.96" OLED |
|   port 81 (/stream)         |                         | - Piezo Buzzer & Alert LEDs |
| - Covers both driving lanes |                         | - Listens on UDP port 8888  |
+--------------+--------------+                         +--------------^--------------+
               |                                                       |
               | MJPEG Video Stream                                    | Low-Latency UDP
               | (HTTP / WiFi)                                         | Alert Packets
               v                                                       |
+----------------------------------------------------------------------+--------------+
|                         DESKTOP COMPUTER (AI Hub / Node 3)                          |
| - IP: 192.168.43.200                                                                |
| - Video Ingestion: Live ESP32-CAM stream, Local Webcam, or Pre-recorded video clips |
| - AI Engine: YOLOv8 / YOLO11 Real-time Object Detection                             |
| - Hazard Analytics: Polygon Road ROI, Stationary Obstacle Tracking, Collision TTC  |
| - PyQt6 Modern Dashboard: Real-time video overlay, metrics, event logging           |
| - Network Dispatcher: Instant UDP broadcasting to ESP32 Receiver(s)                 |
+-------------------------------------------------------------------------------------+
```

---

## 2. Communication Protocols Over Shared Hotspot

### A. Video Stream (ESP32-CAM -> Desktop)
- **Protocol**: HTTP Motion JPEG (MJPEG)
- **URL**: `http://<ESP32_CAM_IP>:81/stream` (or `/cam-hi.jpg` snapshot polling)
- **Resolution**: VGA (640x480) or QVGA (320x240) at 15–25 FPS for stable transmission over hotspot.

### B. Warning / Alert Telemetry (Desktop -> ESP32 Receiver)
- **Protocol**: UDP Datagrams (Fast, zero-handshake, low latency < 5ms)
- **Port**: `8888`
- **JSON Payload Format**:
  ```json
  {
    "status": "DANGER",         // "CLEAR", "CAUTION", "DANGER"
    "type": "STALLED_CAR",      // "NONE", "STALLED_CAR", "PEDESTRIAN", "DEBRIS"
    "dist": "CLOSE",            // "FAR", "MEDIUM", "CLOSE", "IMMINENT"
    "duration": 4.2,            // seconds object has been stopped in lane
    "sound": 2                  // 0: silent, 1: slow beep, 2: urgent siren
  }
  ```

---

## 3. Migration to LoRa (Future Expansion)
When replacing the Hotspot link with LoRa:
- The Desktop connects to a **LoRa USB dongle** (e.g. Reyax RYLR896 or ESP32-LoRa transmitter via UART).
- The ESP32 Receiver replaces the Wi-Fi UDP listener with a LoRa receiver module (e.g. SX1276 / SX1278 or RYLR896 via UART/SPI).
- The alert payload packet structure remains identical.

"""
Configuration parameters for Desktop Road Object Obstruction Detection System
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"
SAMPLE_DATA_DIR.mkdir(exist_ok=True)

# Hotspot Networking
DEFAULT_HOTSPOT_SSID = "RoadAlertHotspot"
DEFAULT_ESP32_CAM_URL = "http://192.168.43.50:81/stream"
DEFAULT_RECEIVER_UDP_IP = "255.255.255.255"  # Broadcast to entire hotspot subnet
DEFAULT_RECEIVER_UDP_PORT = 8888

# AI Model Configuration
YOLO_MODEL_NAME = "yolov8n.pt"  # Lightweight nano model for high FPS on CPU/GPU
CONFIDENCE_THRESHOLD = 0.40
IOU_THRESHOLD = 0.45

# Road Obstruction Parameters
STATIONARY_SECONDS_THRESHOLD = 2.5  # Seconds before stationary vehicle triggers OBSTRUCTION ALERT
MOTION_PIXEL_THRESHOLD = 15.0       # Max pixel drift to still be considered stationary
ZONE_NEAR_Y_RATIO = 0.70            # Y-coord ratio threshold for "CLOSE" hazard

# Classes of interest from COCO dataset
TARGET_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    16: "dog",
    17: "horse",
}

# Road ROI Polygons (normalized points [x, y] in range 0.0 - 1.0)
# 1. Street Pole Vantage View (Full aerial road corridor)
POLE_ROI_NORMALIZED = [
    (0.12, 0.02),  # Top Left
    (0.88, 0.02),  # Top Right
    (0.96, 0.98),  # Bottom Right
    (0.04, 0.98)   # Bottom Left
]

# 2. Vehicle Forward View (Dashcam trapezoid perspective)
DEFAULT_ROI_NORMALIZED = [
    (0.20, 0.95),  # Bottom Left
    (0.40, 0.50),  # Top Left
    (0.60, 0.50),  # Top Right
    (0.80, 0.95)   # Bottom Right
]

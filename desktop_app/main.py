"""
Desktop Road Object Obstruction Detection System
Final Production Application (PyQt6 / PyQt5 Compatible)
Features:
- Live Street Pole Vision & Obstruction Detection Engine
- Dual Wireless Transmitter: Wi-Fi Hotspot (UDP) + LoRa Radio (Serial AT)
- Virtual ESP32 Hardware Receiver Emulator (16x2 LCD + LEDs + Siren)
- Persistent SQLite / CSV Storage & Evidence Image Viewer
"""

import sys
import os
import time
import cv2
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QLineEdit, QTableWidget,
        QTableWidgetItem, QFileDialog, QHeaderView, QSplitter,
        QGroupBox, QSlider, QCheckBox, QMessageBox, QTabWidget,
        QScrollArea, QFrame
    )
    from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QPoint
    from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    KEEP_ASPECT = Qt.AspectRatioMode.KeepAspectRatio
    SMOOTH_TRANSFORM = Qt.TransformationMode.SmoothTransformation
except ImportError:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QComboBox, QLineEdit, QTableWidget,
        QTableWidgetItem, QFileDialog, QHeaderView, QSplitter,
        QGroupBox, QSlider, QCheckBox, QMessageBox, QTabWidget,
        QScrollArea, QFrame
    )
    from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QPoint
    from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QPen
    ALIGN_CENTER = Qt.AlignCenter
    KEEP_ASPECT = Qt.KeepAspectRatio
    SMOOTH_TRANSFORM = Qt.SmoothTransformation

from detector import RoadObstructionDetector
from network_hub import DualBroadcaster, ESP32CamStreamer
from virtual_esp32_receiver import VirtualESP32Receiver
from incident_logger import IncidentDatabase
from generate_demo_clip import create_synthetic_road_clip
from generate_pole_clip import create_street_pole_clip
import config

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0f1115;
}
QWidget {
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QTabWidget::pane {
    border: 1px solid #232832;
    background-color: #14171d;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #1a1e24;
    color: #88c0d0;
    padding: 9px 22px;
    margin-right: 3px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #2e3440;
    color: #eceff4;
    border-bottom: 2px solid #88c0d0;
}
QGroupBox {
    border: 1px solid #282f3a;
    border-radius: 8px;
    margin-top: 14px;
    font-weight: bold;
    color: #88c0d0;
    padding: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QPushButton {
    background-color: #242b35;
    border: 1px solid #3b4252;
    border-radius: 5px;
    color: #eceff4;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #3b4252;
    border-color: #88c0d0;
}
QPushButton:pressed {
    background-color: #4c566a;
}
QPushButton#dangerBtn {
    background-color: #bf616a;
    border-color: #d08770;
}
QPushButton#successBtn {
    background-color: #2e7d32;
    border-color: #4caf50;
}
QLineEdit, QComboBox {
    background-color: #1a1e24;
    border: 1px solid #3b4252;
    border-radius: 4px;
    padding: 6px;
    color: #ffffff;
}
QTableWidget {
    background-color: #16191f;
    border: 1px solid #282f3a;
    gridline-color: #282f3a;
    color: #d8dee9;
    border-radius: 4px;
}
QHeaderView::section {
    background-color: #1e232b;
    color: #88c0d0;
    padding: 6px;
    border: 1px solid #282f3a;
    font-weight: bold;
}
"""

class VideoDisplayWidget(QLabel):
    roi_updated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(ALIGN_CENTER)
        self.setStyleSheet("background-color: #0b0d10; border: 2px solid #202630; border-radius: 8px;")
        self.setMinimumSize(640, 420)
        self.roi_editing = False
        self.roi_points = []

    def mousePressEvent(self, event):
        if self.roi_editing and event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            w = max(1, self.width())
            h = max(1, self.height())
            nx = pos.x() / w
            ny = pos.y() / h
            self.roi_points.append((nx, ny))
            if len(self.roi_points) == 4:
                self.roi_editing = False
                self.roi_updated.emit(self.roi_points)
            self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Highway Road Obstruction Detection & LoRa Alert System")
        self.resize(1360, 860)
        self.setStyleSheet(DARK_STYLESHEET)

        # Core Components
        self.detector = RoadObstructionDetector()
        self.incident_db = IncidentDatabase()
        self.broadcaster = DualBroadcaster(
            wifi_broadcast_ip=config.DEFAULT_RECEIVER_UDP_IP,
            wifi_port=config.DEFAULT_RECEIVER_UDP_PORT
        )
        self.video_cap = None
        self.is_playing = False
        self.packets_sent_count = 0
        self.latest_frame = None

        # Verify demo clips
        self.pole_video_path = config.SAMPLE_DATA_DIR / "street_pole_demo.mp4"
        if not self.pole_video_path.exists():
            create_street_pole_clip(self.pole_video_path)

        self.dashcam_video_path = config.SAMPLE_DATA_DIR / "road_obstruction_demo.mp4"
        if not self.dashcam_video_path.exists():
            create_synthetic_road_clip(self.dashcam_video_path)

        self.current_video_file = str(self.pole_video_path)

        self.init_ui()

        # Timer for ~30 FPS loop
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_next_frame)

        # Initial source setup
        self.load_video_source(self.current_video_file)
        self._apply_normalized_roi(config.POLE_ROI_NORMALIZED)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # Global Header
        header = QHBoxLayout()
        title_lbl = QLabel("🚗 SMART HIGHWAY ROAD OBSTRUCTION & DRIVER ALERT SYSTEM")
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #88c0d0; padding: 4px;")
        header.addWidget(title_lbl)

        header.addStretch()

        self.comm_badge_wifi = QLabel("Wi-Fi: READY")
        self.comm_badge_wifi.setStyleSheet("background-color: #2b3a4a; color: #88c0d0; padding: 5px 12px; border-radius: 12px; font-weight: bold;")
        header.addWidget(self.comm_badge_wifi)

        self.comm_badge_lora = QLabel("LoRa: STANDBY")
        self.comm_badge_lora.setStyleSheet("background-color: #3b332b; color: #ebcb8b; padding: 5px 12px; border-radius: 12px; font-weight: bold;")
        header.addWidget(self.comm_badge_lora)

        self.global_status_pill = QLabel("SYSTEM: READY")
        self.global_status_pill.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.global_status_pill.setStyleSheet("background-color: #2e7d32; color: white; padding: 6px 16px; border-radius: 14px; font-weight: bold;")
        header.addWidget(self.global_status_pill)
        root_layout.addLayout(header)

        # Main Tabs: 1. Live Vision & Operations | 2. Storage & Evidence Database
        self.tabs = QTabWidget()

        # TAB 1: LIVE VISION & DETECTION
        tab_vision = QWidget()
        tab_vision_layout = QVBoxLayout(tab_vision)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Video & Controls
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)

        self.video_canvas = VideoDisplayWidget()
        self.video_canvas.roi_updated.connect(self.on_roi_customized)
        left_layout.addWidget(self.video_canvas, stretch=5)

        # Controls Group
        ctrl_box = QGroupBox("Camera Feed & Road Corridor Calibration")
        ctrl_layout = QVBoxLayout(ctrl_box)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Video Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems([
            "Street Pole View (Elevated 45° - Stalled Car in Lane 1)",
            "Vehicle Forward View (Dashcam Perspective)",
            "Local Video File (.mp4/.avi)",
            "ESP32-CAM Stream (Street Pole Node via Hotspot)",
            "USB / Local Webcam (Live Camera)"
        ])
        self.source_combo.currentIndexChanged.connect(self.on_source_changed)
        r1.addWidget(self.source_combo, stretch=3)

        self.btn_browse = QPushButton("📁 Browse")
        self.btn_browse.clicked.connect(self.browse_video_file)
        self.btn_browse.setEnabled(False)
        r1.addWidget(self.btn_browse)

        self.btn_play_pause = QPushButton("▶ Play Feed")
        self.btn_play_pause.setObjectName("successBtn")
        self.btn_play_pause.clicked.connect(self.toggle_playback)
        r1.addWidget(self.btn_play_pause)

        self.btn_reset = QPushButton("↺ Restart")
        self.btn_reset.clicked.connect(self.restart_video)
        r1.addWidget(self.btn_reset)
        ctrl_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Live URL/IP:"))
        self.cam_url_edit = QLineEdit(config.DEFAULT_ESP32_CAM_URL)
        r2.addWidget(self.cam_url_edit, stretch=2)

        self.btn_scan_cam = QPushButton("🔍 Auto-Detect ESP32-CAM")
        self.btn_scan_cam.clicked.connect(self.scan_for_esp32_cam)
        r2.addWidget(self.btn_scan_cam)

        self.btn_roi = QPushButton("📐 Calibrate Lane ROI")
        self.btn_roi.clicked.connect(self.start_roi_edit)
        r2.addWidget(self.btn_roi)

        self.btn_reset_roi = QPushButton("Reset ROI")
        self.btn_reset_roi.clicked.connect(self.reset_roi_default)
        r2.addWidget(self.btn_reset_roi)
        ctrl_layout.addLayout(r2)

        left_layout.addWidget(ctrl_box)
        splitter.addWidget(left_box)

        # Right Column: Virtual ESP32 & Dual Wireless Comms
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)

        # Virtual ESP32 Hardware
        self.virtual_esp32 = VirtualESP32Receiver(listen_udp=True, udp_port=config.DEFAULT_RECEIVER_UDP_PORT)
        right_layout.addWidget(self.virtual_esp32)

        # Dual Comms Panel (Wi-Fi + LoRa)
        comms_box = QGroupBox("Dual Wireless Dispatcher (Wi-Fi Hotspot + LoRa Radio)")
        comms_layout = QVBoxLayout(comms_box)

        wifi_row = QHBoxLayout()
        self.chk_wifi = QCheckBox("Wi-Fi Hotspot UDP")
        self.chk_wifi.setChecked(True)
        self.chk_wifi.stateChanged.connect(self.toggle_wifi_broadcast)
        wifi_row.addWidget(self.chk_wifi)
        wifi_row.addWidget(QLabel("IP:"))
        self.net_ip_edit = QLineEdit(config.DEFAULT_RECEIVER_UDP_IP)
        self.net_ip_edit.setMaximumWidth(120)
        wifi_row.addWidget(self.net_ip_edit)
        wifi_row.addWidget(QLabel("Port:"))
        self.net_port_edit = QLineEdit(str(config.DEFAULT_RECEIVER_UDP_PORT))
        self.net_port_edit.setMaximumWidth(60)
        wifi_row.addWidget(self.net_port_edit)
        comms_layout.addLayout(wifi_row)

        lora_row = QHBoxLayout()
        self.chk_lora = QCheckBox("LoRa Radio Link")
        self.chk_lora.setChecked(True)
        lora_row.addWidget(self.chk_lora)
        lora_row.addWidget(QLabel("Port:"))
        self.lora_port_combo = QComboBox()
        self.refresh_lora_ports()
        lora_row.addWidget(self.lora_port_combo, stretch=1)
        self.btn_connect_lora = QPushButton("Connect LoRa")
        self.btn_connect_lora.clicked.connect(self.toggle_lora_connection)
        lora_row.addWidget(self.btn_connect_lora)
        comms_layout.addLayout(lora_row)

        self.net_stat_lbl = QLabel("Packets Broadcasted: 0 | Dispatcher Ready")
        self.net_stat_lbl.setStyleSheet("color: #a3be8c; font-size: 11px;")
        comms_layout.addWidget(self.net_stat_lbl)

        right_layout.addWidget(comms_box)

        # Live Alert Incident Feed
        log_box = QGroupBox("Active Hazard Stream")
        log_layout = QVBoxLayout(log_box)

        self.live_table = QTableWidget(0, 4)
        self.live_table.setHorizontalHeaderLabels(["Time", "Status", "Hazard Type", "Proximity"])
        self.live_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        log_layout.addWidget(self.live_table)

        btn_row = QHBoxLayout()
        self.btn_save_snap = QPushButton("📸 Snapshot Now")
        self.btn_save_snap.clicked.connect(self.capture_manual_snapshot)
        btn_row.addWidget(self.btn_save_snap)

        self.btn_view_storage = QPushButton("📂 Open Storage Tab")
        self.btn_view_storage.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        btn_row.addWidget(self.btn_view_storage)
        log_layout.addLayout(btn_row)

        right_layout.addWidget(log_box)

        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 4)
        tab_vision_layout.addWidget(splitter)

        self.tabs.addTab(tab_vision, "📹 Live Detection & Operations")

        # TAB 2: STORAGE & HISTORICAL EVIDENCE DATABASE
        tab_storage = QWidget()
        tab_storage_layout = QVBoxLayout(tab_storage)

        # Top stats banner
        stats_box = QHBoxLayout()
        self.stat_total_lbl = QLabel("Total Incidents Recorded: 0")
        self.stat_total_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.stat_total_lbl.setStyleSheet("background-color: #1f2530; padding: 10px; border-radius: 6px; border: 1px solid #3b4252;")
        stats_box.addWidget(self.stat_total_lbl)

        self.stat_db_path = QLabel(f"SQLite DB: {self.incident_db.db_path.name} | CSV: {self.incident_db.csv_path.name}")
        self.stat_db_path.setStyleSheet("color: #88c0d0; padding: 10px;")
        stats_box.addWidget(self.stat_db_path)

        stats_box.addStretch()

        self.btn_refresh_db = QPushButton("🔄 Refresh Records")
        self.btn_refresh_db.clicked.connect(self.reload_storage_table)
        stats_box.addWidget(self.btn_refresh_db)

        self.btn_export_csv = QPushButton("📊 Export CSV")
        self.btn_export_csv.clicked.connect(self.export_csv_action)
        stats_box.addWidget(self.btn_export_csv)

        tab_storage_layout.addLayout(stats_box)

        # Splitter between DB Table and Snapshot Evidence Viewer
        storage_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: SQLite Table
        table_box = QGroupBox("Relational Incident Records (SQLite)")
        tbl_layout = QVBoxLayout(table_box)
        self.db_table = QTableWidget(0, 7)
        self.db_table.setHorizontalHeaderLabels(["Timestamp", "Node ID", "Status", "Hazard Type", "Lane", "Duration (s)", "Zone"])
        self.db_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.db_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.db_table.cellClicked.connect(self.on_db_row_selected)
        tbl_layout.addWidget(self.db_table)
        storage_splitter.addWidget(table_box)

        # Right: Photographic Evidence Preview
        preview_box = QGroupBox("Photographic Hazard Evidence (Stored Snapshot)")
        prv_layout = QVBoxLayout(preview_box)
        self.snapshot_viewer = QLabel("Select an incident row to inspect photographic evidence.")
        self.snapshot_viewer.setAlignment(ALIGN_CENTER)
        self.snapshot_viewer.setStyleSheet("background-color: #0b0d10; border: 2px dashed #3b4252; border-radius: 6px;")
        self.snapshot_viewer.setMinimumSize(420, 320)
        prv_layout.addWidget(self.snapshot_viewer)

        self.snapshot_details_lbl = QLabel("Snapshot File: ---")
        self.snapshot_details_lbl.setStyleSheet("color: #d8dee9; font-size: 11px;")
        prv_layout.addWidget(self.snapshot_details_lbl)

        storage_splitter.addWidget(preview_box)
        storage_splitter.setStretchFactor(0, 6)
        storage_splitter.setStretchFactor(1, 4)

        tab_storage_layout.addWidget(storage_splitter)

        self.tabs.addTab(tab_storage, "💾 Storage & Evidence Database (Obj 6)")

        root_layout.addWidget(self.tabs)
        self.reload_storage_table()

    def refresh_lora_ports(self):
        self.lora_port_combo.clear()
        try:
            import serial.tools.list_ports
            ports = [p.device for p in serial.tools.list_ports.comports()]
            if not ports:
                ports = ["/dev/ttyUSB0", "/dev/ttyACM0", "COM1", "COM3"]
            self.lora_port_combo.addItems(ports)
        except Exception:
            self.lora_port_combo.addItems(["/dev/ttyUSB0", "/dev/ttyACM0"])

    def toggle_lora_connection(self):
        if not self.broadcaster.lora.connected:
            port = self.lora_port_combo.currentText().strip()
            ok, msg = self.broadcaster.lora.connect(port, 115200)
            if ok:
                self.btn_connect_lora.setText("Disconnect LoRa")
                self.btn_connect_lora.setObjectName("dangerBtn")
                self.comm_badge_lora.setText(f"LoRa: {port} (115200)")
                self.comm_badge_lora.setStyleSheet("background-color: #2e7d32; color: white; padding: 5px 12px; border-radius: 12px; font-weight: bold;")
                QMessageBox.information(self, "LoRa Connected", f"LoRa Transceiver connected on {port}!")
            else:
                QMessageBox.warning(self, "LoRa Connection Failed", f"Could not open {port}:\n{msg}\nEnsure the LoRa module is plugged into USB.")
        else:
            self.broadcaster.lora.disconnect()
            self.btn_connect_lora.setText("Connect LoRa")
            self.btn_connect_lora.setObjectName("")
            self.comm_badge_lora.setText("LoRa: STANDBY")
            self.comm_badge_lora.setStyleSheet("background-color: #3b332b; color: #ebcb8b; padding: 5px 12px; border-radius: 12px; font-weight: bold;")

    def toggle_wifi_broadcast(self, state):
        self.broadcaster.wifi_enabled = (state == 2 or state is True)
        if self.broadcaster.wifi_enabled:
            self.comm_badge_wifi.setText("Wi-Fi: READY")
            self.comm_badge_wifi.setStyleSheet("background-color: #2b3a4a; color: #88c0d0; padding: 5px 12px; border-radius: 12px; font-weight: bold;")
        else:
            self.comm_badge_wifi.setText("Wi-Fi: DISABLED")
            self.comm_badge_wifi.setStyleSheet("background-color: #4c566a; color: #d8dee9; padding: 5px 12px; border-radius: 12px;")

    def reload_storage_table(self):
        records = self.incident_db.get_recent_incidents(50)
        self.db_table.setRowCount(len(records))
        for row_idx, r in enumerate(records):
            for col_idx, val in enumerate(r):
                self.db_table.setItem(row_idx, col_idx, QTableWidgetItem(str(val)))

        stats = self.incident_db.get_summary_statistics()
        self.stat_total_lbl.setText(f"Total Incidents Recorded: {stats['total_incidents']} | Avg Duration: {stats['avg_duration']}s")

    def on_db_row_selected(self, row, column):
        # Query snapshot filename for this row
        timestamp_str = self.db_table.item(row, 0).text() if self.db_table.item(row, 0) else ""
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.incident_db.db_path))
            c = conn.cursor()
            c.execute("SELECT snapshot_filename FROM incidents WHERE timestamp = ?", (timestamp_str,))
            res = c.fetchone()
            conn.close()
            if res and res[0]:
                snap_path = self.incident_db.snapshots_dir / res[0]
                if snap_path.exists():
                    pix = QPixmap(str(snap_path))
                    self.snapshot_viewer.setPixmap(pix.scaled(
                        self.snapshot_viewer.size(), KEEP_ASPECT, SMOOTH_TRANSFORM
                    ))
                    self.snapshot_details_lbl.setText(f"Evidence Image: {res[0]} (Saved at {timestamp_str})")
                    return
        except Exception:
            pass

        self.snapshot_viewer.setText("Snapshot image not found for this event.")
        self.snapshot_details_lbl.setText("Snapshot File: ---")

    def export_csv_action(self):
        if self.incident_db.csv_path.exists():
            QMessageBox.information(
                self, "CSV Export",
                f"Incident records are continuously persisted in CSV format at:\n{self.incident_db.csv_path}"
            )

    def load_video_source(self, path_or_index):
        if self.video_cap:
            self.video_cap.release()
        self.video_cap = cv2.VideoCapture(path_or_index)

    def on_source_changed(self, index):
        self.stop_playback()
        self.btn_browse.setEnabled(index == 2)

        if index == 0:  # Street Pole View
            self.current_video_file = str(self.pole_video_path)
            self.load_video_source(self.current_video_file)
            self._apply_normalized_roi(config.POLE_ROI_NORMALIZED)
        elif index == 1:  # Vehicle Forward View
            self.current_video_file = str(self.dashcam_video_path)
            self.load_video_source(self.current_video_file)
            self._apply_normalized_roi(config.DEFAULT_ROI_NORMALIZED)
        elif index == 2:  # Custom file
            self.browse_video_file()
        elif index == 3:  # ESP32-CAM stream
            url = self.cam_url_edit.text().strip()
            self.load_video_source(url)
            self._apply_normalized_roi(config.POLE_ROI_NORMALIZED)
        elif index == 4:  # Local/USB Camera
            cam_idx = self.find_working_camera()
            self.load_video_source(cam_idx)
            self._apply_normalized_roi(config.POLE_ROI_NORMALIZED)

    def find_working_camera(self):
        for idx in [1, 0, 2, 3]:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    return idx
        return 0

    def scan_for_esp32_cam(self):
        import socket, concurrent.futures
        self.btn_scan_cam.setText("Scanning...")
        QApplication.processEvents()

        found_ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "192.168.43.1"

        prefix = '.'.join(local_ip.split('.')[:3])

        def check_target(host):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.2)
                res = sock.connect_ex((host, 81))
                sock.close()
                return host if res == 0 else None
            except:
                return None

        targets = [f"{prefix}.{i}" for i in range(1, 255)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            for ip in executor.map(check_target, targets):
                if ip:
                    found_ip = ip
                    break

        self.btn_scan_cam.setText("🔍 Auto-Detect ESP32-CAM")
        if found_ip:
            stream_url = f"http://{found_ip}:81/stream"
            self.cam_url_edit.setText(stream_url)
            self.source_combo.setCurrentIndex(3)
            self.load_video_source(stream_url)
            QMessageBox.information(self, "ESP32-CAM Discovered!", f"Found ESP32-CAM streaming at:\n{stream_url}\nLoaded automatically!")
        else:
            QMessageBox.warning(self, "Not Found", f"No ESP32-CAM found on subnet {prefix}.0/24.\nEnsure ESP32-CAM is connected to the hotspot, or enter its IP manually.")

    def _apply_normalized_roi(self, norm_pts):
        if self.video_cap:
            w = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 800)
            h = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 600)
            abs_pts = [(int(nx * w), int(ny * h)) for nx, ny in norm_pts]
            self.detector.set_roi(abs_pts)

    def browse_video_file(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if fname:
            self.current_video_file = fname
            self.load_video_source(fname)

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        self.is_playing = True
        self.btn_play_pause.setText("⏸ Pause")
        self.btn_play_pause.setObjectName("dangerBtn")
        self.btn_play_pause.setStyle(self.btn_play_pause.style())
        self.timer.start(33)

    def stop_playback(self):
        self.is_playing = False
        self.btn_play_pause.setText("▶ Play Feed")
        self.btn_play_pause.setObjectName("successBtn")
        self.btn_play_pause.setStyle(self.btn_play_pause.style())
        self.timer.stop()

    def restart_video(self):
        if self.video_cap:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not self.is_playing:
            self.start_playback()

    def process_next_frame(self):
        if not self.video_cap:
            return

        ret, frame = self.video_cap.read()
        if not ret:
            if self.source_combo.currentIndex() in [0, 1]:
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_cap.read()
            if not ret:
                self.stop_playback()
                return

        # AI Detection & Obstruction Logic
        if self.source_combo.currentIndex() in [0, 1]:
            pos_msec = self.video_cap.get(cv2.CAP_PROP_POS_MSEC)
            t_sec = (pos_msec / 1000.0) if pos_msec > 0 else time.time()
            annotated_frame, alert_info = self.detector.process_frame(frame, timestamp=t_sec)
        else:
            annotated_frame, alert_info = self.detector.process_frame(frame, timestamp=None)

        self.latest_frame = annotated_frame

        # Dispatch alert concurrently via Dual Wi-Fi & LoRa Broadcaster
        target_ip = self.net_ip_edit.text().strip()
        target_port = int(self.net_port_edit.text().strip() or 8888)
        self.broadcaster.wifi.broadcast_ip = target_ip
        self.broadcaster.wifi.port = target_port

        self.broadcaster.send_alert(
            status=alert_info["status"],
            obj_type=alert_info["type"],
            dist=alert_info["dist"],
            duration=alert_info["duration"],
            sound=alert_info["sound"]
        )
        self.packets_sent_count += 1
        lora_stat = "CONNECTED" if self.broadcaster.lora.connected else "STANDBY"
        self.net_stat_lbl.setText(f"Packets Broadcasted: {self.packets_sent_count} | Wi-Fi: Active | LoRa: {lora_stat}")

        # Sync Virtual ESP32 Hardware Simulator
        self.virtual_esp32.apply_packet(alert_info)

        # Update System Status Pill
        status = alert_info["status"]
        if status == "DANGER":
            self.global_status_pill.setText(f"DANGER: {alert_info['type']}")
            self.global_status_pill.setStyleSheet("background-color: #bf616a; color: white; padding: 6px 16px; border-radius: 14px; font-weight: bold;")
            self._log_incident_if_new(alert_info)
        elif status == "CAUTION":
            self.global_status_pill.setText(f"CAUTION: {alert_info['type']}")
            self.global_status_pill.setStyleSheet("background-color: #d08770; color: white; padding: 6px 16px; border-radius: 14px; font-weight: bold;")
        else:
            self.global_status_pill.setText("SYSTEM: CLEAR")
            self.global_status_pill.setStyleSheet("background-color: #2e7d32; color: white; padding: 6px 16px; border-radius: 14px; font-weight: bold;")

        # Render annotated frame to screen
        rgb_frame = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.video_canvas.setPixmap(pix.scaled(
            self.video_canvas.size(), KEEP_ASPECT, SMOOTH_TRANSFORM
        ))

    def _log_incident_if_new(self, alert_info):
        now_str = time.strftime("%H:%M:%S")
        row_count = self.live_table.rowCount()
        if row_count > 0:
            last_type = self.live_table.item(0, 2).text()
            if last_type == alert_info["type"]:
                return

        # Objective 6: Persist in SQLite & Save Evidence Image
        lane_str = "LANE_1" if self.source_combo.currentIndex() == 0 else "MAIN_LANE"
        self.incident_db.log_hazard(
            alert_info, frame=self.latest_frame, node_id="POLE_04", lane=lane_str
        )

        self.live_table.insertRow(0)
        self.live_table.setItem(0, 0, QTableWidgetItem(now_str))
        self.live_table.setItem(0, 1, QTableWidgetItem(alert_info["status"]))
        self.live_table.setItem(0, 2, QTableWidgetItem(alert_info["type"]))
        self.live_table.setItem(0, 3, QTableWidgetItem(alert_info["dist"]))
        if row_count > 50:
            self.live_table.removeRow(50)

    def capture_manual_snapshot(self):
        if self.latest_frame is not None:
            snap_path = config.SAMPLE_DATA_DIR / "snapshots" / f"manual_{int(time.time())}.jpg"
            cv2.imwrite(str(snap_path), self.latest_frame)
            QMessageBox.information(self, "Snapshot Saved", f"Hazard frame saved to:\n{snap_path}")

    def start_roi_edit(self):
        self.video_canvas.roi_points = []
        self.video_canvas.roi_editing = True
        QMessageBox.information(
            self, "Lane ROI Calibration",
            "Click 4 points on the video in order:\n1. Bottom-Left\n2. Top-Left\n3. Top-Right\n4. Bottom-Right"
        )

    def on_roi_customized(self, norm_points):
        if self.latest_frame is not None:
            h, w = self.latest_frame.shape[:2]
            abs_points = [(int(nx * w), int(ny * h)) for nx, ny in norm_points]
            self.detector.set_roi(abs_points)
            QMessageBox.information(self, "ROI Updated", "Custom Lane Danger Corridor applied successfully!")

    def reset_roi_default(self):
        if self.source_combo.currentIndex() == 0:
            self._apply_normalized_roi(config.POLE_ROI_NORMALIZED)
        else:
            self._apply_normalized_roi(config.DEFAULT_ROI_NORMALIZED)
        QMessageBox.information(self, "ROI Reset", "Restored default road corridor.")

    def closeEvent(self, event):
        self.stop_playback()
        if self.video_cap:
            self.video_cap.release()
        self.broadcaster.close()
        self.virtual_esp32.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    if "--live" in sys.argv:
        window.source_combo.setCurrentIndex(4)
        window.start_playback()
    elif "--esp32" in sys.argv:
        window.source_combo.setCurrentIndex(3)
        window.start_playback()
    window.show()
    sys.exit(app.exec())

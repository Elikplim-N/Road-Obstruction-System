"""
Virtual ESP32 Dashboard Receiver Simulator
Emulates the physical ESP32 Receiver hardware (16x2 LCD, LEDs, and Buzzer)
inside a PyQt widget. Also listens to real UDP packets on port 8888!
"""

import socket
import json
import threading
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
except ImportError:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QTimer
    from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen
    ALIGN_CENTER = Qt.AlignCenter

class VirtualESP32Receiver(QGroupBox):
    packet_received = pyqtSignal(dict)

    def __init__(self, listen_udp=True, udp_port=8888, parent=None):
        super().__init__("ESP32 Receiver Dashboard Node (Virtual Hardware)", parent)
        self.udp_port = udp_port
        self.listen_udp = listen_udp
        self.running = False
        self.sock = None

        self.status = "STANDBY"
        self.obj_type = "NONE"
        self.dist = "---"
        self.duration = 0.0
        self.sound = 0

        self.init_ui()

        if self.listen_udp:
            self.packet_received.connect(self.apply_packet)
            self.start_listener()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # LCD Frame (styled to look like a retro 16x2 green backlit LCD)
        self.lcd_box = QFrame()
        self.lcd_box.setStyleSheet("""
            QFrame {
                background-color: #0b260b;
                border: 3px solid #1f4f1f;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        lcd_layout = QVBoxLayout(self.lcd_box)
        lcd_layout.setSpacing(4)

        lcd_font = QFont("Monospace", 13, QFont.Weight.Bold)
        lcd_font.setStyleHint(QFont.StyleHint.TypeWriter)

        self.lcd_line1 = QLabel("ROAD STATUS: OK")
        self.lcd_line1.setFont(lcd_font)
        self.lcd_line1.setStyleSheet("color: #39ff14; background: transparent;")
        self.lcd_line1.setAlignment(ALIGN_CENTER)

        self.lcd_line2 = QLabel("LANE: CLEAR")
        self.lcd_line2.setFont(lcd_font)
        self.lcd_line2.setStyleSheet("color: #39ff14; background: transparent;")
        self.lcd_line2.setAlignment(ALIGN_CENTER)

        lcd_layout.addWidget(self.lcd_line1)
        lcd_layout.addWidget(self.lcd_line2)
        layout.addWidget(self.lcd_box)

        # Hardware indicator bar: LEDs + Buzzer indicator
        hw_bar = QHBoxLayout()

        # Green LED indicator
        self.green_led = QLabel("● CLEAR LED")
        self.green_led.setFont(QFont("Sans-Serif", 9, QFont.Weight.Bold))
        self.green_led.setStyleSheet("color: #00ff00; padding: 4px;")
        hw_bar.addWidget(self.green_led)

        # Red LED indicator
        self.red_led = QLabel("● DANGER LED")
        self.red_led.setFont(QFont("Sans-Serif", 9, QFont.Weight.Bold))
        self.red_led.setStyleSheet("color: #440000; padding: 4px;")
        hw_bar.addWidget(self.red_led)

        # Buzzer status
        self.buzzer_lbl = QLabel("🔊 BUZZER: MUTE")
        self.buzzer_lbl.setFont(QFont("Sans-Serif", 9, QFont.Weight.Bold))
        self.buzzer_lbl.setStyleSheet("color: #aaaaaa; padding: 4px;")
        hw_bar.addWidget(self.buzzer_lbl)

        layout.addLayout(hw_bar)

    def apply_packet(self, data):
        self.status = data.get("status", "CLEAR")
        self.obj_type = data.get("type", "NONE")
        self.dist = data.get("dist", "SAFE")
        self.duration = data.get("duration", 0.0)
        self.sound = data.get("sound", 0)

        # Update LCD
        if self.status == "DANGER":
            self.lcd_line1.setText("! ROAD OBSTRUCT !")
            self.lcd_line1.setStyleSheet("color: #ff3333; background: transparent;")
            self.lcd_line2.setText(f"{self.obj_type[:10]} {self.dist[:4]}")
            self.lcd_line2.setStyleSheet("color: #ff3333; background: transparent;")

            self.red_led.setStyleSheet("color: #ff0000; font-weight: bold; text-shadow: 0 0 8px red;")
            self.green_led.setStyleSheet("color: #004400;")
            self.buzzer_lbl.setText("🔊 BUZZER: [ALARM]")
            self.buzzer_lbl.setStyleSheet("color: #ff3333; font-weight: bold;")
        elif self.status == "CAUTION":
            self.lcd_line1.setText("CAUTION: ROAD")
            self.lcd_line1.setStyleSheet("color: #ffaa00; background: transparent;")
            self.lcd_line2.setText(f"{self.obj_type[:10]} {self.dist[:4]}")
            self.lcd_line2.setStyleSheet("color: #ffaa00; background: transparent;")

            self.red_led.setStyleSheet("color: #ffaa00;")
            self.green_led.setStyleSheet("color: #00ff00;")
            self.buzzer_lbl.setText("🔊 BUZZER: [PULSE]")
            self.buzzer_lbl.setStyleSheet("color: #ffaa00;")
        else:
            self.lcd_line1.setText("ROAD STATUS: OK")
            self.lcd_line1.setStyleSheet("color: #39ff14; background: transparent;")
            self.lcd_line2.setText("LANE: CLEAR")
            self.lcd_line2.setStyleSheet("color: #39ff14; background: transparent;")

            self.red_led.setStyleSheet("color: #440000;")
            self.green_led.setStyleSheet("color: #00ff00; font-weight: bold;")
            self.buzzer_lbl.setText("🔊 BUZZER: MUTE")
            self.buzzer_lbl.setStyleSheet("color: #666666;")

    def start_listener(self):
        self.running = True
        self.thread = threading.Thread(target=self._udp_listen_loop, daemon=True)
        self.thread.start()

    def _udp_listen_loop(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self.udp_port))
            sock.settimeout(1.0)
            self.sock = sock

            while self.running:
                try:
                    data, _ = sock.recvfrom(512)
                    packet = json.loads(data.decode('utf-8'))
                    self.packet_received.emit(packet)
                except socket.timeout:
                    continue
                except Exception:
                    pass
        except Exception as e:
            print(f"[Virtual ESP32] UDP port {self.udp_port} bind note: {e}")

    def close(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

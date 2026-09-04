"""
Network Hub for Road Obstruction Detection System
Handles UDP broadcasting to ESP32 Receiver(s) over the shared hotspot
and manages MJPEG video streaming from ESP32-CAM.
"""

import socket
import json
import time
import threading
import cv2
import requests
import numpy as np

class ESP32Broadcaster:
    """
    Sends JSON alert packets to the ESP32 receiver unit over the shared Wi-Fi hotspot.
    Uses UDP broadcast (255.255.255.255) for instantaneous zero-config discovery.
    """
    def __init__(self, broadcast_ip="255.255.255.255", port=8888):
        self.broadcast_ip = broadcast_ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.last_send_time = 0
        self.min_interval = 0.1  # Max 10 packets/second
        self.last_payload = None

    def send_alert(self, status="CLEAR", obj_type="NONE", dist="SAFE", duration=0.0, sound=0):
        now = time.time()
        payload = {
            "status": status,
            "type": obj_type,
            "dist": dist,
            "duration": round(float(duration), 1),
            "sound": int(sound)
        }

        if now - self.last_send_time < self.min_interval and payload == self.last_payload:
            return

        self.last_send_time = now
        self.last_payload = payload

        try:
            msg = json.dumps(payload).encode('utf-8')
            self.sock.sendto(msg, (self.broadcast_ip, self.port))
        except Exception:
            pass

    def close(self):
        try:
            self.sock.close()
        except:
            pass


class LoRaTransmitter:
    """
    Sends alert packets over LoRa via a USB-to-UART module (e.g., Reyax RYLR896 or SX1278).
    Uses standard AT command protocol: AT+SEND=<Address>,<PayloadLength>,<Data>\r\n
    """
    def __init__(self, port=None, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connected = False
        self.packets_sent = 0

    def connect(self, port, baudrate=115200):
        try:
            import serial
            self.port = port
            self.baudrate = baudrate
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.5)
            self.connected = True
            print(f"[LoRa] Connected to {self.port} at {self.baudrate} baud.")
            return True, f"Connected to {port}"
        except Exception as e:
            self.connected = False
            return False, str(e)

    def disconnect(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        self.connected = False

    def send_alert(self, payload_dict, target_addr=1):
        if not self.connected or not self.ser or not self.ser.is_open:
            return False

        try:
            # Compact JSON
            json_str = json.dumps(payload_dict, separators=(',', ':'))
            cmd = f"AT+SEND={target_addr},{len(json_str)},{json_str}\r\n"
            self.ser.write(cmd.encode('utf-8'))
            self.ser.flush()
            self.packets_sent += 1
            return True
        except Exception as e:
            print(f"[LoRa Send Error] {e}")
            return False


class DualBroadcaster:
    """
    Dispatches road obstruction alerts concurrently over:
    1. Wi-Fi Hotspot UDP (Local subnet broadcast)
    2. LoRa Radio (Long-range upstream link via USB serial)
    """
    def __init__(self, wifi_broadcast_ip="255.255.255.255", wifi_port=8888):
        self.wifi = ESP32Broadcaster(broadcast_ip=wifi_broadcast_ip, port=wifi_port)
        self.lora = LoRaTransmitter()
        self.wifi_enabled = True
        self.lora_enabled = True

    def send_alert(self, status="CLEAR", obj_type="NONE", dist="SAFE", duration=0.0, sound=0):
        payload = {
            "status": status,
            "type": obj_type,
            "dist": dist,
            "duration": round(float(duration), 1),
            "sound": int(sound)
        }

        # 1. Transmit via Wi-Fi Hotspot UDP
        if self.wifi_enabled:
            self.wifi.send_alert(status, obj_type, dist, duration, sound)

        # 2. Transmit via LoRa Radio
        if self.lora_enabled and self.lora.connected:
            self.lora.send_alert(payload)

    def close(self):
        self.wifi.close()
        self.lora.disconnect()


class ESP32CamStreamer:
    """
    Connects to the ESP32-CAM HTTP MJPEG stream.
    Reads continuous JPEG frames over Wi-Fi.
    """
    def __init__(self, url="http://192.168.43.50:81/stream"):
        self.url = url
        self.running = False
        self.latest_frame = None
        self.lock = threading.Lock()
        self.thread = None
        self.connected = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.connected = False

    def get_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None

    def _stream_loop(self):
        while self.running:
            try:
                # Open HTTP stream
                stream = requests.get(self.url, stream=True, timeout=5)
                if stream.status_code != 200:
                    time.sleep(2)
                    continue

                self.connected = True
                bytes_data = bytes()

                for chunk in stream.iter_content(chunk_size=1024):
                    if not self.running:
                        break
                    bytes_data += chunk
                    a = bytes_data.find(b'\xff\xd8') # JPEG start
                    b = bytes_data.find(b'\xff\xd9') # JPEG end
                    if a != -1 and b != -1:
                        jpg = bytes_data[a:b+2]
                        bytes_data = bytes_data[b+2:]
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.lock:
                                self.latest_frame = frame

            except Exception:
                self.connected = False
                time.sleep(1.5)

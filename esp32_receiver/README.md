# ESP32 Highway Road Obstruction Dashboard Receiver

Production-grade in-cabin driver warning node that receives real-time highway obstruction alerts from the Street Pole ESP32-CAM optical detection station.

---

## 🚀 Key Features

1. **Dual Concurrent Reception**:
   - **Wi-Fi UDP Broadcast** on port `8888` (<2ms response time over hotspot).
   - **Long-Range LoRa Transceiver** on HardwareSerial(2) (1–3 km range upstream).
2. **Non-Blocking Audio Engine**:
   - Zero-delay PWM siren sequences. Packet reception is never frozen while beeping.
   - **Code 2 (DANGER)**: Rapid dual-tone siren (2400 Hz ⇄ 1800 Hz).
   - **Code 1 (CAUTION)**: Pulsed 1500 Hz caution beeps.
   - **Code 0 (CLEAR)**: Silent, steady green status LED.
3. **Auto-Detecting I2C Display**:
   - Automatically probes I2C addresses `0x27` (PCF8574T) and `0x3F` (PCF8574AT). No code changes needed for different LCD backpacks.
4. **Embedded In-Cabin Driver HUD**:
   - Hosts a mobile-first Web HUD dashboard on port `80` (accessible at `http://192.168.4.1`).
   - Supports mute toggle and audio test button from the driver's phone.
5. **Brownout & Voltage Spike Tolerance**:
   - Brownout detector disabled to ensure stable operation when powered via vehicle 12V-to-5V cigarette lighter USB adapters.
6. **Failsafe Auto-Clear**:
   - Automatically returns to `CLEAR / MONITORING` if no hazard packets arrive for 5 seconds.

---

## 🔌 Hardware Wiring Diagram

| Peripheral | ESP32 Pin | Peripheral Pin | Notes |
|---|---|---|---|
| **16x2 I2C LCD** | `GPIO 21` | SDA | Standard I2C Data |
| | `GPIO 22` | SCL | Standard I2C Clock |
| | `5V` (or VIN) | VCC | LCD backlight requires 5V |
| | `GND` | GND | Common ground |
| **Piezo Buzzer** | `GPIO 25` | Positive (+) | Passive/active piezo PWM |
| | `GND` | Negative (-) | Ground |
| **Red LED (Danger)** | `GPIO 26` | Anode (+) | Through 220Ω resistor |
| | `GND` | Cathode (-) | Ground |
| **Green LED (Safe)** | `GPIO 27` | Anode (+) | Through 220Ω resistor |
| | `GND` | Cathode (-) | Ground |
| **LoRa Module (RYLR896)** | `GPIO 16` (RX2) | TXD | Transceiver TX into ESP32 RX |
| | `GPIO 17` (TX2) | RXD | Transceiver RX into ESP32 TX |
| | `3V3` | VDD | 3.3V Logic & Power |
| | `GND` | GND | Common ground |

---

## 📦 Required Arduino Libraries

Install these via the Arduino IDE Library Manager:
1. **ArduinoJson** (by Benoit Blanchon, v6.x or v7.x)
2. **LiquidCrystal_I2C** (by Frank de Brabander or Marco Schwartz)
3. *(Optional for OLED)* **Adafruit SSD1306** & **Adafruit GFX Library**

---

## 📱 Using the In-Cabin Mobile HUD

1. Turn on the receiver unit inside the vehicle.
2. Connect your smartphone to the Wi-Fi network:
   - **SSID**: `Road_Alert_Receiver`
   - **Password**: `RoadSafe123`
3. Open your browser and navigate to: `http://192.168.4.1`
4. The dashboard displays live hazard cards, corridor lane status, signal channels, and mute controls.

---

## ⚡ Testing the Alert System

You can test the receiver in two ways:
1. **From the Web HUD**: Tap the `⚡ Sound Test` button at `http://192.168.4.1`.
2. **From the IoT Fleet Dashboard**: Click `⚡ Test Alarm` under **ESP32 In-Cabin Receiver Node #01** in the web dashboard.
3. **Using Python CLI**:
   ```bash
   python3 -c "import socket, json; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); s.sendto(json.dumps({'status':'DANGER','type':'STALLED CAR','dist':'50m','duration':4.5,'sound':2}).encode(), ('255.255.255.255', 8888))"
   ```

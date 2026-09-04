# Hardware Wiring & Pinout Guide

## 1. ESP32 Receiver Unit (LCD + Buzzer + Status LEDs)

The ESP32 Receiver acts as the dashboard in-cabin warning receiver. It receives UDP alert packets from the Desktop over the shared hotspot and triggers visual/audio alarms.

### Components
1. ESP32 Development Board (e.g. NodeMCU ESP32-WROOM-32)
2. 16x2 I2C Character LCD (PCF8574 I2C adapter) OR 0.96" SSD1306 OLED (I2C)
3. 5V Active Piezo Buzzer
4. 2x LEDs (Green = Road Clear, Red = Obstruction Danger) + 2x 220Ω resistors
5. Breadboard and jumper wires

### Pin Connections (Standard ESP32 NodeMCU)

| Component Pin | ESP32 Pin | Note |
| :--- | :--- | :--- |
| **I2C LCD / OLED VCC** | `VIN` (5V) or `3V3` | 5V for 16x2 LCD backlight; 3.3V for SSD1306 OLED |
| **I2C LCD / OLED GND** | `GND` | Common Ground |
| **I2C LCD / OLED SDA** | `GPIO 21` | Standard ESP32 I2C Data |
| **I2C LCD / OLED SCL** | `GPIO 22` | Standard ESP32 I2C Clock |
| **Active Buzzer (+)**  | `GPIO 25` | PWM or digital output for tone generation |
| **Active Buzzer (-)**  | `GND` | Common Ground |
| **Red LED (+)**       | `GPIO 26` | Via 220Ω resistor (Danger Alert) |
| **Green LED (+)**     | `GPIO 27` | Via 220Ω resistor (System Clear) |
| **LEDs (-)**          | `GND` | Common Ground |

---

## 2. ESP32-CAM (AI-Thinker Model)

The ESP32-CAM streams real-time video to the desktop over Wi-Fi.

### Pin Connections (Flashing via FTDI USB-to-UART Adapter)

> [!IMPORTANT]
> The ESP32-CAM does NOT have an onboard USB port. Use an FTDI USB-to-TTL adapter or ESP32-CAM-MB motherboard to flash.

| FTDI Programmer Pin | ESP32-CAM Pin | Note |
| :--- | :--- | :--- |
| **VCC (5V)** | `5V` (or `3V3`) | Provide strong 5V at least 1A power supply |
| **GND** | `GND` | Common Ground |
| **TX** | `U0R` (GPIO 3) | FTDI TX -> ESP32 RX |
| **RX** | `U0T` (GPIO 1) | FTDI RX -> ESP32 TX |
| **GND to GPIO 0** | Jumper wire | Connect `GPIO 0` to `GND` during flashing, disconnect for normal boot |

---

## 3. Future LoRa Module Addition (Optional Migration)

When adding a LoRa module (e.g., Reyax RYLR896 or SX1278) to the ESP32 Receiver:

| LoRa Module (UART RYLR896) | ESP32 Receiver Pin | Note |
| :--- | :--- | :--- |
| **VDD (3.3V)** | `3V3` | Power |
| **GND** | `GND` | Ground |
| **TXD** | `GPIO 16` (RX2) | HardwareSerial(2) |
| **RXD** | `GPIO 17` (TX2) | HardwareSerial(2) |

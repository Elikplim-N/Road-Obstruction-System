/*
 * ESP32 Highway Road Obstruction Dashboard Receiver
 * 
 * Dual Communication Architecture:
 *   1. Wi-Fi Hotspot (UDP port 8888) - Local high-speed prototyping
 *   2. LoRa Transceiver (HardwareSerial 2 on GPIO 16/17) - 1-3km upstream warning link
 *
 * Hardware:
 *   - ESP32 Development Board (e.g. NodeMCU ESP32-WROOM)
 *   - 16x2 I2C LCD (or 0.96" SSD1306 OLED)
 *   - Piezo Buzzer on GPIO 25
 *   - Red LED (Danger) on GPIO 26
 *   - Green LED (Clear) on GPIO 27
 *   - LoRa Module: Reyax RYLR896 or Ra-02 (SX1278) on RX2 (GPIO 16) / TX2 (GPIO 17)
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <ArduinoJson.h>

// ==========================================
// DISPLAY SELECTION (16x2 LCD or OLED)
// ==========================================
#define USE_LCD1602 true
#define USE_OLED    false

#if USE_LCD1602
  #include <LiquidCrystal_I2C.h>
  LiquidCrystal_I2C lcd(0x27, 16, 2); // Default address 0x27 or 0x3F
#endif

#if USE_OLED
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  #define SCREEN_WIDTH 128
  #define SCREEN_HEIGHT 64
  Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
#endif

// ==========================================
// DUAL COMMUNICATION CONFIGURATION
// ==========================================
// 1. Wi-Fi Hotspot
const char* ssid     = "RoadAlertHotspot";
const char* password = "RoadAlertPassword123";
const unsigned int udpPort = 8888;
WiFiUDP udp;

// 2. LoRa Radio (HardwareSerial 2)
#define LORA_RX_PIN 16
#define LORA_TX_PIN 17
HardwareSerial LoRaSerial(2);

// Hardware Pins
const int BUZZER_PIN    = 25;
const int RED_LED_PIN   = 26;
const int GREEN_LED_PIN = 27;

char incomingPacket[256];
unsigned long lastPacketTime = 0;
const unsigned long TIMEOUT_MS = 5000;

// State tracking
String currentStatus = "CLEAR";
String currentType   = "NONE";
String currentDist   = "SAFE";
float currentDuration = 0.0;
int currentSound = 0;
String commChannel = "NONE";

void updateDisplay(String status, String type, String dist, String channel) {
#if USE_LCD1602
  lcd.clear();
  lcd.setCursor(0, 0);
  if (status == "DANGER") {
    lcd.print("!ROAD OBSTRUCT!");
  } else if (status == "CAUTION") {
    lcd.print("CAUTION: ROAD");
  } else {
    lcd.print("ROAD STATUS: OK");
  }

  lcd.setCursor(0, 1);
  if (status == "CLEAR") {
    lcd.print("LANE: OK [" + channel + "]");
  } else {
    String line2 = type.substring(0, 8) + " " + dist.substring(0, 3) + " " + channel.substring(0, 2);
    lcd.print(line2);
  }
#endif

#if USE_OLED
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);
  oled.printf("ROAD ALERT [%s]", channel.c_str());
  oled.drawLine(0, 10, 128, 10, SSD1306_WHITE);

  oled.setCursor(0, 16);
  oled.setTextSize(2);
  if (status == "DANGER") {
    oled.println("! DANGER !");
  } else if (status == "CAUTION") {
    oled.println(" CAUTION ");
  } else {
    oled.println(" ROAD OK ");
  }

  oled.setTextSize(1);
  oled.setCursor(0, 42);
  oled.printf("Type: %s\n", type.c_str());
  oled.printf("Dist: %s", dist.c_str());
  oled.display();
#endif
}

void triggerAudioAlarm(int soundLevel) {
  if (soundLevel == 2) {
    // Urgent danger siren: alternating high frequencies
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, LOW);
    for (int i = 0; i < 3; i++) {
      tone(BUZZER_PIN, 2400, 70);
      delay(80);
      tone(BUZZER_PIN, 1800, 70);
      delay(80);
    }
  } else if (soundLevel == 1) {
    // Caution: intermittent single beep
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, HIGH);
    tone(BUZZER_PIN, 1500, 100);
    delay(120);
  } else {
    // Normal / Clear
    noTone(BUZZER_PIN);
    digitalWrite(RED_LED_PIN, LOW);
    digitalWrite(GREEN_LED_PIN, HIGH);
  }
}

void processJsonAlert(String jsonPayload, String sourceChannel) {
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, jsonPayload);

  if (!error) {
    lastPacketTime = millis();
    commChannel = sourceChannel;
    currentStatus   = doc["status"].as<String>();
    currentType     = doc["type"].as<String>();
    currentDist     = doc["dist"].as<String>();
    currentDuration = doc["duration"].as<float>();
    currentSound    = doc["sound"].as<int>();

    Serial.printf("[%s ALERT] Status: %s | Type: %s | Dist: %s | Sound: %d\n",
                  sourceChannel.c_str(), currentStatus.c_str(), currentType.c_str(), currentDist.c_str(), currentSound);

    updateDisplay(currentStatus, currentType, currentDist, sourceChannel);
    triggerAudioAlarm(currentSound);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);

  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(GREEN_LED_PIN, HIGH);

  // Initialize display
#if USE_LCD1602
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Road Obstruction");
  lcd.setCursor(0, 1);
  lcd.print("Dual WiFi+LoRa");
#endif

#if USE_OLED
  if(oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oled.clearDisplay();
    oled.setTextSize(1);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(0, 20);
    oled.println("Dual WiFi+LoRa Node");
    oled.display();
  }
#endif

  // 1. Initialize LoRa Serial Interface (UART2)
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  delay(100);
  // Configure LoRa RYLR896 default address and band
  LoRaSerial.println("AT+ADDRESS=1");
  LoRaSerial.println("AT+NETWORKID=6");
  Serial.println("[LoRa] UART Interface initialized on GPIO 16 (RX) / 17 (TX)");

  // 2. Connect to Hotspot Wi-Fi
  WiFi.begin(ssid, password);
  Serial.printf("Connecting to Hotspot %s...", ssid);
  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 20) {
    delay(400);
    Serial.print(".");
    wifiAttempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
    udp.begin(udpPort);
    Serial.printf("Listening on UDP port %u\n", udpPort);
  } else {
    Serial.println("\nWiFi not reachable; running in standalone LoRa mode!");
  }

  // Confirmation startup beep
  tone(BUZZER_PIN, 2000, 150);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, HIGH);

  updateDisplay("CLEAR", "NONE", "READY", "OK");
  lastPacketTime = millis();
}

void loop() {
  // --- Check 1: Wi-Fi UDP Alert Packets ---
  if (WiFi.status() == WL_CONNECTED) {
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
      int len = udp.read(incomingPacket, sizeof(incomingPacket) - 1);
      if (len > 0) {
        incomingPacket[len] = '\0';
        processJsonAlert(String(incomingPacket), "WIFI");
      }
    }
  }

  // --- Check 2: LoRa Radio Alert Packets (UART) ---
  if (LoRaSerial.available()) {
    String incoming = LoRaSerial.readStringUntil('\n');
    incoming.trim();

    // Reyax RYLR896 format: +RCV=address,length,data,rssi,snr
    if (incoming.startsWith("+RCV=")) {
      int firstComma = incoming.indexOf(',');
      int secondComma = incoming.indexOf(',', firstComma + 1);
      int thirdComma = incoming.indexOf(',', secondComma + 1);
      String jsonPayload = incoming.substring(secondComma + 1, thirdComma);
      processJsonAlert(jsonPayload, "LORA");
    } else if (incoming.startsWith("{")) {
      // Direct raw JSON over LoRa UART
      processJsonAlert(incoming, "LORA");
    }
  }

  // Watchdog: If no packet received within 6 seconds
  if (millis() - lastPacketTime > TIMEOUT_MS) {
    updateDisplay("STANDBY", "MONITORING", "---", "--");
    digitalWrite(GREEN_LED_PIN, HIGH);
    digitalWrite(RED_LED_PIN, LOW);
    noTone(BUZZER_PIN);
  }

  delay(40);
}

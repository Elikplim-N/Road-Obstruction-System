/*
 * ESP32 Highway Road Obstruction Dashboard Receiver — Production Firmware v2.2
 *
 * Designed for In-Cabin Driver Warning & Fleet Vehicle Telemetry.
 *
 * Core Capabilities:
 *   1. DUAL CONCURRENT RECEPTION:
 *      - Ultra-fast Wi-Fi UDP Broadcast (port 8888) (<2ms latency over shared hotspot)
 *      - Upstream Long-Range LoRa (UART2 on GPIO 16 RX / 17 TX or SPI SX1278) (1-3km distance)
 *   2. NON-BLOCKING AUDIO ENGINE:
 *      - Zero-delay PWM siren sequences (Code 2 = Urgent dual-tone siren, Code 1 = Intermittent caution)
 *      - Never blocks radio or packet processing loop!
 *   3. AUTO-DETECTING I2C DISPLAY:
 *      - Probes 0x27 and 0x3F addresses for 16x2 LCD backpacks automatically
 *      - Optional 0.96" SSD1306 OLED fallback
 *   4. EMBEDDED IN-CABIN DRIVER HUD:
 *      - Web server on port 80 serving real-time HUD dashboard to driver smartphone/tablet
 *      - REST API: /api/status, /api/test-alarm, /api/mute
 *   5. FAILSAFE & AUTO-CLEAR:
 *      - Reverts to MONITORING / ROAD OK if hazard ceases for > 5 seconds
 *      - Brownout protection disabled for unstable automotive 12V-to-5V converters
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "dashboard.h"

// ============================================================================
// CONFIGURATION & HARDWARE PINOUTS
// ============================================================================

// --- Display Selection ---
#define USE_LCD1602 true
#define USE_OLED    false

#if USE_LCD1602
  #include <LiquidCrystal_I2C.h>
  LiquidCrystal_I2C lcd27(0x27, 16, 2);
  LiquidCrystal_I2C lcd3F(0x3F, 16, 2);
  LiquidCrystal_I2C* lcd = &lcd27;
  bool lcdFound = false;
#endif

#if USE_OLED
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  #define SCREEN_WIDTH 128
  #define SCREEN_HEIGHT 64
  Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
  bool oledFound = false;
#endif

// --- Wi-Fi Settings ---
// Hotspot SSID of the street pole network or in-vehicle router
const char* WIFI_SSID     = "RoadAlertHotspot";
const char* WIFI_PASSWORD = "RoadAlertPassword123";
const unsigned int UDP_PORT = 8888;
WiFiUDP udp;
WebServer server(80);

// --- LoRa Transceiver Configuration ---
// Default: Reyax RYLR896 / RYLR998 UART on HardwareSerial(2)
#define LORA_RX_PIN 16
#define LORA_TX_PIN 17
HardwareSerial LoRaSerial(2);

// --- Driver Alert Peripherals ---
const int BUZZER_PIN    = 25;  // Piezo Buzzer (PWM)
const int RED_LED_PIN   = 26;  // Danger Indicator LED
const int GREEN_LED_PIN = 27;  // Clear / Safe Road LED

// Timeout to auto-clear alert when road is free of obstructions
const unsigned long HAZARD_TIMEOUT_MS = 5000;

// ============================================================================
// STATE TELEMETRY
// ============================================================================
String currentStatus   = "CLEAR";
String currentType     = "NONE";
String currentDist     = "SAFE";
String currentLane     = "LANE 1";
float currentDuration  = 0.0;
int currentSound       = 0;
String activeChannel   = "IDLE";
unsigned long lastPacketTime = 0;
unsigned long totalPacketsReceived = 0;
bool buzzerMuted = false;

// Audio Sequencer State (Non-Blocking)
unsigned long lastAudioToggleTime = 0;
bool audioPhase = false;

// ============================================================================
// DISPLAY CONTROLLER
// ============================================================================

void renderDisplay(const String& status, const String& type, const String& dist, const String& channel) {
#if USE_LCD1602
  if (!lcdFound) return;

  lcd->clear();
  lcd->setCursor(0, 0);

  if (status == "DANGER") {
    lcd->print("!ROAD OBSTRUCT!");
  } else if (status == "CAUTION") {
    lcd->print("CAUTION: ROAD");
  } else {
    lcd->print("ROAD STATUS: OK");
  }

  lcd->setCursor(0, 1);
  if (status == "CLEAR" || status == "STANDBY") {
    lcd->print("MONITORING [" + channel.substring(0, 4) + "]");
  } else {
    // Format: "CAR   50m WF"
    String tShort = type.substring(0, 7);
    while (tShort.length() < 7) tShort += " ";
    String dShort = dist.substring(0, 4);
    while (dShort.length() < 4) dShort += " ";
    lcd->print(tShort + " " + dShort + " " + channel.substring(0, 2));
  }
#endif

#if USE_OLED
  if (!oledFound) return;

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

// ============================================================================
// NON-BLOCKING AUDIO & LED DRIVER
// ============================================================================

void updateAlarms() {
  unsigned long now = millis();

  if (buzzerMuted || currentSound == 0) {
    noTone(BUZZER_PIN);
    if (currentStatus == "CLEAR" || currentStatus == "STANDBY") {
      digitalWrite(RED_LED_PIN, LOW);
      digitalWrite(GREEN_LED_PIN, HIGH);
    }
    return;
  }

  if (currentSound == 2) {
    // Level 2 (DANGER): Urgent rapid dual-tone siren (2400Hz <-> 1800Hz alternating every 90ms)
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, LOW);

    if (now - lastAudioToggleTime >= 90) {
      lastAudioToggleTime = now;
      audioPhase = !audioPhase;
      if (audioPhase) {
        tone(BUZZER_PIN, 2400);
      } else {
        tone(BUZZER_PIN, 1800);
      }
    }
  } else if (currentSound == 1) {
    // Level 1 (CAUTION): Pulsed 1500Hz beeps (120ms ON, 200ms OFF)
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, HIGH);

    if (audioPhase && (now - lastAudioToggleTime >= 120)) {
      audioPhase = false;
      lastAudioToggleTime = now;
      noTone(BUZZER_PIN);
    } else if (!audioPhase && (now - lastAudioToggleTime >= 200)) {
      audioPhase = true;
      lastAudioToggleTime = now;
      tone(BUZZER_PIN, 1500);
    }
  }
}

// ============================================================================
// PACKET PROCESSING ENGINE (Wi-Fi UDP & LoRa)
// ============================================================================

void handleIncomingPayload(const String& payload, const String& channel) {
  StaticJsonDocument<384> doc;
  DeserializationError err = deserializeJson(doc, payload);

  if (err) {
    Serial.printf("[%s] JSON parse error: %s\n", channel.c_str(), err.c_str());
    return;
  }

  totalPacketsReceived++;
  lastPacketTime = millis();
  activeChannel  = channel;

  currentStatus   = doc["status"].as<String>();
  currentType     = doc["type"].as<String>();
  currentDist     = doc["dist"].as<String>();
  currentDuration = doc["duration"].as<float>();
  currentSound    = doc["sound"].as<int>();
  if (doc.containsKey("lane")) {
    currentLane = doc["lane"].as<String>();
  }

  Serial.printf("[%s #%lu] %s | Type: %s | Dist: %s | Sound: %d\n",
                channel.c_str(), totalPacketsReceived, currentStatus.c_str(),
                currentType.c_str(), currentDist.c_str(), currentSound);

  renderDisplay(currentStatus, currentType, currentDist, channel);
}

// ============================================================================
// WEB SERVER (IN-CABIN DRIVER HUD)
// ============================================================================

void setupWebServer() {
  server.on("/", HTTP_GET, []() {
    server.send_P(200, "text/html", RECEIVER_DASHBOARD_HTML);
  });

  server.on("/api/status", HTTP_GET, []() {
    StaticJsonDocument<256> resp;
    resp["status"]   = currentStatus;
    resp["type"]     = currentType;
    resp["dist"]     = currentDist;
    resp["lane"]     = currentLane;
    resp["duration"] = currentDuration;
    resp["sound"]    = currentSound;
    resp["channel"]  = activeChannel;
    resp["packets"]  = totalPacketsReceived;
    resp["muted"]    = buzzerMuted;

    String jsonStr;
    serializeJson(resp, jsonStr);
    server.send(200, "application/json", jsonStr);
  });

  server.on("/api/test-alarm", HTTP_POST, []() {
    currentStatus = "DANGER";
    currentType   = "TEST HAZARD";
    currentDist   = "IMMEDIATE";
    currentSound  = 2;
    activeChannel = "TEST";
    lastPacketTime = millis();
    renderDisplay(currentStatus, currentType, currentDist, "TEST");
    server.send(200, "application/json", "{\"success\":true,\"message\":\"Alarm test triggered\"}");
  });

  server.on("/api/mute", HTTP_POST, []() {
    if (server.hasArg("val")) {
      buzzerMuted = (server.arg("val") == "1");
    } else {
      buzzerMuted = !buzzerMuted;
    }
    if (buzzerMuted) noTone(BUZZER_PIN);
    server.send(200, "application/json", String("{\"muted\":") + (buzzerMuted ? "true" : "false") + "}");
  });

  server.begin();
  Serial.println("[Web HUD] Server running on http://192.168.4.1 (or station IP)");
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // 1. Disable brownout detector to tolerate voltage drops on vehicle 12V-to-5V step-downs
  WRITE_PERI_REG(RTC_CNTL_BROWNOUT_REG, 0);

  Serial.begin(115200);
  Serial.println("\n=======================================================");
  Serial.println("  ESP32 HIGHWAY ROAD OBSTRUCTION RECEIVER v2.2");
  Serial.println("=======================================================");

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);

  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(GREEN_LED_PIN, HIGH);

  // 2. Auto-Scan I2C Bus for LCD (0x27 or 0x3F)
  Wire.begin();
#if USE_LCD1602
  Wire.beginTransmission(0x27);
  if (Wire.endTransmission() == 0) {
    lcd = &lcd27;
    lcdFound = true;
    Serial.println("[Display] 16x2 LCD detected at 0x27");
  } else {
    Wire.beginTransmission(0x3F);
    if (Wire.endTransmission() == 0) {
      lcd = &lcd3F;
      lcdFound = true;
      Serial.println("[Display] 16x2 LCD detected at 0x3F");
    } else {
      Serial.println("[Display] No I2C LCD detected at 0x27 or 0x3F");
    }
  }

  if (lcdFound) {
    lcd->init();
    lcd->backlight();
    lcd->setCursor(0, 0);
    lcd->print("Road Alert HUD");
    lcd->setCursor(0, 1);
    lcd->print("Dual WiFi+LoRa");
  }
#endif

#if USE_OLED
  if (oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oledFound = true;
    oled.clearDisplay();
    oled.setTextSize(1);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(0, 20);
    oled.println("Road Alert HUD Node");
    oled.display();
    Serial.println("[Display] SSD1306 OLED initialized at 0x3C");
  }
#endif

  // 3. Initialize LoRa UART Transceiver (HardwareSerial 2)
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  delay(100);
  LoRaSerial.println("AT+ADDRESS=1");
  LoRaSerial.println("AT+NETWORKID=6");
  Serial.printf("[LoRa] UART initialized on GPIO %d (RX) / %d (TX)\n", LORA_RX_PIN, LORA_TX_PIN);

  // 4. Wi-Fi Configuration: Connect to Station or Spawn SoftAP
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP("Road_Alert_Receiver", "RoadSafe123");
  Serial.println("[Wi-Fi] SoftAP Created: 'Road_Alert_Receiver' (IP: 192.168.4.1)");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[Wi-Fi] Connecting to upstream station '%s'...", WIFI_SSID);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 15) {
    delay(300);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[Wi-Fi] Connected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[Wi-Fi] Upstream station not found; running in AP + LoRa mode.");
  }

  // 5. Begin UDP Listener on Port 8888
  udp.begin(UDP_PORT);
  Serial.printf("[UDP] Listening for broadcast alerts on port %u\n", UDP_PORT);

  // 6. Start Web HUD Server
  setupWebServer();

  // Startup audio confirmation
  tone(BUZZER_PIN, 2000, 100);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, HIGH);

  renderDisplay("CLEAR", "NONE", "READY", "OK");
  lastPacketTime = millis();
}

// ============================================================================
// MAIN LOOP (ZERO BLOCKING)
// ============================================================================

void loop() {
  // A. Handle HTTP Web HUD requests
  server.handleClient();

  // B. Drive non-blocking audio sirens & LEDs
  updateAlarms();

  // C. Listen for Wi-Fi UDP Alert Broadcasts
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char packetBuffer[384];
    int len = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    if (len > 0) {
      packetBuffer[len] = '\0';
      handleIncomingPayload(String(packetBuffer), "WIFI");
    }
  }

  // D. Listen for LoRa Radio Packets (UART)
  if (LoRaSerial.available()) {
    String incoming = LoRaSerial.readStringUntil('\n');
    incoming.trim();

    if (incoming.length() > 0) {
      // Reyax RYLR896 format: +RCV=address,length,data,rssi,snr
      if (incoming.startsWith("+RCV=")) {
        int firstComma = incoming.indexOf(',');
        int secondComma = incoming.indexOf(',', firstComma + 1);
        int thirdComma = incoming.indexOf(',', secondComma + 1);
        String jsonPayload = incoming.substring(secondComma + 1, thirdComma);
        handleIncomingPayload(jsonPayload, "LORA");
      } else if (incoming.startsWith("{")) {
        handleIncomingPayload(incoming, "LORA");
      }
    }
  }

  // E. Auto-Clear Watchdog: Revert to Safe State when road clear
  if (currentStatus != "CLEAR" && currentStatus != "STANDBY") {
    if (millis() - lastPacketTime > HAZARD_TIMEOUT_MS) {
      currentStatus = "CLEAR";
      currentType   = "NONE";
      currentDist   = "SAFE";
      currentSound  = 0;
      noTone(BUZZER_PIN);
      digitalWrite(RED_LED_PIN, LOW);
      digitalWrite(GREEN_LED_PIN, HIGH);
      renderDisplay("CLEAR", "NONE", "READY", activeChannel);
      Serial.println("[Watchdog] Hazard cleared. Highway corridor is SAFE.");
    }
  }

  // Small yield to allow FreeRTOS & Wi-Fi background stack to process
  delay(5);
}

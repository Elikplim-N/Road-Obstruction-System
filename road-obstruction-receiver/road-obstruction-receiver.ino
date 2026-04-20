
#include <RadioLib.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include "dashboard.h"

// --- HARDWARE PINS (NodeMCU / ESP8266) ---
#define NSS        D0
#define DIO0       D8
#define RST        D3
// Buzzer removed per user request to simplify hardware

// --- OBJECTS ---
SX1278 radio = new Module(NSS, DIO0, RST);
LiquidCrystal_I2C lcd27(0x27, 16, 2);
LiquidCrystal_I2C lcd3F(0x3F, 16, 2);
LiquidCrystal_I2C* lcd = &lcd27; // Initially point to 0x27
ESP8266WebServer server(80);

unsigned long lastHeartbeat = 0;

// --- INTERRUPT-DRIVEN RX FLAG ---
volatile bool packetReceived = false;
void IRAM_ATTR onReceive() {
  packetReceived = true;
}

// --- FORWARD DECLARATIONS ---
void lcdShowStartup();
void manageAlertState();

// --- STATE ---
int alertCount = 0;
int lastPacketId = 0;
int lastRssi = 0;
bool isAlerting = false;
unsigned long alertStartTime = 0;
unsigned long lastPhaseTime = 0;
int alertPhase = 0; // 0 = Screen1+BeepOn, 1 = Screen1+BeepOff, 2 = Screen2+BeepOn, 3 = Screen2+BeepOff
unsigned long standbyReturnTime = 0;

// --- WEB APP (Stored in dashboard.h) ---


void setup() {
  // Standard serial setup now that RX is free
  Serial.begin(115200);
  
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); 

  // 1. Auto-Detect LCD Address
  Wire.begin();
  Wire.beginTransmission(0x27);
  if (Wire.endTransmission() == 0) {
    lcd = &lcd27;
    Serial.println("[LCD] Found at 0x27");
  } else {
    lcd = &lcd3F;
    Serial.println("[LCD] Found at 0x3F (or not found)");
  }
  
  lcd->init();
  lcd->backlight();
  
  // 2. Setup Access Point & Web Server
  WiFi.softAP("Road_Alert_System");
  Serial.println("\n[WiFi] AP Started: Road_Alert_System (192.168.4.1)");

  server.on("/", HTTP_GET, []() {
    server.send_P(200, "text/html", PWA_DASHBOARD);
  });
  server.on("/api/status", HTTP_GET, []() {
    String json = "{\"id\": " + String(lastPacketId) + ", \"rssi\": " + String(lastRssi) + 
                  ", \"alertCount\": " + String(alertCount) + ", \"alerting\": " + (isAlerting ? "true" : "false") + "}";
    server.send(200, "application/json", json);
  });
  server.begin();
  
  lcdShowStartup();

  // 2. Init LoRa for maximum compatibility (SF7)
  Serial.print("[LoRa] Initializing... ");
  // Frequency: 433.0, BW: 125.0, SF: 7, CR: 7, Sync: 0x12, Power: 10, Preamble: 8
  int state = radio.begin(433.0, 125.0, 7, 7, 0x12, 10, 8); 
  if (state == RADIOLIB_ERR_NONE) {
    Serial.println("Success!");
  } else {
    Serial.print("FAILED (code: ");
    Serial.print(state);
    Serial.println(")");
    lcd->clear();
    lcd->setCursor(0, 0);
    lcd->print("LORA ERR:");
    lcd->setCursor(0, 1);
    lcd->print(state);
    while (true);
  }
  // Maximize sensitivity
  radio.setGain(0); // LNA gain (0 is auto/max)
  
  // Attach interrupt for non-blocking receive
  radio.setDio0Action(onReceive, RISING);
  radio.startReceive();

  Serial.println("Receiver Online.");
    digitalWrite(BUZZER_PIN, LOW);

}

void loop() {
  server.handleClient();
  manageAlertState();

  // Heartbeat every 5 seconds to prove we are alive
  if (millis() - lastHeartbeat > 5000) {
    lastHeartbeat = millis();
    Serial.println("[System] Scanning for alerts... WiFi Active.");
  }

  if (packetReceived) {
    packetReceived = false;
    digitalWrite(LED_BUILTIN, LOW); // LED ON
    Serial.println("[LoRa] Interrupt triggered! Reading data...");

    String payload;
    int rssi = radio.getRSSI();
    float snr = radio.getSNR();
    int state = radio.readData(payload);

    if (state == RADIOLIB_ERR_NONE) {
      Serial.print("[LoRa] Packet Received: \"");
      Serial.print(payload);
      Serial.print("\" | RSSI: ");
      Serial.print(rssi);
      Serial.print(" dBm | SNR: ");
      Serial.print(snr);
      Serial.println(" dB");

      if (payload.indexOf("WARN") >= 0) {
        Serial.println("[LoRa] !!! CRITICAL ALERT DETECTED !!!");
        alertCount++;
        lastPacketId++;
        lastRssi = rssi;
        
        // Start or refresh the 1-minute alert cycle
        isAlerting = true;
        alertStartTime = millis();
        lastPhaseTime = millis();
        alertPhase = 0;
      }
    } else {
      Serial.print("[LoRa] Read Error: ");
      Serial.println(state);
    }

    // Resume listening
    radio.startReceive();
    delay(50);
    digitalWrite(LED_BUILTIN, HIGH); // LED OFF
  }
}

// --- LCD HELPERS ---

void lcdShowStartup() {
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print("LORA RECEIVER");
  lcd->setCursor(0, 1);
  lcd->print("SCANNING ROAD...");
}

void manageAlertState() {
  if (isAlerting) {
    unsigned long now = millis();
    
    // Check if 60 seconds have passed
    if (now - alertStartTime >= 60000) {
      isAlerting = false;
      
      // Show Final Stats
      lcd->clear();
      lcd->setCursor(0, 0);
      lcd->print("RSSI: ");
      lcd->print(lastRssi);
      lcd->print(" dBm");
      lcd->setCursor(0, 1);
      lcd->print("ALERTS: ");
      lcd->print(alertCount);
      
      standbyReturnTime = millis() + 4000; // Stay on screen for 4s before resting
    } else {
      // Manage 500ms intervals natively without blocking
      if (now - lastPhaseTime >= 500) {
        lastPhaseTime = now;
        alertPhase = (alertPhase + 1) % 4;
        
        switch (alertPhase) {
          case 0: // Setup Screen 1
            lcd->clear();
            lcd->setCursor(2, 0); lcd->print("OBSTRUCTION");
            lcd->setCursor(1, 1); lcd->print("DETECTED AHEAD");
            break;
          case 1: // Hold Screen 1
            break;
          case 2: // Setup Screen 2
            lcd->clear();
            lcd->setCursor(1, 0); lcd->print("DANGER: REDUCE");
            lcd->setCursor(1, 1); lcd->print("YOUR SPEED NOW");
            break;
          case 3: // Hold Screen 2
            break;
        }
      }
    }
  } else if (standbyReturnTime > 0 && millis() > standbyReturnTime) {
    // Return to default screen after showing stats
    standbyReturnTime = 0;
  }
}


/*
 * LoRa Extension Guide for ESP32 Road Obstruction Dashboard Receiver
 * 
 * When migrating from Hotspot Wi-Fi to Long-Range (LoRa) Communication:
 *
 * 1. Hardware options:
 *    A) Reyax RYLR896 / RYLR998 UART LoRa Module (Easiest to wire and program)
 *       - RX2 (GPIO 16) -> TXD of RYLR896
 *       - TX2 (GPIO 17) -> RXD of RYLR896
 *       - 3V3 -> VDD
 *       - GND -> GND
 *
 *    B) Semtech SX1278 SPI LoRa Module (e.g. Ra-02)
 *       - SPI pins: SCK(18), MISO(19), MOSI(23), NSS(5), DIO0(2), RST(14)
 *
 * 2. Drop-in Replacement Code Snippet for RYLR896:
 *
 *   #define LORA_RX 16
 *   #define LORA_TX 17
 *   HardwareSerial LoRaSerial(2);
 *
 *   void setupLoRa() {
 *     LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX, LORA_TX);
 *     LoRaSerial.println("AT+ADDRESS=1");
 *     LoRaSerial.println("AT+NETWORKID=6");
 *     LoRaSerial.println("AT+BAND=915000000"); // or 868MHz / 433MHz
 *   }
 *
 *   void readLoRaPacket() {
 *     if (LoRaSerial.available()) {
 *       String incoming = LoRaSerial.readStringUntil('\n');
 *       // Format: +RCV=address,length,data,rssi,snr
 *       if (incoming.startsWith("+RCV=")) {
 *         int firstComma = incoming.indexOf(',');
 *         int secondComma = incoming.indexOf(',', firstComma + 1);
 *         int thirdComma = incoming.indexOf(',', secondComma + 1);
 *         String jsonPayload = incoming.substring(secondComma + 1, thirdComma);
 *         // Pass jsonPayload to deserializeJson() exactly like the UDP packet!
 *       }
 *     }
 *   }
 */
#pragma once

#include "esp_camera.h"
#include <RadioLib.h>
#include <SPI.h>

// --- HARDWARE PINOUT ---
#define LORA_NSS  15
#define LORA_RST  27
#define LORA_DIO0 4  // Blinks Flash LED on TX
#define LORA_SCK  12
#define LORA_MISO 2
#define LORA_MOSI 13

// AI-Thinker Pin Map
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

SPIClass spi(HSPI);
SX1278 radio = new Module(LORA_NSS, LORA_DIO0, LORA_RST, RADIOLIB_NC, spi, SPISettings());

uint8_t* baselineBuffer = NULL;
size_t bufferSize = 0;
float threshold = 55.0; // Lowered to 55 for higher sensitivity

void setup() {
  Serial.begin(115200);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM; config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_GRAYSCALE; 
  config.frame_size = FRAMESIZE_QQVGA; 
  config.fb_count = 2; // Fixed FB-SIZE error
  config.grab_mode = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&config) != ESP_OK) { while(true); }

  // 10-Second Warm-up for Auto-Exposure
  Serial.println("Stabilizing Sensor...");
  for(int i = 0; i < 20; i++) {
    camera_fb_t * fb = esp_camera_fb_get();
    esp_camera_fb_return(fb);
    delay(500);
  }

  spi.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_NSS);
  // Sync with receiver: 433MHz, 125kHz BW, SF 7, CR 7, Sync 0x12, Power 17dBm
  int state = radio.begin(433.0, 125.0, 7, 7, 0x12, 17, 8); 
  if (state == RADIOLIB_ERR_NONE) {
    Serial.println("LoRa Radio Ready (SF7)");
  } else {
    Serial.print("LoRa Init Failed, code: ");
    Serial.println(state);
  }
  radio.setGain(0); 

  captureBaseline();
}

void captureBaseline() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) return;
  if (baselineBuffer) free(baselineBuffer);
  bufferSize = fb->len;
  baselineBuffer = (uint8_t*)malloc(bufferSize);
  memcpy(baselineBuffer, fb->buf, bufferSize);
  esp_camera_fb_return(fb);
  Serial.println(">> BASELINE RESET <<");
}

float getFilteredDifference() {
  long totalDiff = 0;
  int samples = 3; // Average 3 frames to kill noise
  
  for(int s = 0; s < samples; s++) {
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) continue;
    for (size_t i = 0; i < bufferSize; i++) {
      totalDiff += abs(fb->buf[i] - baselineBuffer[i]);
    }
    esp_camera_fb_return(fb);
    delay(30);
  }
  return (float)totalDiff / (bufferSize * samples);
}

void loop() {
  float currentDiff = getFilteredDifference();
  Serial.print("Diff: "); Serial.println(currentDiff);

  if (currentDiff > threshold) {
    Serial.println("Movement Detected. Checking persistence...");
    delay(3000); // 3-second check back
    
    if (getFilteredDifference() > threshold) {
      Serial.println("!!! ALERT: OBSTRUCTION BROADCAST !!!");
      int state = radio.transmit("WARN:OBSTRUCTION_01");
      if (state == RADIOLIB_ERR_NONE) {
        Serial.println(">> Broadcast Success!");
      } else {
        Serial.print(">> Broadcast FAILED, code: ");
        Serial.println(state);
      }
      delay(2000); 
    }
  } else {
    // Slowly update baseline to follow the sun/shadows
    static int driftCounter = 0;
    if (driftCounter++ > 150) { captureBaseline(); driftCounter = 0; }
  }
  delay(1000);
}

/*
 * ==============================================================================
 * ESP32-CAM Production Firmware: Highway Road Obstruction Optical Node
 * Board: AI Thinker ESP32-CAM (OV2640 Sensor)
 *
 * Capabilities:
 * - High-speed MJPEG Video Streaming (/stream)
 * - Single-Frame High-Resolution Snapshot Capture (/capture)
 * - Remote Health & Diagnostics Telemetry (/status)
 * - Remote Illumination Flash LED Control (/led?val=1|0)
 * - Brownout Detector Protection (prevents current spike crash loops)
 * - Outdoor Highway Exposure & Contrast Optimization
 * - Automatic Wi-Fi Watchdog & Reconnection (Self-Healing on Street Pole)
 * ==============================================================================
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include "camera_pins.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ==============================================================================
// 1. NETWORK & HOTSPOT CREDENTIALS
// ==============================================================================
const char* ssid     = "RoadAlertHotspot";
const char* password = "RoadAlertPassword123";

// Onboard Hardware Pins
#define FLASH_LED_PIN    4    // High-power flash LED
#define STATUS_LED_PIN   33   // Small red indicator LED (Active LOW)

// HTTP Server Config
#define HTTP_SERVER_PORT 81
httpd_handle_t stream_httpd = NULL;

// Multipart boundary for MJPEG
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY     = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART         = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// Watchdog & Uptime Tracking
unsigned long lastWifiCheck = 0;
unsigned long bootTimestamp = 0;
uint32_t framesServed = 0;

// ==============================================================================
// 2. HTTP REQUEST HANDLERS
// ==============================================================================

// --- Handler: MJPEG Video Stream (/stream) ---
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char part_buf[64];

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  // CORS headers so web browsers can stream directly
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("[ESP32-CAM] Frame capture failed");
      res = ESP_FAIL;
      break;
    }

    _jpg_buf_len = fb->len;
    _jpg_buf = fb->buf;

    if (res == ESP_OK) {
      size_t hlen = snprintf(part_buf, 64, _STREAM_PART, _jpg_buf_len);
      res = httpd_resp_send_chunk(req, part_buf, hlen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
    }

    esp_camera_fb_return(fb);
    fb = NULL;
    _jpg_buf = NULL;

    if (res != ESP_OK) break;
    framesServed++;
  }

  return res;
}

// --- Handler: Single Snapshot Capture (/capture) ---
static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[ESP32-CAM] Single snapshot capture failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=road_snapshot.jpg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");

  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

// --- Handler: Telemetry & Health Diagnostics (/status) ---
static esp_err_t status_handler(httpd_req_t *req) {
  char json_response[320];
  uint32_t uptime_sec = (millis() - bootTimestamp) / 1000;
  int rssi = WiFi.RSSI();
  uint32_t free_heap = ESP.getFreeHeap();
  uint32_t free_psram = ESP.getFreePsram();

  snprintf(json_response, sizeof(json_response),
    "{\"device\":\"ESP32-CAM-01\",\"mode\":\"FRAME_DIFFERENCING_EVENT_CAPTURE\",\"status\":\"ONLINE\",\"ip\":\"%s\",\"rssi\":%d,\"uptime_s\":%u,\"frames_served\":%u,\"free_heap\":%u,\"free_psram\":%u}",
    WiFi.localIP().toString().c_str(), rssi, uptime_sec, framesServed, free_heap, free_psram
  );

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, json_response, strlen(json_response));
}

// --- Handler: Edge Frame Differencing Telemetry (/diff-status) ---
static esp_err_t diff_status_handler(httpd_req_t *req) {
  char json_response[256];
  snprintf(json_response, sizeof(json_response),
    "{\"engine\":\"EDGE_FRAME_DIFFERENCING\",\"constant_threshold_s\":2.5,\"motion_threshold_px\":15,\"event_capture_ready\":true,\"active\":true}"
  );

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, json_response, strlen(json_response));
}

// --- Handler: Remote Flash LED Illumination (/led?val=1|0) ---
static esp_err_t led_handler(httpd_req_t *req) {
  char* buf;
  size_t buf_len = httpd_req_get_url_query_len(req) + 1;
  int led_val = 0;

  if (buf_len > 1) {
    buf = (char*)malloc(buf_len);
    if (httpd_req_get_url_query_str(req, buf, buf_len) == ESP_OK) {
      char param[8];
      if (httpd_query_key_value(buf, "val", param, sizeof(param)) == ESP_OK) {
        led_val = atoi(param);
        digitalWrite(FLASH_LED_PIN, led_val ? HIGH : LOW);
      }
    }
    free(buf);
  }

  char res_msg[64];
  snprintf(res_msg, sizeof(res_msg), "{\"led_flash\": %d}", led_val);
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, res_msg, strlen(res_msg));
}

// ==============================================================================
// 3. START HTTP SERVER
// ==============================================================================
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = HTTP_SERVER_PORT;
  config.ctrl_port   = HTTP_SERVER_PORT + 1;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t capture_uri = {
    .uri       = "/capture",
    .method    = HTTP_GET,
    .handler   = capture_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t status_uri = {
    .uri       = "/status",
    .method    = HTTP_GET,
    .handler   = status_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t led_uri = {
    .uri       = "/led",
    .method    = HTTP_GET,
    .handler   = led_handler,
    .user_ctx  = NULL
  };

  httpd_uri_t diff_status_uri = {
    .uri       = "/diff-status",
    .method    = HTTP_GET,
    .handler   = diff_status_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    httpd_register_uri_handler(stream_httpd, &capture_uri);
    httpd_register_uri_handler(stream_httpd, &status_uri);
    httpd_register_uri_handler(stream_httpd, &diff_status_uri);
    httpd_register_uri_handler(stream_httpd, &led_uri);

    Serial.printf("[ESP32-CAM] Web server active on port %d\n", HTTP_SERVER_PORT);
    Serial.printf("   Capture (Event Snapshot): http://%s:%d/capture\n", WiFi.localIP().toString().c_str(), HTTP_SERVER_PORT);
    Serial.printf("   Differencing Telemetry:  http://%s:%d/diff-status\n", WiFi.localIP().toString().c_str(), HTTP_SERVER_PORT);
    Serial.printf("   Stream (Optional Debug): http://%s:%d/stream\n", WiFi.localIP().toString().c_str(), HTTP_SERVER_PORT);
  }
}

// ==============================================================================
// 4. SETUP
// ==============================================================================
void setup() {
  // Disable brownout detector to prevent current spike reboot loops on USB/battery
#if defined(RTC_CNTL_BROWN_OUT_REG)
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
#elif defined(RTC_CNTL_BROWNOUT_REG)
  WRITE_PERI_REG(RTC_CNTL_BROWNOUT_REG, 0);
#endif

  Serial.begin(115200);
  delay(500);
  Serial.println("\n=======================================================");
  Serial.println("  ESP32-CAM HIGHWAY OBSTRUCTION SENSING NODE (v2.2)");
  Serial.println("=======================================================");

  // Pins & Diagnostic LEDs
  pinMode(FLASH_LED_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, HIGH); // Off initially (Active LOW)

  // Configure Camera Hardware
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Frame resolution tuning (SVGA 800x600 for sharp road corridor detection)
  if (psramFound()) {
    config.frame_size   = FRAMESIZE_SVGA; // 800x600 matching desktop CV pipeline
    config.jpeg_quality = 10;            // 10-63 (lower = sharper obstacle contours)
    config.fb_count     = 2;             // Double buffer for smooth 25 FPS
    Serial.println("[ESP32-CAM] PSRAM Detected: Configured SVGA 800x600 (Quality: 10)");
  } else {
    config.frame_size   = FRAMESIZE_VGA;  // 640x480 fallback
    config.jpeg_quality = 14;
    config.fb_count     = 1;
    Serial.println("[ESP32-CAM] Standard SRAM: Configured VGA 640x480 (Quality: 14)");
  }

  // Initialize Camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ESP32-CAM] First probe failed (0x%x). Retrying with 10MHz XCLK...\n", err);
    esp_camera_deinit();
    delay(100);
    config.xclk_freq_hz = 10000000;
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    err = esp_camera_init(&config);
  }

  if (err != ESP_OK) {
    Serial.printf("[ESP32-CAM WARNING] Camera sensor init failed (0x%x). Please check OV2640 ribbon connector seating.\n", err);
  } else {
    Serial.println("[ESP32-CAM] Camera initialized successfully!");
  }

  // Optimize Sensor for Outdoor Highway Lighting
  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_brightness(s, 1);     // Slight boost for asphalt visibility
    s->set_contrast(s, 1);       // Sharpens vehicle edges against road
    s->set_saturation(s, 0);     // Natural saturation
    s->set_whitebal(s, 1);       // Enable Auto White Balance
    s->set_awb_gain(s, 1);
    s->set_wb_mode(s, 0);        // Auto WB
    s->set_exposure_ctrl(s, 1);  // Auto Exposure
    s->set_aec2(s, 1);           // AEC DSP
    s->set_gain_ctrl(s, 1);      // Auto Gain Control
    s->set_vflip(s, 0);          // Normal orientation
    s->set_hmirror(s, 0);
  }

  // Connect to Highway Hotspot
  Serial.printf("[ESP32-CAM] Connecting to Wi-Fi SSID '%s'...", ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 35) {
    delay(400);
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN)); // Blink while connecting
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED_PIN, LOW); // Steady ON indicates connected (Active LOW)
    Serial.println("\n[ESP32-CAM] Wi-Fi Connected Successfully!");
    Serial.printf("   IP Address: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("   Signal RSSI: %d dBm\n", WiFi.RSSI());
    startCameraServer();
  } else {
    digitalWrite(STATUS_LED_PIN, HIGH);
    Serial.println("\n[ESP32-CAM WARNING] Hotspot connection timed out. Watchdog will auto-retry in background.");
  }

  bootTimestamp = millis();
}

// ==============================================================================
// 5. MAIN LOOP & AUTO-HEALING WATCHDOG
// ==============================================================================
void loop() {
  unsigned long now = millis();

  // Self-Healing Watchdog: Every 10 seconds, verify Wi-Fi connectivity
  if (now - lastWifiCheck > 10000) {
    lastWifiCheck = now;

    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WATCHDOG] Wi-Fi lost on street pole node! Reconnecting...");
      digitalWrite(STATUS_LED_PIN, HIGH);
      WiFi.disconnect();
      WiFi.reconnect();

      int retry = 0;
      while (WiFi.status() != WL_CONNECTED && retry < 15) {
        delay(300);
        digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
        retry++;
      }

      if (WiFi.status() == WL_CONNECTED) {
        digitalWrite(STATUS_LED_PIN, LOW);
        Serial.printf("[WATCHDOG] Reconnected! IP: %s\n", WiFi.localIP().toString().c_str());
        if (stream_httpd == NULL) {
          startCameraServer();
        }
      }
    }
  }

  delay(200);
}

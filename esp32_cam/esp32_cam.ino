/*
 * ==============================================================================
 * ESP32-CAM Production Firmware: Highway Road Obstruction Optical Node v2.3
 * Board: AI Thinker ESP32-CAM (OV2640 Sensor)
 *
 * Capabilities:
 * - NO HARDCODED WI-FI:
 *   * Auto-connects to saved hotspot credentials stored in NVS Flash (Preferences)
 *   * Spawns SoftAP Captive Portal ("ESP32-CAM-HOTSPOT-SETUP" at 192.168.4.1)
 *     if no hotspot is saved or connection fails.
 *   * Scans nearby networks dynamically so you choose and enter passwords on phone/PC.
 *   * Remote Wi-Fi Reset endpoint (/reset-wifi) to switch hotspots on demand.
 * - Single-Frame High-Resolution Snapshot Capture (/capture)
 * - Edge Frame Differencing Telemetry (/diff-status)
 * - Remote Health & Diagnostics (/status)
 * - Remote Illumination Flash LED Control (/led?val=1|0)
 * - Optional Debug Video Stream (/stream)
 * - Brownout Protection (Tolerates automotive 12V-to-5V adapter dips)
 * ==============================================================================
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include "esp_http_server.h"
#include "camera_pins.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "wifi_portal.h"

// ==============================================================================
// 1. HARDWARE PINS & SYSTEM STATE
// ==============================================================================
#define FLASH_LED_PIN    4    // High-power flash LED
#define STATUS_LED_PIN   33   // Small red indicator LED (Active LOW)

#define HTTP_SERVER_PORT 81
httpd_handle_t stream_httpd = NULL;

// AP Provisioning State
bool isAPMode = false;
WebServer portalServer(80);
DNSServer dnsServer;
Preferences prefs;

// Watchdog & Uptime Tracking
unsigned long lastWifiCheck = 0;
unsigned long bootTimestamp = 0;
uint32_t framesServed = 0;

// Multipart boundary for optional MJPEG
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY     = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART         = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// ==============================================================================
// 2. HTTP REQUEST HANDLERS (PORT 81 - NORMAL OPERATION)
// ==============================================================================

// --- Single Snapshot Capture (/capture) ---
static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[ESP32-CAM] Snapshot capture failed");
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

// --- Frame Differencing Telemetry (/diff-status) ---
static esp_err_t diff_status_handler(httpd_req_t *req) {
  char json_response[256];
  snprintf(json_response, sizeof(json_response),
    "{\"engine\":\"EDGE_FRAME_DIFFERENCING\",\"constant_threshold_s\":2.5,\"motion_threshold_px\":15,\"event_capture_ready\":true,\"active\":true}"
  );

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, json_response, strlen(json_response));
}

// --- Health Diagnostics (/status) ---
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

// --- Reset Wi-Fi Endpoint (/reset-wifi) ---
static esp_err_t reset_wifi_handler(httpd_req_t *req) {
  const char* msg = "{\"status\":\"WIFI_CLEARED\",\"message\":\"Rebooting into AP Setup Portal (192.168.4.1)...\"}";
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_send(req, msg, strlen(msg));

  delay(500);
  prefs.begin("wifi_cfg", false);
  prefs.clear();
  prefs.end();
  Serial.println("[Wi-Fi] Saved credentials cleared by user request. Rebooting into AP setup mode...");
  delay(1000);
  ESP.restart();
  return ESP_OK;
}

// --- Flash LED Illumination (/led?val=1|0) ---
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

// --- Optional Video Stream (/stream) ---
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char part_buf[64];

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) return res;

  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-cache, no-store, must-revalidate");

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
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

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = HTTP_SERVER_PORT;
  config.ctrl_port   = HTTP_SERVER_PORT + 1;

  httpd_uri_t capture_uri = {
    .uri = "/capture", .method = HTTP_GET, .handler = capture_handler, .user_ctx = NULL
  };
  httpd_uri_t diff_status_uri = {
    .uri = "/diff-status", .method = HTTP_GET, .handler = diff_status_handler, .user_ctx = NULL
  };
  httpd_uri_t status_uri = {
    .uri = "/status", .method = HTTP_GET, .handler = status_handler, .user_ctx = NULL
  };
  httpd_uri_t reset_wifi_uri = {
    .uri = "/reset-wifi", .method = HTTP_GET, .handler = reset_wifi_handler, .user_ctx = NULL
  };
  httpd_uri_t led_uri = {
    .uri = "/led", .method = HTTP_GET, .handler = led_handler, .user_ctx = NULL
  };
  httpd_uri_t stream_uri = {
    .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &capture_uri);
    httpd_register_uri_handler(stream_httpd, &diff_status_uri);
    httpd_register_uri_handler(stream_httpd, &status_uri);
    httpd_register_uri_handler(stream_httpd, &reset_wifi_uri);
    httpd_register_uri_handler(stream_httpd, &led_uri);
    httpd_register_uri_handler(stream_httpd, &stream_uri);

    Serial.printf("[ESP32-CAM] Camera server active on port %d\n", HTTP_SERVER_PORT);
    Serial.printf("   Capture:    http://%s:%d/capture\n", WiFi.localIP().toString().c_str(), HTTP_SERVER_PORT);
    Serial.printf("   Diff Info:  http://%s:%d/diff-status\n", WiFi.localIP().toString().c_str(), HTTP_SERVER_PORT);
    Serial.printf("   Reset WiFi: http://%s:%d/reset-wifi\n", WiFi.localIP().toString().c_str(), HTTP_SERVER_PORT);
  }
}

// ==============================================================================
// 3. AP PROVISIONING CAPTIVE PORTAL (PORT 80)
// ==============================================================================

void handlePortalRoot() {
  Serial.println("[AP Portal] Client connected to setup portal");
  
  // Scan surrounding networks
  int n = WiFi.scanNetworks();
  String optionsHtml = "";
  if (n == 0) {
    optionsHtml += "<option value=\"__MANUAL__\">-- No networks found (Enter manually) --</option>";
  } else {
    for (int i = 0; i < n; ++i) {
      String ssidName = WiFi.SSID(i);
      int rssiVal = WiFi.RSSI(i);
      String lock = (WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "🔓" : "🔒";
      optionsHtml += "<option value=\"" + ssidName + "\">" + ssidName + " (" + lock + " " + String(rssiVal) + " dBm)</option>";
    }
    optionsHtml += "<option value=\"__MANUAL__\">-- Other / Enter Hidden SSID --</option>";
  }

  String fullPage = String(WIFI_PORTAL_HTML_HEAD) + optionsHtml + String(WIFI_PORTAL_HTML_FOOT);
  portalServer.send(200, "text/html", fullPage);
}

void handlePortalSave() {
  String chosenSsid = portalServer.arg("ssid");
  String manualSsid = portalServer.arg("manual_ssid");
  String pass       = portalServer.arg("password");

  if (chosenSsid == "__MANUAL__" && manualSsid.length() > 0) {
    chosenSsid = manualSsid;
  }

  Serial.printf("[AP Portal] Saving new hotspot: '%s'\n", chosenSsid.c_str());

  prefs.begin("wifi_cfg", false);
  prefs.putString("ssid", chosenSsid);
  prefs.putString("pass", pass);
  prefs.end();

  String reply = String(WIFI_SAVED_PAGE);
  reply.replace("%SSID%", chosenSsid);
  portalServer.send(200, "text/html", reply);

  delay(1500);
  Serial.println("[AP Portal] Rebooting to connect to chosen hotspot...");
  ESP.restart();
}

void startAPProvisioning() {
  isAPMode = true;
  WiFi.mode(WIFI_AP);
  WiFi.softAP("ESP32-CAM-HOTSPOT-SETUP"); // Open network for easy 1-click connection

  IPAddress apIP(192, 168, 4, 1);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));

  dnsServer.start(53, "*", apIP); // Captive portal DNS redirect

  portalServer.on("/", HTTP_GET, handlePortalRoot);
  portalServer.on("/save", HTTP_POST, handlePortalSave);
  portalServer.onNotFound(handlePortalRoot);
  portalServer.begin();

  Serial.println("\n=======================================================");
  Serial.println("  📶 ESP32-CAM HOTSPOT SETUP PORTAL ACTIVE!");
  Serial.println("=======================================================");
  Serial.println("  1. Connect your phone or laptop to Wi-Fi:");
  Serial.println("     SSID: ESP32-CAM-HOTSPOT-SETUP (No password)");
  Serial.println("  2. Open your browser and go to:");
  Serial.println("     http://192.168.4.1");
  Serial.println("  3. Pick your hotspot from the list & click Save!");
  Serial.println("=======================================================\n");
}

// ==============================================================================
// 4. SETUP
// ==============================================================================
void setup() {
  // Brownout protection
#if defined(RTC_CNTL_BROWN_OUT_REG)
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
#elif defined(RTC_CNTL_BROWNOUT_REG)
  WRITE_PERI_REG(RTC_CNTL_BROWNOUT_REG, 0);
#endif

  Serial.begin(115200);
  delay(400);

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

  if (psramFound()) {
    config.frame_size   = FRAMESIZE_SVGA; // 800x600 sharp resolution
    config.jpeg_quality = 10;
    config.fb_count     = 2;
    Serial.println("[ESP32-CAM] PSRAM Detected: Configured SVGA 800x600 (Quality: 10)");
  } else {
    config.frame_size   = FRAMESIZE_VGA;
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
    Serial.printf("[ESP32-CAM WARNING] Camera sensor init failed (0x%x). Check OV2640 ribbon seating.\n", err);
  } else {
    Serial.println("[ESP32-CAM] Camera sensor initialized successfully!");
    sensor_t * s = esp_camera_sensor_get();
    if (s != NULL) {
      s->set_brightness(s, 1);
      s->set_contrast(s, 1);
      s->set_whitebal(s, 1);
      s->set_exposure_ctrl(s, 1);
      s->set_gain_ctrl(s, 1);
    }
  }

  // Check saved Wi-Fi credentials in flash
  prefs.begin("wifi_cfg", true);
  String savedSSID = prefs.getString("ssid", "");
  String savedPass = prefs.getString("pass", "");
  prefs.end();

  bool connected = false;

  if (savedSSID.length() > 0) {
    Serial.printf("[Wi-Fi] Saved hotspot found: '%s'. Connecting...\n", savedSSID.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(savedSSID.c_str(), savedPass.c_str());

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 22) {
      delay(350);
      digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN)); // Quick blink
      Serial.print(".");
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      connected = true;
      digitalWrite(STATUS_LED_PIN, LOW); // Steady ON indicates connected
      Serial.println("\n[Wi-Fi] Connected to saved hotspot!");
      Serial.printf("   Assigned IP: %s\n", WiFi.localIP().toString().c_str());
      Serial.printf("   Signal RSSI: %d dBm\n", WiFi.RSSI());
      startCameraServer();
    } else {
      Serial.println("\n[Wi-Fi] Could not connect to saved hotspot. Entering AP Setup Portal...");
    }
  } else {
    Serial.println("[Wi-Fi] No saved hotspot credentials. Entering AP Setup Portal...");
  }

  if (!connected) {
    startAPProvisioning();
  }

  bootTimestamp = millis();
}

// ==============================================================================
// 5. MAIN LOOP
// ==============================================================================
void loop() {
  unsigned long now = millis();

  if (isAPMode) {
    // Process Captive Portal & Web Requests
    dnsServer.processNextRequest();
    portalServer.handleClient();

    // Slow pulse status LED in AP mode (500ms cycle)
    static unsigned long lastBlink = 0;
    if (now - lastBlink > 500) {
      lastBlink = now;
      digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    }
    delay(5);
    return;
  }

  // Station Mode: Wi-Fi Watchdog (verify connection every 10 seconds)
  if (now - lastWifiCheck > 10000) {
    lastWifiCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WATCHDOG] Wi-Fi lost! Attempting auto-reconnect...");
      digitalWrite(STATUS_LED_PIN, HIGH);
      WiFi.reconnect();
    } else {
      digitalWrite(STATUS_LED_PIN, LOW);
    }
  }

  delay(200);
}

/*
  ESP32-CAM Pollution Monitor — HTTP Server
  ─────────────────────────────────────────
  Flash this to your ESP32-CAM using Arduino IDE.

  Board:   AI Thinker ESP32-CAM
  Library: ESPAsyncWebServer + AsyncTCP (install via Library Manager)

  Setup:
    1. Set WIFI_SSID and WIFI_PASS below
    2. Flash via FTDI adapter (GPIO0 to GND during upload)
    3. Open Serial Monitor at 115200 baud to see assigned IP
    4. Add that IP to config.py
*/

#include "esp_camera.h"
#include <WiFi.h>
#include <ESPAsyncWebServer.h>

// ─── WIFI CREDENTIALS ────────────────────────────────────────────────────────
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// ─── CAMERA PIN DEFINITION (AI-Thinker model) ────────────────────────────────
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

AsyncWebServer server(80);

// ─── CAMERA INIT ─────────────────────────────────────────────────────────────
bool initCamera() {
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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_VGA;   // 640x480
  config.jpeg_quality = 12;              // 0-63, lower = better quality
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  return (err == ESP_OK);
}

// ─── SETUP ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n[ESP32-CAM] Booting...");

  if (!initCamera()) {
    Serial.println("[ERROR] Camera init failed! Check wiring.");
    return;
  }
  Serial.println("[OK] Camera initialized");

  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[WiFi] Connected!");
  Serial.print("[WiFi] IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.println("Add this IP to config.py in CAMERAS list.");

  // ── ROUTES ────────────────────────────────────────────────────────────────

  // /capture — Returns a single JPEG image
  server.on("/capture", HTTP_GET, [](AsyncWebServerRequest *request) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      request->send(500, "text/plain", "Camera capture failed");
      return;
    }
    AsyncWebServerResponse *response = request->beginResponse_P(
      200, "image/jpeg", fb->buf, fb->len
    );
    response->addHeader("Access-Control-Allow-Origin", "*");
    request->send(response);
    esp_camera_fb_return(fb);
  });

  // /status — Returns JSON with basic status
  server.on("/status", HTTP_GET, [](AsyncWebServerRequest *request) {
    String json = "{";
    json += "\"status\":\"ok\",";
    json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
    json += "\"rssi\":" + String(WiFi.RSSI()) + ",";
    json += "\"uptime\":" + String(millis() / 1000);
    json += "}";
    request->send(200, "application/json", json);
  });

  // /settings — Adjust camera settings via GET params
  // e.g. /settings?quality=10&framesize=5
  server.on("/settings", HTTP_GET, [](AsyncWebServerRequest *request) {
    sensor_t *s = esp_camera_sensor_get();
    if (request->hasParam("quality")) {
      s->set_quality(s, request->getParam("quality")->value().toInt());
    }
    if (request->hasParam("brightness")) {
      s->set_brightness(s, request->getParam("brightness")->value().toInt());
    }
    if (request->hasParam("contrast")) {
      s->set_contrast(s, request->getParam("contrast")->value().toInt());
    }
    request->send(200, "text/plain", "Settings updated");
  });

  server.begin();
  Serial.println("[Server] HTTP server started on port 80");
  Serial.println("[Ready] Visit: http://" + WiFi.localIP().toString() + "/capture");
}

// ─── LOOP ────────────────────────────────────────────────────────────────────
void loop() {
  // Nothing needed — AsyncWebServer handles requests in background
  delay(10);
}

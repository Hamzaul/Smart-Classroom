/*
  Smart Classroom - ESP32 Firmware
  Board: ESP32 DevKit V1 (default board for this project)

  Runs a small HTTP server on the classroom ESP32 that accepts JSON
  commands from the Flask backend (see backend/services/esp32_service.py)
  and drives:
    - 3 status LEDs (green / yellow / red)
    - 1 piezo buzzer
    - 1 16x2 I2C LCD

  Protocol (matches ESP32Service._send_http exactly):
    POST /command
      {"cmd": "alert", "severity": "warning", "led": "yellow",
       "buzzer_ms": 300, "lcd_line1": "Notice", "lcd_line2": "..."}
      {"cmd": "display", "lcd_line1": "Present: 22/25", "lcd_line2": "Avg Attn: 78%"}
      {"cmd": "clear"}

    GET /status
      -> {"online": true, "uptime_ms": 12345, "wifi_rssi_dbm": -52}

  Libraries required (install via Arduino Library Manager):
    - ArduinoJson (by Benoit Blanchon)      v6.x or v7.x
    - LiquidCrystal I2C (by Frank de Brabander, or "hd44780" as an alternative)
    - WiFi.h and WebServer.h are bundled with the ESP32 board package.

  Board package: install "esp32 by Espressif Systems" via Boards Manager,
  then select Board: "ESP32 Dev Module".
*/

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ---------------------------------------------------------------------
// Configuration - EDIT THESE for your classroom WiFi network
// ---------------------------------------------------------------------
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Set a static IP so this matches ESP32_IP in backend/.env exactly.
// If you'd rather use DHCP, comment out the three IPAddress lines below
// and the WiFi.config(...) call in setupWiFi().
IPAddress STATIC_IP(192, 168, 1, 50);
IPAddress GATEWAY(192, 168, 1, 1);
IPAddress SUBNET(255, 255, 255, 0);

// ---------------------------------------------------------------------
// Pin assignments (ESP32 DevKit V1) - see hardware/docs/wiring_diagram.md
// ---------------------------------------------------------------------
const int PIN_LED_GREEN = 25;
const int PIN_LED_YELLOW = 26;
const int PIN_LED_RED = 27;
const int PIN_BUZZER = 14;

// LCD: SDA=21 (default), SCL=22 (default) - no explicit pins needed for Wire.begin()
const uint8_t LCD_I2C_ADDRESS = 0x27; // common default; use an I2C scanner sketch if blank
const uint8_t LCD_COLS = 16;
const uint8_t LCD_ROWS = 2;

// ---------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------
WebServer server(80);
LiquidCrystal_I2C lcd(LCD_I2C_ADDRESS, LCD_COLS, LCD_ROWS);

unsigned long buzzerOffAtMs = 0;
bool buzzerActive = false;

// ---------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------
void setupPins() {
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  allLedsOff();
  digitalWrite(PIN_BUZZER, LOW);
}

void setupLCD() {
  Wire.begin(); // default SDA=21, SCL=22 on ESP32 DevKit V1
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Smart Classroom");
  lcd.setCursor(0, 1);
  lcd.print("Booting...");
}

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.config(STATIC_IP, GATEWAY, SUBNET);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi");
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
    // Fail safe: after 20s of no connection, reboot and try again rather
    // than hanging forever with a dead classroom display.
    if (millis() - startAttempt > 20000) {
      Serial.println("\nWiFi connection timed out. Restarting...");
      ESP.restart();
    }
  }
  Serial.println("\nWiFi connected.");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connected");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP().toString());
  delay(1500);
}

void setupRoutes() {
  server.on("/command", HTTP_POST, handleCommand);
  server.on("/status", HTTP_GET, handleStatus);
  server.onNotFound([]() {
    server.send(404, "application/json", "{\"error\":\"not found\"}");
  });
  server.begin();
  Serial.println("HTTP server started on port 80");
}

void setup() {
  Serial.begin(115200);
  delay(200);
  setupPins();
  setupLCD();
  setupWiFi();
  setupRoutes();
  displayIdleScreen();
}

// ---------------------------------------------------------------------
// Main loop - keep this non-blocking so the HTTP server stays responsive
// ---------------------------------------------------------------------
void loop() {
  server.handleClient();
  updateBuzzerNonBlocking();

  // Auto-reconnect if WiFi drops mid-session (classroom AP hiccups happen).
  static unsigned long lastWifiCheck = 0;
  if (millis() - lastWifiCheck > 10000) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi disconnected, reconnecting...");
      WiFi.reconnect();
    }
  }
}

// ---------------------------------------------------------------------
// HTTP handlers
// ---------------------------------------------------------------------
void handleCommand() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"missing JSON body\"}");
    return;
  }

  StaticJsonDocument<512> doc;
  DeserializationError parseError = deserializeJson(doc, server.arg("plain"));
  if (parseError) {
    server.send(400, "application/json", "{\"error\":\"invalid JSON\"}");
    return;
  }

  const char *cmd = doc["cmd"] | "";

  if (strcmp(cmd, "alert") == 0) {
    handleAlertCommand(doc);
  } else if (strcmp(cmd, "display") == 0) {
    handleDisplayCommand(doc);
  } else if (strcmp(cmd, "clear") == 0) {
    handleClearCommand();
  } else {
    server.send(400, "application/json", "{\"error\":\"unknown cmd\"}");
    return;
  }

  server.send(200, "application/json", "{\"success\":true}");
}

void handleStatus() {
  StaticJsonDocument<256> doc;
  doc["online"] = true;
  doc["uptime_ms"] = millis();
  doc["wifi_rssi_dbm"] = WiFi.RSSI();
  doc["ip"] = WiFi.localIP().toString();

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// ---------------------------------------------------------------------
// Command implementations
// ---------------------------------------------------------------------
void handleAlertCommand(JsonDocument &doc) {
  const char *led = doc["led"] | "yellow";
  int buzzerMs = doc["buzzer_ms"] | 0;
  const char *line1 = doc["lcd_line1"] | "";
  const char *line2 = doc["lcd_line2"] | "";

  setLed(led);
  if (buzzerMs > 0) {
    startBuzzer(buzzerMs);
  }
  displayLcd(line1, line2);
}

void handleDisplayCommand(JsonDocument &doc) {
  const char *line1 = doc["lcd_line1"] | "";
  const char *line2 = doc["lcd_line2"] | "";
  displayLcd(line1, line2);
}

void handleClearCommand() {
  allLedsOff();
  stopBuzzer();
  displayIdleScreen();
}

// ---------------------------------------------------------------------
// LED control
// ---------------------------------------------------------------------
void allLedsOff() {
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_RED, LOW);
}

void setLed(const char *color) {
  allLedsOff();
  if (strcmp(color, "green") == 0) {
    digitalWrite(PIN_LED_GREEN, HIGH);
  } else if (strcmp(color, "yellow") == 0) {
    digitalWrite(PIN_LED_YELLOW, HIGH);
  } else if (strcmp(color, "red") == 0) {
    digitalWrite(PIN_LED_RED, HIGH);
  }
}

// ---------------------------------------------------------------------
// Buzzer control (non-blocking: loop() turns it off via millis(), no delay())
// ---------------------------------------------------------------------
void startBuzzer(int durationMs) {
  digitalWrite(PIN_BUZZER, HIGH);
  buzzerActive = true;
  buzzerOffAtMs = millis() + (unsigned long)durationMs;
}

void stopBuzzer() {
  digitalWrite(PIN_BUZZER, LOW);
  buzzerActive = false;
}

void updateBuzzerNonBlocking() {
  if (buzzerActive && millis() >= buzzerOffAtMs) {
    stopBuzzer();
  }
}

// ---------------------------------------------------------------------
// LCD helpers
// ---------------------------------------------------------------------
void displayLcd(const char *line1, const char *line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

void displayIdleScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Smart Classroom");
  lcd.setCursor(0, 1);
  lcd.print("System Ready");
}

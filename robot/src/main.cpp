#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

// WiFi credentials (provided)
const char* WIFI_SSID = "HackTheNorth";
const char* WIFI_PASS = "HTN2025!";

// Heartbeat LED (on many ESP32 boards GPIO2 has onboard LED; adjust if needed)
const int LED_PIN = 2;

// Servo configuration
static const int SERVO_COUNT = 6; // 0-2 left arm, 3-5 right arm
int SERVO_PINS[SERVO_COUNT] = {13, 14, 12, 17, 18, 19};
Servo servos[SERVO_COUNT];
int currentAngles[SERVO_COUNT];

// Pulse range typical for SG90/MG90 etc.
const int SERVO_MIN_US = 500;  // microseconds
const int SERVO_MAX_US = 2400; // microseconds

// HTTP server on port 80
WebServer server(80);

unsigned long lastBlink = 0;
bool ledState = false;

void sendJson(const JsonDocument &doc, int status = 200) {
  String out;
  serializeJson(doc, out);
  server.send(status, "application/json", out);
}

void handleRoot() {
  Serial.println("📡 GET / - Status request received");
  StaticJsonDocument<256> doc;
  doc["status"] = "ok";
  JsonArray pins = doc.createNestedArray("pins");
  for (int i = 0; i < SERVO_COUNT; ++i) pins.add(SERVO_PINS[i]);
  JsonArray angles = doc.createNestedArray("angles");
  for (int i = 0; i < SERVO_COUNT; ++i) angles.add(currentAngles[i]);
  doc["mapping"] = "indices 0-2 left arm joints, 3-5 right arm joints";
  Serial.println("✅ Status response sent");
  sendJson(doc);
}

bool parseJsonBody(StaticJsonDocument<512> &doc) {
  if (server.hasArg("plain")) {
    DeserializationError err = deserializeJson(doc, server.arg("plain"));
    if (err) return false;
    return true;
  }
  return false;
}

void handleSetSingle() {
  Serial.print("📡 POST /servo - Single servo request received from ");
  Serial.println(server.client().remoteIP());

  StaticJsonDocument<512> doc;
  if (!parseJsonBody(doc)) {
    Serial.println("❌ Invalid JSON in request");
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }
  if (!doc.containsKey("id") || !doc.containsKey("angle")) {
    Serial.println("❌ Missing id or angle in request");
    server.send(400, "application/json", "{\"error\":\"Missing id or angle\"}");
    return;
  }

  int id = doc["id"].as<int>();
  int angle = doc["angle"].as<int>();

  Serial.print("🎯 Request: Servo ");
  Serial.print(id);
  Serial.print(" -> ");
  Serial.print(angle);
  Serial.println("°");

  if (id < 0 || id >= SERVO_COUNT) {
    Serial.print("❌ Invalid servo ID: ");
    Serial.println(id);
    server.send(400, "application/json", "{\"error\":\"Invalid servo id\"}");
    return;
  }
  if (angle < 0 || angle > 180) {
    Serial.print("❌ Invalid angle: ");
    Serial.println(angle);
    server.send(400, "application/json", "{\"error\":\"Angle out of range 0-180\"}");
    return;
  }

  servos[id].write(angle);
  currentAngles[id] = angle;

  Serial.print("✅ Servo ");
  Serial.print(id);
  Serial.print(" moved to ");
  Serial.print(angle);
  Serial.println("°");

  StaticJsonDocument<128> res;
  res["id"] = id;
  res["angle"] = angle;
  sendJson(res);
}

void handleSetBatch() {
  Serial.print("📡 POST /servos - Batch servo request received from ");
  Serial.println(server.client().remoteIP());

  StaticJsonDocument<512> doc;
  if (!parseJsonBody(doc)) {
    Serial.println("❌ Invalid JSON in batch request");
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }
  if (!doc.containsKey("angles")) {
    Serial.println("❌ Missing angles array in batch request");
    server.send(400, "application/json", "{\"error\":\"Missing angles array\"}");
    return;
  }

  JsonArray arr = doc["angles"].as<JsonArray>();
  if (arr.size() != SERVO_COUNT) {
    Serial.print("❌ Invalid angles array size: ");
    Serial.print(arr.size());
    Serial.print(" (expected ");
    Serial.print(SERVO_COUNT);
    Serial.println(")");
    server.send(400, "application/json", "{\"error\":\"angles array must have 6 values\"}");
    return;
  }

  // Validate all angles first
  Serial.print("🎯 Batch request angles: [");
  for (int i = 0; i < SERVO_COUNT; ++i) {
    int a = arr[i].as<int>();
    if (i > 0) Serial.print(", ");
    Serial.print(a);
    if (a < 0 || a > 180) {
      Serial.println("]");
      Serial.print("❌ Invalid angle at index ");
      Serial.print(i);
      Serial.print(": ");
      Serial.println(a);
      server.send(400, "application/json", "{\"error\":\"All angles must be 0-180\"}");
      return;
    }
  }
  Serial.println("]");

  // Apply all angles
  Serial.println("🔄 Applying angles to servos...");
  for (int i = 0; i < SERVO_COUNT; ++i) {
    int a = arr[i].as<int>();
    servos[i].write(a);
    currentAngles[i] = a;
    Serial.print("  Servo ");
    Serial.print(i);
    Serial.print(" -> ");
    Serial.print(a);
    Serial.println("°");
  }

  Serial.println("✅ All servos moved successfully!");

  StaticJsonDocument<256> res;
  JsonArray angles = res.createNestedArray("angles");
  for (int i = 0; i < SERVO_COUNT; ++i) angles.add(currentAngles[i]);
  sendJson(res);
}

void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"Not found\"}");
}

void setupWiFi() {
  Serial.println("=== WiFi Setup Starting ===");
  WiFi.mode(WIFI_STA);
  Serial.println("WiFi mode set to STA (Station)");

  Serial.print("Connecting to WiFi network: ");
  Serial.println(WIFI_SSID);

  // First try DHCP to get on the network
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting with DHCP");

  unsigned long startAttempt = millis();
  int dotCount = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print('.');
    dotCount++;

    // Print status every 10 dots
    if (dotCount % 10 == 0) {
      Serial.print(" [");
      Serial.print((millis() - startAttempt) / 1000);
      Serial.print("s] Status: ");
      switch(WiFi.status()) {
        case WL_IDLE_STATUS: Serial.print("IDLE"); break;
        case WL_NO_SSID_AVAIL: Serial.print("NO_SSID"); break;
        case WL_SCAN_COMPLETED: Serial.print("SCAN_COMPLETED"); break;
        case WL_CONNECTED: Serial.print("CONNECTED"); break;
        case WL_CONNECT_FAILED: Serial.print("CONNECT_FAILED"); break;
        case WL_CONNECTION_LOST: Serial.print("CONNECTION_LOST"); break;
        case WL_DISCONNECTED: Serial.print("DISCONNECTED"); break;
        default: Serial.print("UNKNOWN"); break;
      }
      Serial.println();
    }

    if (millis() - startAttempt > 20000) {
      Serial.println("\n❌ WiFi connection timeout after 20 seconds!");
      Serial.print("Final status: ");
      Serial.println(WiFi.status());
      Serial.println("Rebooting ESP32...");
      delay(2000);
      ESP.restart();
    }
  }

  Serial.println();
  Serial.println("🎉 WiFi CONNECTION ESTABLISHED!");
  Serial.println("=== Network Information ===");
  Serial.print("✅ DHCP IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("✅ Gateway: ");
  Serial.println(WiFi.gatewayIP());
  Serial.print("✅ Subnet Mask: ");
  Serial.println(WiFi.subnetMask());
  Serial.print("✅ Primary DNS: ");
  Serial.println(WiFi.dnsIP());
  Serial.print("✅ MAC Address: ");
  Serial.println(WiFi.macAddress());
  Serial.print("✅ Signal Strength (RSSI): ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  Serial.print("✅ HTTP Server Port: ");
  Serial.println(80);
  Serial.println("=========================");
  Serial.println("📝 NOTE: ESP32 is using DHCP - IP may change on reboot!");
  Serial.println("📝 Use the IP shown above for your Python script.");
}

void setupServos() {
  Serial.println("=== Servo Setup Starting ===");
  Serial.println("Allocating PWM timers...");

  // Allow allocation of all timers
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  Serial.println("✅ PWM timers allocated");

  Serial.print("Initializing ");
  Serial.print(SERVO_COUNT);
  Serial.println(" servos...");

  for (int i = 0; i < SERVO_COUNT; ++i) {
    Serial.print("  Servo ");
    Serial.print(i);
    Serial.print(" -> Pin ");
    Serial.print(SERVO_PINS[i]);
    Serial.print("...");

    servos[i].setPeriodHertz(50); // Standard 50Hz
    servos[i].attach(SERVO_PINS[i], SERVO_MIN_US, SERVO_MAX_US);
    currentAngles[i] = 90; // neutral start
    servos[i].write(currentAngles[i]);

    Serial.print(" ✅ Initialized at ");
    Serial.print(currentAngles[i]);
    Serial.println("°");
    delay(100); // Small delay between servo inits
  }
  Serial.println("��� All servos initialized successfully!");
  Serial.println("=== Servo Setup Complete ===");
}

void setupServer() {
  Serial.println("=== HTTP Server Setup Starting ===");
  Serial.println("Registering HTTP endpoints...");
  server.on("/", HTTP_GET, handleRoot);
  Serial.println("  ✅ GET / (status endpoint)");
  server.on("/servo", HTTP_POST, handleSetSingle);
  Serial.println("  ✅ POST /servo (single servo control)");
  server.on("/servos", HTTP_POST, handleSetBatch);
  Serial.println("  ✅ POST /servos (batch servo control)");
  server.onNotFound(handleNotFound);
  Serial.println("  ✅ 404 handler registered");

  server.begin();
  Serial.println("🎉 HTTP server started successfully on port 80!");
  Serial.println("=== HTTP Server Setup Complete ===");
}

void setup() {
  Serial.begin(115200);
  delay(2000); // Give serial time to initialize

  // Startup countdown to allow time to open serial monitor
  Serial.println("\n\n╔═════════════════════════════════════════��════════╗");
  Serial.println("║          ESP32 SERVO CONTROLLER STARTING        ║");
  Serial.println("╚══════════════════════════════════════════════════╝");
  Serial.println("⏰ Starting in 5 seconds... Open serial monitor now!");

  for (int i = 5; i > 0; i--) {
    Serial.print("Starting in: ");
    Serial.print(i);
    Serial.println(" seconds...");
    delay(1000);
  }

  Serial.println("\n🚀 INITIALIZING ESP32 SERVO CONTROLLER...\n");

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  setupWiFi();
  setupServos();
  setupServer();

  Serial.println("\n╔══════════════════════════════════════════════════╗");
  Serial.println("║              SYSTEM READY!                      ║");
  Serial.println("╚══════════════════════════════════════════════════╝");
  Serial.println("🎉 ESP32 Servo Controller is now operational!");
  Serial.println("📡 Listening for HTTP requests...");
  Serial.println("\n📖 USAGE EXAMPLES:");
  Serial.println("Example single: curl -X POST http://" + WiFi.localIP().toString() + "/servo -H 'Content-Type: application/json' -d '{\"id\":0,\"angle\":120}'");
  Serial.println("Example batch: curl -X POST http://" + WiFi.localIP().toString() + "/servos -H 'Content-Type: application/json' -d '{\"angles\":[90,45,120,60,30,150]}'");
  Serial.println("\n💡 Watch this monitor for real-time servo commands and debug info!");
  Serial.println("============================================================");
}

void loop() {
  server.handleClient();
  unsigned long now = millis();
  if (now - lastBlink >= 1000) { // heartbeat every second
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    lastBlink = now;
  }
}
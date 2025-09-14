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
int SERVO_PINS[SERVO_COUNT] = {13, 14, 12, 27, 26, 25};
Servo servos[SERVO_COUNT];
int currentAngles[SERVO_COUNT];

// Servo ID mapping for numeric commands (1-6 instead of names)
struct ServoMapping {
  int id;        // Numeric ID (1-6)
  int index;     // Array index (0-5)
  const char* name; // Description for debugging
};

static const ServoMapping SERVO_MAP[] = {
  {1,0,"left_shoulder_vertical"},
  {2,1,"left_shoulder_horizontal"},
  {3,2,"left_elbow_vertical"},
  {4,3,"right_shoulder_vertical"},
  {5,4,"right_shoulder_horizontal"},
  {6,5,"right_elbow_vertical"}
};
static const int SERVO_MAP_SIZE = sizeof(SERVO_MAP)/sizeof(ServoMapping);

// Function to get servo index from numeric ID (1-6)
int getServoIndex(int numericId) {
  for(int i=0;i<SERVO_MAP_SIZE;++i) {
    if(SERVO_MAP[i].id==numericId) return SERVO_MAP[i].index;
  }
  return -1;
}

const char* getServoName(int numericId) {
  for(int i=0;i<SERVO_MAP_SIZE;++i) {
    if(SERVO_MAP[i].id==numericId) return SERVO_MAP[i].name;
  }
  return "unknown";
}

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
  for (int i = 0; i < SERVO_COUNT; ++i) {
    pins.add(SERVO_PINS[i]);
  }
  JsonArray angles = doc.createNestedArray("angles");
  for (int i = 0; i < SERVO_COUNT; ++i) {
    angles.add(currentAngles[i]);
  }
  doc["mapping"] = "indices 0-2 left arm joints, 3-5 right arm joints";
  doc["free_heap"] = ESP.getFreeHeap();
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

void handleSequence() {
  Serial.print("📡 POST /sequence - Sequence request received from ");
  Serial.println(server.client().remoteIP());

  unsigned long heapBefore = ESP.getFreeHeap();

  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"Missing body\"}");
    return;
  }

  String body = server.arg("plain");
  size_t bodyLen = body.length();
  Serial.print("📥 Received JSON body length: ");
  Serial.println(bodyLen);

  // Parse JSON in memory
  Serial.println("🧠 Parsing sequence in memory");
  size_t cap = 2048 + bodyLen; // Generous allocation for ESP32 WROVER
  DynamicJsonDocument *docPtr = new (std::nothrow) DynamicJsonDocument(cap);
  if (!docPtr) {
    server.send(500, "application/json", "{\"error\":\"Memory allocation failure\"}");
    return;
  }

  DeserializationError jerr = deserializeJson(*docPtr, body);
  if (jerr) {
    Serial.print("❌ JSON deserialization error: ");
    Serial.println(jerr.c_str());
    delete docPtr;
    server.send(400, "application/json", "{\"error\":\"JSON parse failed\"}");
    return;
  }

  JsonDocument &doc = *docPtr;

  if (!doc.containsKey("sequence")) {
    delete docPtr;
    server.send(400, "application/json", "{\"error\":\"Missing sequence field\"}");
    return;
  }

  JsonArray sequence = doc["sequence"].as<JsonArray>();
  String skill = doc.containsKey("skill") ? doc["skill"].as<String>() : String("Unknown Skill");

  Serial.print("🎭 Skill: ");
  Serial.println(skill);
  Serial.print("🧾 Steps: ");
  Serial.println(sequence.size());

  // Execute steps
  for (JsonObject step : sequence) {
    if (!step.containsKey("commands")) {
      delete docPtr;
      server.send(400, "application/json", "{\"error\":\"Step missing commands\"}");
      return;
    }
    JsonArray commands = step["commands"].as<JsonArray>();
    Serial.print("🔢 Step ");
    Serial.print(step["seq_num"].as<int>());
    Serial.print(" cmds=");
    Serial.println(commands.size());

    for (JsonObject c : commands) {
      if (!c.containsKey("id") || !c.containsKey("deg")) {
        delete docPtr;
        server.send(400, "application/json", "{\"error\":\"Command missing id/deg\"}");
        return;
      }
      int sid = c["id"].as<int>();
      int angle = c["deg"].as<int>();
      int idx = getServoIndex(sid);
      if (idx < 0) {
        delete docPtr;
        server.send(400,"application/json","{\"error\":\"Bad servo id\"}");
        return;
      }
      if (angle < 0 || angle > 180) {
        delete docPtr;
        server.send(400,"application/json","{\"error\":\"Angle out of range\"}");
        return;
      }
      servos[idx].write(angle);
      currentAngles[idx]=angle;
      Serial.print("  ✅ Servo ");
      Serial.print(sid);
      Serial.print(" -> ");
      Serial.print(angle);
      Serial.println("°");
    }
    delay(400);
  }

  unsigned long heapAfter = ESP.getFreeHeap();

  // Build response
  DynamicJsonDocument resp(512 + SERVO_COUNT * 8);
  resp["status"] = "completed";
  resp["skill"] = skill;
  resp["steps_executed"] = sequence.size();
  resp["heap_before"] = heapBefore;
  resp["heap_after"] = heapAfter;
  resp["body_size"] = bodyLen;
  resp["memory_used"] = heapBefore - heapAfter;
  JsonArray finalAngles = resp.createNestedArray("final_angles");
  for (int i=0;i<SERVO_COUNT;++i) {
    finalAngles.add(currentAngles[i]);
  }

  sendJson(resp);
  delete docPtr; // Free memory
}

void handleSetSingle() {
  Serial.print("📡 POST /servo - Single servo request received from ");
  Serial.println(server.client().remoteIP());
  StaticJsonDocument<512> doc;
  if(!parseJsonBody(doc) || !doc.containsKey("id") || !doc.containsKey("angle")) {
    server.send(400,"application/json","{\"error\":\"Bad request\"}");
    return;
  }
  int id = doc["id"].as<int>();
  int angle = doc["angle"].as<int>();
  if(id < 1 || id > SERVO_COUNT) {
    server.send(400,"application/json","{\"error\":\"Invalid servo id (1-6)\"}");
    return;
  }
  if(angle < 0 || angle > 180) {
    server.send(400,"application/json","{\"error\":\"Angle out of range 0-180\"}");
    return;
  }
  int idx = getServoIndex(id);
  if(idx < 0) {
    server.send(400,"application/json","{\"error\":\"Mapping failure\"}");
    return;
  }
  servos[idx].write(angle);
  currentAngles[idx] = angle;
  StaticJsonDocument<128> res;
  res["id"] = id;
  res["name"] = getServoName(id);
  res["angle"] = angle;
  sendJson(res);
}

void handleSetBatch() {
  Serial.print("📡 POST /servos - Batch servo request received from ");
  Serial.println(server.client().remoteIP());
  StaticJsonDocument<512> doc;
  if(!parseJsonBody(doc) || !doc.containsKey("angles")) {
    server.send(400,"application/json","{\"error\":\"Bad request\"}");
    return;
  }
  JsonArray arr = doc["angles"].as<JsonArray>();
  if(arr.size() != SERVO_COUNT) {
    server.send(400,"application/json","{\"error\":\"Need 6 angles (index 1..6)\"}");
    return;
  }
  for(int i=0;i<SERVO_COUNT;++i) {
    int a = arr[i].as<int>();
    if(a<0||a>180){
      server.send(400,"application/json","{\"error\":\"Angle out of range\"}");
      return;
    }
  }
  for(int i=0;i<SERVO_COUNT;++i) {
    int a = arr[i].as<int>();
    servos[i].write(a);
    currentAngles[i]=a;
  }
  StaticJsonDocument<256> res;
  JsonArray out=res.createNestedArray("angles");
  for(int i=0;i<SERVO_COUNT;++i) {
    out.add(currentAngles[i]);
  }
  sendJson(res);
}

void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"Not found\"}");
}

void handleCalibrate() {
  Serial.println("🛠 POST /calibrate - neutralizing servos then restarting");
  for(int i=0;i<SERVO_COUNT;++i){
    servos[i].write(90);
    currentAngles[i]=90;
  }
  StaticJsonDocument<256> doc;
  doc["status"]="restarting";
  doc["action"]="calibrate";
  doc["neutral_angle"]=90;
  JsonArray arr=doc.createNestedArray("angles");
  for(int i=0;i<SERVO_COUNT;++i) {
    arr.add(currentAngles[i]);
  }
  doc["restart_in_ms"]=500;
  doc["timestamp_ms"]=millis();
  sendJson(doc);
  Serial.println("🔄 Rebooting in 500ms...");
  delay(500);
  ESP.restart();
}

void setupWiFi() {
  Serial.println("=== WiFi Setup Starting ===");
  WiFi.mode(WIFI_STA);
  Serial.println("WiFi mode set to STA (Station)");

  Serial.print("Connecting to WiFi network: ");
  Serial.println(WIFI_SSID);

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

    servos[i].setPeriodHertz(50);
    servos[i].attach(SERVO_PINS[i], SERVO_MIN_US, SERVO_MAX_US);
    currentAngles[i] = 90;
    servos[i].write(currentAngles[i]);

    Serial.print(" ✅ Initialized at ");
    Serial.print(currentAngles[i]);
    Serial.println("°");
    delay(100);
  }
  Serial.println("✅ All servos initialized successfully!");
  Serial.println("=== Servo Setup Complete ===");
}

void setupServer() {
  Serial.println("=== HTTP Server Setup Starting ===");
  Serial.println("Registering HTTP endpoints...");
  server.on("/", HTTP_GET, handleRoot);
  server.on("/servo", HTTP_POST, handleSetSingle);
  server.on("/servos", HTTP_POST, handleSetBatch);
  server.on("/sequence", HTTP_POST, handleSequence);
  server.on("/calibrate", HTTP_POST, handleCalibrate);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("🎉 HTTP server started successfully on port 80!");
  Serial.println("=== HTTP Server Setup Complete ===");
}

void setup() {
  Serial.begin(115200);
  delay(1200);
  Serial.println("\n=== ESP32 SERVO CONTROLLER BOOT ===");

  Serial.println("\n\n============================================================");
  Serial.println("          ESP32 SERVO CONTROLLER STARTING        ");
  Serial.println("============================================================");
  Serial.println("Starting in 2 seconds... Open serial monitor now!");

  for (int i = 2; i > 0; i--) {
    Serial.print("Starting in: ");
    Serial.print(i);
    Serial.println(" seconds...");
    delay(1000);
  }

  Serial.println("\nINITIALIZING ESP32 SERVO CONTROLLER...\n");

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  setupWiFi();
  setupServos();
  setupServer();

  Serial.println("\n============================================================");
  Serial.println("              SYSTEM READY!                      ");
  Serial.println("============================================================");
  Serial.println("ESP32 Servo Controller is now operational!");
  Serial.println("Listening for HTTP requests...");
  Serial.print("Free heap memory: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
  Serial.println("\nUSAGE EXAMPLES:");
  Serial.print("Example single: curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/servo -H 'Content-Type: application/json' -d '{\"id\":1,\"angle\":120}'");
  Serial.print("Example batch: curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/servos -H 'Content-Type: application/json' -d '{\"angles\":[90,45,120,60,30,150]}'");
  Serial.print("Example sequence: curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/sequence -H 'Content-Type: application/json' -d '{\"skill\":\"wave\",\"sequence\":[{\"seq_num\":1,\"commands\":[{\"id\":2,\"deg\":45}]}]}'");
  Serial.print("Calibrate (neutral + restart): curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/calibrate");
  Serial.println("\nWatch this monitor for real-time servo commands and debug info!");
  Serial.println("============================================================");
}

void loop() {
  server.handleClient();
  unsigned long now = millis();
  if (now - lastBlink >= 1000) {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    lastBlink = now;
  }
}
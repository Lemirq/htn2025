#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>
#include <queue>

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

// Servo command structure
struct ServoCommand {
  int angle;
  unsigned long timestamp;
};

// Batch collection structure
struct BatchedCommand {
  int servoId;
  int angle;
  unsigned long timestamp;
  bool isSet;
};

// Batch collection for 6 servo commands
BatchedCommand batchBuffer[SERVO_COUNT];
int batchCount = 0;
bool batchReady = false;
unsigned long batchStartTime = 0;
const unsigned long BATCH_TIMEOUT = 1000; // 1 second timeout to auto-execute incomplete batches

// Command stacks for each servo (using std::queue as a stack)
std::queue<ServoCommand> servoStacks[SERVO_COUNT];

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

// Function to invert angle for servo on pin 12 (index 2 - left_elbow_vertical)
int adjustAngleForServo(int servoIndex, int angle) {
  // Invert angle for servo at index 2 (pin 12)
  if (servoIndex == 2) {
    return 180 - angle;
  }
  return angle;
}

// Initialize batch buffer
void initializeBatch() {
  for (int i = 0; i < SERVO_COUNT; ++i) {
    batchBuffer[i].servoId = i + 1;
    batchBuffer[i].angle = 90; // default angle
    batchBuffer[i].timestamp = 0;
    batchBuffer[i].isSet = false;
  }
  batchCount = 0;
  batchReady = false;
  batchStartTime = millis();
}

// Execute the current batch
void executeBatch() {
  if (batchCount == 0) return;

  Serial.println("🚀 Executing batch of " + String(batchCount) + " servo commands simultaneously:");

  // Execute all commands in the batch at the same time
  for (int i = 0; i < SERVO_COUNT; ++i) {
    if (batchBuffer[i].isSet) {
      int idx = getServoIndex(batchBuffer[i].servoId);
      if (idx >= 0) {
        int adjustedAngle = adjustAngleForServo(idx, batchBuffer[i].angle);
        servos[idx].write(adjustedAngle);
        currentAngles[idx] = batchBuffer[i].angle; // Store original angle for status

        Serial.print("  ⚡ Servo ");
        Serial.print(batchBuffer[i].servoId);
        Serial.print(" (");
        Serial.print(getServoName(batchBuffer[i].servoId));
        Serial.print(") -> ");
        Serial.print(batchBuffer[i].angle);
        if (idx == 2) { // Show inverted angle for pin 12
          Serial.print("° (inverted to ");
          Serial.print(adjustedAngle);
          Serial.print("°)");
        } else {
          Serial.print("°");
        }
        Serial.println();
      }
    }
  }

  Serial.println("✅ Batch execution complete!");

  // Reset batch
  initializeBatch();
}

// Check if batch should be auto-executed due to timeout
void checkBatchTimeout() {
  if (batchCount > 0 && (millis() - batchStartTime) >= BATCH_TIMEOUT) {
    Serial.println("⏰ Batch timeout reached - executing incomplete batch");
    executeBatch();
  }
}

// Pulse range typical for SG90/MG90 etc.
const int SERVO_MIN_US = 500;  // microseconds
const int SERVO_MAX_US = 2400; // microseconds

// HTTP server on port 80
WebServer server(80);

unsigned long lastBlink = 0;
bool ledState = false;
unsigned long lastStackExecution[SERVO_COUNT] = {0};
const unsigned long STACK_EXECUTION_INTERVAL = 50; // Execute stack every 50ms

void sendJson(const JsonDocument &doc, int status = 200) {
  String out;
  serializeJson(doc, out);
  server.send(status, "application/json", out);
}

void handleRoot() {
  Serial.println("📡 GET / - Status request received");
  StaticJsonDocument<1024> doc;
  doc["status"] = "ok";
  JsonArray pins = doc.createNestedArray("pins");
  for (int i = 0; i < SERVO_COUNT; ++i) {
    pins.add(SERVO_PINS[i]);
  }
  JsonArray angles = doc.createNestedArray("angles");
  for (int i = 0; i < SERVO_COUNT; ++i) {
    angles.add(currentAngles[i]);
  }

  // Add stack status
  JsonArray stackSizes = doc.createNestedArray("stack_sizes");
  for (int i = 0; i < SERVO_COUNT; ++i) {
    stackSizes.add(servoStacks[i].size());
  }

  // Add batch status
  doc["batch_count"] = batchCount;
  doc["batch_ready"] = batchReady;
  doc["batch_timeout_remaining"] = BATCH_TIMEOUT - (millis() - batchStartTime);

  doc["mapping"] = "indices 0-2 left arm joints, 3-5 right arm joints";
  doc["free_heap"] = ESP.getFreeHeap();
  Serial.println("✅ Status response sent");
  sendJson(doc);
}

// Simple servo command handler - collects 6 commands before executing
void handleServos() {
  Serial.print("📡 POST /servo - Servo command received from ");
  Serial.println(server.client().remoteIP());

  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"Missing body\"}");
    return;
  }

  String body = server.arg("plain");
  body.trim();

  Serial.print("📥 Raw command: ");
  Serial.println(body);

  // Simple JSON parsing - just looking for id and angle
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, body);

  if (error) {
    Serial.print("❌ JSON error: ");
    Serial.println(error.c_str());
    server.send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
    return;
  }

  // Extract id and angle
  if (!doc.containsKey("id") || !doc.containsKey("angle")) {
    server.send(400, "application/json", "{\"error\":\"Missing id or angle\"}");
    return;
  }

  int id = doc["id"];
  int angle = doc["angle"];

  // Validate servo ID
  if (id < 1 || id > SERVO_COUNT) {
    server.send(400, "application/json", "{\"error\":\"Invalid servo id (1-6)\"}");
    return;
  }

  // Validate angle
  if (angle < 0 || angle > 180) {
    server.send(400, "application/json", "{\"error\":\"Angle out of range 0-180\"}");
    return;
  }

  int idx = getServoIndex(id);
  if (idx < 0) {
    server.send(400, "application/json", "{\"error\":\"Mapping failure\"}");
    return;
  }

  // Add command to batch buffer
  if (!batchBuffer[idx].isSet) {
    batchBuffer[idx].angle = angle;
    batchBuffer[idx].timestamp = millis();
    batchBuffer[idx].isSet = true;
    batchCount++;

    // Initialize batch timing if this is the first command
    if (batchCount == 1) {
      batchStartTime = millis();
    }

    Serial.print("📦 Added to batch - Servo ");
    Serial.print(id);
    Serial.print(" (");
    Serial.print(getServoName(id));
    Serial.print(") -> ");
    Serial.print(angle);
    Serial.print("° | Batch progress: ");
    Serial.print(batchCount);
    Serial.print("/");
    Serial.println(SERVO_COUNT);

    // Check if batch is complete
    if (batchCount == SERVO_COUNT) {
      batchReady = true;
      Serial.println("🎯 Batch complete! Executing all 6 servo commands...");
      executeBatch();
    }
  } else {
    // Update existing command in batch
    batchBuffer[idx].angle = angle;
    batchBuffer[idx].timestamp = millis();

    Serial.print("🔄 Updated batch - Servo ");
    Serial.print(id);
    Serial.print(" (");
    Serial.print(getServoName(id));
    Serial.print(") -> ");
    Serial.print(angle);
    Serial.print("° | Batch progress: ");
    Serial.print(batchCount);
    Serial.print("/");
    Serial.println(SERVO_COUNT);
  }

  // Send immediate response
  StaticJsonDocument<256> res;
  res["status"] = batchReady ? "batch_executed" : "batched";
  res["id"] = id;
  res["name"] = getServoName(id);
  res["angle"] = angle;
  res["batch_count"] = batchCount;
  res["batch_complete"] = (batchCount == SERVO_COUNT);
  res["timestamp"] = millis();
  sendJson(res);
}

// Handle choreographed sequence commands
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

      // Apply angle adjustment for motor inversion (pin 12)
      int adjustedAngle = adjustAngleForServo(idx, angle);
      servos[idx].write(adjustedAngle);
      currentAngles[idx] = angle; // Store original angle for status

      Serial.print("  ✅ Servo ");
      Serial.print(sid);
      Serial.print(" -> ");
      Serial.print(angle);
      if (idx == 2) { // Show inverted angle for pin 12
        Serial.print("° (inverted to ");
        Serial.print(adjustedAngle);
        Serial.print("°)");
      } else {
        Serial.print("°");
      }
      Serial.println();
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

// Process servo stacks in parallel (keeping for backwards compatibility)
void processServoStacks() {
  unsigned long now = millis();

  for (int i = 0; i < SERVO_COUNT; ++i) {
    // Check if it's time to execute next command for this servo
    if (now - lastStackExecution[i] >= STACK_EXECUTION_INTERVAL) {
      if (!servoStacks[i].empty()) {
        ServoCommand cmd = servoStacks[i].front();
        servoStacks[i].pop();

        // Execute servo command with angle adjustment
        int adjustedAngle = adjustAngleForServo(i, cmd.angle);
        servos[i].write(adjustedAngle);
        currentAngles[i] = cmd.angle; // Store original angle for status
        lastStackExecution[i] = now;

        Serial.print("⚡ Executed - Servo ");
        Serial.print(i + 1);
        Serial.print(" -> ");
        Serial.print(cmd.angle);
        if (i == 2) { // Show inverted angle for pin 12
          Serial.print("° (inverted to ");
          Serial.print(adjustedAngle);
          Serial.print("°)");
        } else {
          Serial.print("°");
        }
        Serial.print(" | Remaining in stack: ");
        Serial.println(servoStacks[i].size());
      }
    }
  }
}

void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"Not found\"}");
}

void handleCalibrate() {
  Serial.println("🛠 POST /calibrate - neutralizing servos, clearing stacks and batch");

  // Clear batch
  initializeBatch();

  // Clear all stacks
  for (int i = 0; i < SERVO_COUNT; ++i) {
    while (!servoStacks[i].empty()) {
      servoStacks[i].pop();
    }
  }

  // Set all servos to neutral with angle adjustment
  for(int i=0;i<SERVO_COUNT;++i){
    int adjustedAngle = adjustAngleForServo(i, 90);
    servos[i].write(adjustedAngle);
    currentAngles[i]=90;
  }

  StaticJsonDocument<256> doc;
  doc["status"]="calibrated";
  doc["action"]="calibrate";
  doc["neutral_angle"]=90;
  doc["stacks_cleared"]=true;
  doc["batch_cleared"]=true;
  JsonArray arr=doc.createNestedArray("angles");
  for(int i=0;i<SERVO_COUNT;++i) {
    arr.add(currentAngles[i]);
  }
  doc["timestamp_ms"]=millis();
  sendJson(doc);

  Serial.println("✅ Calibration complete - all stacks and batch cleared, servos at 90°");
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
    Serial.print(i + 1);
    Serial.print(" -> Pin ");
    Serial.print(SERVO_PINS[i]);
    Serial.print("...");

    servos[i].setPeriodHertz(50);
    servos[i].attach(SERVO_PINS[i], SERVO_MIN_US, SERVO_MAX_US);
    currentAngles[i] = 90;

    // Apply angle adjustment for initial position
    int adjustedAngle = adjustAngleForServo(i, 90);
    servos[i].write(adjustedAngle);

    Serial.print(" ✅ Initialized at ");
    Serial.print(currentAngles[i]);
    if (i == 2) { // Show inverted angle for pin 12
      Serial.print("° (inverted to ");
      Serial.print(adjustedAngle);
      Serial.print("°)");
    } else {
      Serial.print("°");
    }
    Serial.println();
    delay(100);
  }
  Serial.println("✅ All servos initialized successfully!");
  Serial.println("=== Servo Setup Complete ===");
}

void setupServer() {
  Serial.println("=== HTTP Server Setup Starting ===");
  Serial.println("Registering HTTP endpoints...");
  server.on("/", HTTP_GET, handleRoot);
  server.on("/servo", HTTP_POST, handleServos);
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
  Serial.println("\n=== ESP32 BATCHED SERVO CONTROLLER BOOT ===");

  Serial.println("\n\n============================================================");
  Serial.println("       ESP32 BATCHED SERVO CONTROLLER STARTING        ");
  Serial.println("============================================================");
  Serial.println("Starting in 2 seconds... Open serial monitor now!");

  for (int i = 2; i > 0; i--) {
    Serial.print("Starting in: ");
    Serial.print(i);
    Serial.println(" seconds...");
    delay(1000);
  }

  Serial.println("\nINITIALIZING ESP32 BATCHED SERVO CONTROLLER...\n");

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Initialize batch system
  initializeBatch();

  setupWiFi();
  setupServos();
  setupServer();

  Serial.println("\n============================================================");
  Serial.println("              SYSTEM READY!                      ");
  Serial.println("============================================================");
  Serial.println("ESP32 Batched Servo Controller is now operational!");
  Serial.println("Listening for HTTP requests...");
  Serial.print("Free heap memory: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
  Serial.println("\nUSAGE EXAMPLES:");
  Serial.print("Send servo commands (collects 6 before executing): curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/servo -H 'Content-Type: application/json' -d '{\"id\":1,\"angle\":120}'");
  Serial.print("Execute choreographed sequence: curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/sequence -H 'Content-Type: application/json' -d '{\"skill\":\"wave\",\"sequence\":[{\"seq_num\":1,\"commands\":[{\"id\":2,\"deg\":45}]}]}'");
  Serial.print("Calibrate (neutral + clear batch): curl -X POST http://");
  Serial.print(WiFi.localIP().toString());
  Serial.println("/calibrate");
  Serial.println("\nBATCH BEHAVIOR:");
  Serial.println("- Collects up to 6 servo commands");
  Serial.println("- Executes all 6 simultaneously when batch is complete");
  Serial.println("- Auto-executes incomplete batches after 1 second timeout");
  Serial.println("- Can update commands in current batch");
  Serial.println("\n🔄 SERVO INVERSION:");
  Serial.println("- Servo 3 (pin 12, left_elbow_vertical) has inverted movement");
  Serial.println("- 0° becomes 180°, 180° becomes 0°, 90° stays 90°");
  Serial.println("\n🎭 SEQUENCE ENDPOINT:");
  Serial.println("- POST /sequence for choreographed movements");
  Serial.println("- Executes immediately with timed steps");
  Serial.println("- Supports memory-efficient large sequences");
  Serial.println("============================================================");
}

void loop() {
  server.handleClient();
  processServoStacks(); // Process servo command stacks in parallel
  checkBatchTimeout(); // Check if batch should be auto-executed

  unsigned long now = millis();
  if (now - lastBlink >= 1000) {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState ? HIGH : LOW);
    lastBlink = now;
  }
}

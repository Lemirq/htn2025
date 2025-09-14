#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <MCUFRIEND_kbv.h>
#include <TouchScreen.h>

// Touchscreen pins (not used right now)
const int XP = 8, XM = A2, YP = A3, YM = 9; 
const int TS_LEFT = 127, TS_RT = 904, TS_TOP = 945, TS_BOT = 92;

MCUFRIEND_kbv tft; 
TouchScreen ts = TouchScreen(XP, YP, XM, YM, 300);

int16_t TFT_WIDTH, TFT_HEIGHT;

uint16_t monkeyBrown, monkeyTan, black, white, darkBrown;

enum FaceMode { HAPPY, ANGRY };
FaceMode currentMode = HAPPY;

// ----------------- FACE DRAWING -----------------

void drawMonkeyBase(int cx, int cy) {
    // Head
    tft.fillCircle(cx, cy, 100, monkeyBrown);

    // Ears - big and low
    tft.fillCircle(cx - 95, cy, 40, monkeyBrown); // left outer
    tft.fillCircle(cx + 95, cy, 40, monkeyBrown); // right outer
    tft.fillCircle(cx - 95, cy, 25, monkeyTan);   // left inner
    tft.fillCircle(cx + 95, cy, 25, monkeyTan);   // right inner

    // Face area (tan muzzle zone)
    tft.fillCircle(cx, cy + 20, 70, monkeyTan);
}

void drawHappyFace() {
    int cx = TFT_WIDTH / 2;
    int cy = TFT_HEIGHT / 2;

    tft.fillScreen(white);
    drawMonkeyBase(cx, cy);

    // Eyes - big and wide-set, perfectly circular
    tft.fillCircle(cx - 35, cy - 20, 22, white);
    tft.fillCircle(cx + 35, cy - 20, 22, white);
    tft.fillCircle(cx - 35, cy - 20, 12, black);
    tft.fillCircle(cx + 35, cy - 20, 12, black);
    // highlights - positioned better for circular eyes
    tft.fillCircle(cx - 31, cy - 24, 4, white);
    tft.fillCircle(cx + 39, cy - 24, 4, white);

    // Nose (small oval in muzzle)
    tft.fillCircle(cx - 6, cy + 10, 4, black);
    tft.fillCircle(cx + 6, cy + 10, 4, black);

    // Smile inside muzzle - UPWARD curve for happiness
    for (int i = 0; i < 180; i++) {
        int x = cx + cos(radians(i)) * 35;
        int y = cy + sin(radians(i)) * 20 + 35;
        tft.fillCircle(x, y, 2, darkBrown);
    }
}

void drawAngryFace() {
    int cx = TFT_WIDTH / 2;
    int cy = TFT_HEIGHT / 2;

    tft.fillScreen(white);
    drawMonkeyBase(cx, cy);

    // Angled eyebrows - slanted downward toward the nose for angry look
    // Left eyebrow - slopes down from left to center
    for (int i = 0; i < 5; i++) {
        tft.drawLine(cx - 50, cy - 40, cx - 25, cy - 25 - i, darkBrown);
    }
    // Right eyebrow - slopes down from right to center  
    for (int i = 0; i < 5; i++) {
        tft.drawLine(cx + 50, cy - 40, cx + 25, cy - 25 - i, darkBrown);
    }

    // Eyes - circular but narrowed for anger
    tft.fillCircle(cx - 35, cy - 20, 18, white);
    tft.fillCircle(cx + 35, cy - 20, 18, white);
    tft.fillCircle(cx - 35, cy - 20, 10, black);
    tft.fillCircle(cx + 35, cy - 20, 10, black);

    // Nose
    tft.fillCircle(cx - 6, cy + 10, 4, black);
    tft.fillCircle(cx + 6, cy + 10, 4, black);

    // Frown - DOWNWARD curve for anger
    for (int i = 180; i < 360; i++) {
        int x = cx + cos(radians(i)) * 35;
        int y = cy + sin(radians(i)) * 20 + 40;
        tft.fillCircle(x, y, 2, darkBrown);
    }
}

// ----------------- SETUP + LOOP -----------------

void setup() {
    uint16_t ID = tft.readID();
    if (ID == 0xD3D3) ID = 0x9486;
    tft.begin(ID);
    tft.setRotation(1);
    TFT_WIDTH = tft.width();
    TFT_HEIGHT = tft.height();

    monkeyBrown = tft.color565(120, 70, 20);
    monkeyTan   = tft.color565(230, 200, 140);
    black       = tft.color565(0, 0, 0);
    white       = tft.color565(255, 255, 255);
    darkBrown   = tft.color565(60, 40, 10);

    drawHappyFace();  // start happy
    currentMode = HAPPY;
}

void loop() {
    static unsigned long lastSwitch = 0;
    unsigned long now = millis();

    // TODO: Future ESP32 communication feature
    // When ESP32 detects action -> switch to ANGRY mode immediately
    // When idle for 10 seconds -> switch to HAPPY mode
    // For now: Switch every 10s for testing
    
    // Switch every 10s for now
    if (now - lastSwitch > 10000) {
        if (currentMode == HAPPY) {
            drawAngryFace();
            currentMode = ANGRY;
        } else {
            drawHappyFace();
            currentMode = HAPPY;
        }
        lastSwitch = now;
    }
}

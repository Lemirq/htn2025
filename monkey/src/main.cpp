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

// Animation variables
unsigned long lastBlink = 0;
bool eyesOpen = true;

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

void drawEyes(bool open) {
    int cx = TFT_WIDTH / 2;
    int cy = TFT_HEIGHT / 2;

    if (open) {
        // Open eyes - draw over the eye area only
        tft.fillCircle(cx - 35, cy - 20, 22, white);
        tft.fillCircle(cx + 35, cy - 20, 22, white);
        tft.fillCircle(cx - 35, cy - 20, 12, black);
        tft.fillCircle(cx + 35, cy - 20, 12, black);
        // highlights
        tft.fillCircle(cx - 31, cy - 24, 4, white);
        tft.fillCircle(cx + 39, cy - 24, 4, white);
    } else {
        // Closed eyes - just cover the eye area with closed eyes
        // First cover the old eyes with face color
        tft.fillCircle(cx - 35, cy - 20, 25, monkeyTan);
        tft.fillCircle(cx + 35, cy - 20, 25, monkeyTan);
        // Then draw closed eye lines
        tft.fillRect(cx - 45, cy - 22, 20, 4, darkBrown);
        tft.fillRect(cx + 25, cy - 22, 20, 4, darkBrown);
    }
}

void drawHappyFace() {
    int cx = TFT_WIDTH / 2;
    int cy = TFT_HEIGHT / 2;

    tft.fillScreen(white);
    drawMonkeyBase(cx, cy);

    // Draw initial open eyes
    drawEyes(true);

    // Nose (small oval in muzzle)
    tft.fillCircle(cx - 6, cy + 10, 4, black);
    tft.fillCircle(cx + 6, cy + 10, 4, black);

    // Static smile for now
    for (int i = 0; i < 180; i++) {
        int x = cx + cos(radians(i)) * 35;
        int y = cy + sin(radians(i)) * 20 + 35;
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

    // Initialize animation timers
    lastBlink = millis();
    
    drawHappyFace();  // show happy monkey
}

void loop() {
    unsigned long now = millis();

    // Simple blinking animation - blink every 2 seconds
    if (now - lastBlink > 2000) {
        if (eyesOpen) {
            eyesOpen = false;
            lastBlink = now;
            drawEyes(false); // Just update eyes, not whole face
        } else if (now - lastBlink > 200) { // Eyes closed for 200ms
            eyesOpen = true;
            lastBlink = now;
            drawEyes(true); // Just update eyes, not whole face
        }
    }

    // Small delay
    delay(50);
}

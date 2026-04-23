#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <vector>

// ═══════════════════════════════════════════════════
//  SONG CACHE STRUCT
// ═══════════════════════════════════════════════════
struct SongEntry {
  String code;
  String uri;
  String name;
  String artist;
  bool   isPlaylist;
};
std::vector<SongEntry> songCache;

// ═══════════════════════════════════════════════════
//  CONFIG
// ═══════════════════════════════════════════════════
const char* WIFI_SSID     = "donut shop mini";
const char* WIFI_PASS     = "hardpass";
const char* API_BASE      = "http://192.168.1.35:8080";
const char* API_KEY       = "test-api-key";

const int NORMAL_VOLUME  = 100;
const int DIAL_VOLUME    = 20;
const int DIAL_TIMEOUT   = 2000;
const int POLL_INTERVAL  = 3000;
const int CACHE_INTERVAL = 600000;

// ═══════════════════════════════════════════════════
//  PIN MAP  (telephone board pin → ESP32 GPIO)
// ═══════════════════════════════════════════════════
int pinToGPIO[] = {
  -1,  // 0  unused
  13,  // 1
  14,  // 2
  27,  // 3
  18,  // 4
  26,  // 5
  -1,  // 6  unused
  19,  // 7
  -1,  // 8  unused
  -1,  // 9  unused
  25,  // 10
  23,  // 11
  32,  // 12
  33   // 13
};

// ═══════════════════════════════════════════════════
//  BUTTON DEFINITIONS
// ═══════════════════════════════════════════════════
struct Button {
  const char* name;
  int a;   // telephone board pin driven LOW
  int b;   // telephone board pin read
};

Button buttons[] = {
  {"1",      3, 13},
  {"2",      2, 13},
  {"3",      1, 13},
  {"4",      3, 12},
  {"5",      2, 12},
  {"6",      1, 12},
  {"7",      3, 11},
  {"8",      2, 11},
  {"9",      1, 11},
  {"*",      3, 10},
  {"0",      2, 10},
  {"#",      1, 10},
  {"VOL",    7,  5},
  {"REDIAL", 5, 12},
  {"UP",     4, 13},
  {"DOWN",   4, 12},
};
const int NUM_BTNS = sizeof(buttons) / sizeof(buttons[0]);

bool lastState[20] = {false};

// ═══════════════════════════════════════════════════
//  HOOK SWITCH  (GPIO 12, NO switch → GND)
// ═══════════════════════════════════════════════════
const int HOOK_PIN = 12;

bool isHandsetLifted() {
  return (digitalRead(HOOK_PIN) == LOW);
}

// ═══════════════════════════════════════════════════
//  PAIRWISE PRESS DETECTION
// ═══════════════════════════════════════════════════
bool isPressed(Button& btn) {
  int pinA = pinToGPIO[btn.a];
  int pinB = pinToGPIO[btn.b];
  if (pinA == -1 || pinB == -1) return false;

  pinMode(pinA, OUTPUT);
  digitalWrite(pinA, LOW);
  pinMode(pinB, INPUT_PULLUP);
  delayMicroseconds(5);
  bool pressed = (digitalRead(pinB) == LOW);
  pinMode(pinA, INPUT_PULLUP);   // restore
  return pressed;
}

// Scans all buttons, returns the name of first newly-pressed one or nullptr
const char* scanButtons() {
  for (int i = 0; i < NUM_BTNS; i++) {
    bool state = isPressed(buttons[i]);
    bool fresh = (state && !lastState[i]);
    lastState[i] = state;
    if (fresh) return buttons[i].name;
  }
  return nullptr;
}

// ═══════════════════════════════════════════════════
//  APP STATE
// ═══════════════════════════════════════════════════
enum AppState { IDLE, DIALING };
AppState appState = IDLE;

String inputBuffer  = "";
bool   playlistMode = false;

unsigned long lastKeyTime   = 0;
unsigned long lastPollTime  = 0;
unsigned long lastCacheTime = 0;

String currentSong   = "--";
String currentArtist = "--";

bool prevHandset = false;




// ═══════════════════════════════════════════════════
//  SERVER PROXY CONTROLS
// ═══════════════════════════════════════════════════
void postApi(const String& endpoint, const String& payload = "") {
  HTTPClient h;
  h.begin(String(API_BASE) + endpoint);
  h.addHeader("X-API-Key", API_KEY);
  if (payload.length() > 0) {
    h.addHeader("Content-Type", "application/json");
  }
  h.POST(payload);
  h.end();
}

void playSong(const String& uri)     { postApi("/api/player/play", "{\"uri\":\"" + uri + "\", \"is_playlist\": false}"); }
void playPlaylist(const String& uri) { postApi("/api/player/play", "{\"uri\":\"" + uri + "\", \"is_playlist\": true}"); }
void setVolume(int v)                { postApi("/api/player/volume?percent=" + String(v)); }
void nextTrack()                     { postApi("/api/player/next"); }
void prevTrack()                     { postApi("/api/player/previous"); }
void restartTrack()                  { postApi("/api/player/restart"); }

void pollNowPlaying() {
  HTTPClient h;
  h.begin(String(API_BASE) + "/api/player/now-playing");
  h.addHeader("X-API-Key", API_KEY);
  if (h.GET() == 200) {
    DynamicJsonDocument doc(1024);
    deserializeJson(doc, h.getString());
    currentSong   = doc["song_name"].as<String>();
    currentArtist = doc["artist"].as<String>();
  }
  h.end();
}

// ═══════════════════════════════════════════════════
//  WEB APP CACHE
// ═══════════════════════════════════════════════════
void fetchCache() {
  HTTPClient h;
  h.begin(String(API_BASE) + "/api/songs");
  h.addHeader("X-API-Key", API_KEY);
  if (h.GET() == 200) {
    DynamicJsonDocument doc(8192);
    deserializeJson(doc, h.getString());
    songCache.clear();
    for (JsonObject o : doc.as<JsonArray>()) {
      songCache.push_back({
        o["dial_code"].as<String>(),
        o["spotify_uri"].as<String>(),
        o["song_name"].as<String>(),
        o["artist"].as<String>(),
        o["is_playlist"].as<bool>()
      });
    }
  }
  h.end();
  lastCacheTime = millis();
}

SongEntry* findEntry(const String& code, bool isPlaylist) {
  for (auto& e : songCache)
    if (e.code == code && e.isPlaylist == isPlaylist) return &e;
  return nullptr;
}

// ═══════════════════════════════════════════════════
//  LCD
// ═══════════════════════════════════════════════════
LiquidCrystal_I2C lcd(0x27, 16, 2);

void showIdle() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(currentSong.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(currentArtist.substring(0, 16));
}

void showDialing() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(playlistMode ? "Playlist: *" : "Song code:");
  lcd.setCursor(0, 1);
  lcd.print(inputBuffer.length() ? inputBuffer : "_");
}

// ═══════════════════════════════════════════════════
//  STATE TRANSITIONS
// ═══════════════════════════════════════════════════
void enterDialing() {
  appState     = DIALING;
  inputBuffer  = "";
  playlistMode = false;
  lastKeyTime  = millis();
  setVolume(DIAL_VOLUME);
  showDialing();
}

void enterIdle() {
  appState     = IDLE;
  inputBuffer  = "";
  playlistMode = false;
  setVolume(NORMAL_VOLUME);
  showIdle();
}

void confirmDial() {
  if (inputBuffer.length() == 0) { enterIdle(); return; }

  lcd.clear();
  lcd.print("Looking up...");

  SongEntry* e = findEntry(inputBuffer, playlistMode);

  // If not found in local memory, try refreshing from the server once
  if (!e) {
    fetchCache(); 
    e = findEntry(inputBuffer, playlistMode);
  }

  if (e) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(playlistMode ? "Playlist:" : "Playing:");
    lcd.setCursor(0, 1);
    lcd.print(e->name.substring(0, 16));

    if (playlistMode) playPlaylist(e->uri);
    else              playSong(e->uri);

    currentSong   = e->name;
    currentArtist = e->artist;
    delay(1500);
  } else {
    lcd.clear();
    lcd.print("Not found:");
    lcd.setCursor(0, 1);
    lcd.print((playlistMode ? "*" : "") + inputBuffer);
    delay(2000);
  }
  enterIdle();
}

// ═══════════════════════════════════════════════════
//  DIAL KEY HANDLER
// ═══════════════════════════════════════════════════
void handleDialKey(const char* key) {
  lastKeyTime = millis();

  if (strcmp(key, "#") == 0) { confirmDial(); return; }

  if (strcmp(key, "*") == 0) {
    if (inputBuffer.length() == 0) {   // * only switches mode at the start
      playlistMode = true;
      showDialing();
    }
    return;
  }

  // Digit keys 0–9
  if (strlen(key) == 1 && key[0] >= '0' && key[0] <= '9') {
    if (inputBuffer.length() < 6) {
      inputBuffer += key[0];
      showDialing();
    }
  }
}

// ═══════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);

  // All telephone pins start as INPUT_PULLUP
  // isPressed() will temporarily flip one to OUTPUT as needed
  for (int i = 1; i <= 13; i++) {
    if (pinToGPIO[i] != -1)
      pinMode(pinToGPIO[i], INPUT_PULLUP);
  }

  pinMode(HOOK_PIN, INPUT_PULLUP);

  Wire.begin(21, 22);
  lcd.begin();
  lcd.backlight();

  lcd.print("Connecting WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(500);

  lcd.clear(); lcd.print("Fetching songs..");
  fetchCache();

  pollNowPlaying();
  showIdle();
}

// ═══════════════════════════════════════════════════
//  LOOP
// ═══════════════════════════════════════════════════
void loop() {

  // ── 1. Hook switch ──────────────────────────────
  bool handsetUp = isHandsetLifted();
  if (handsetUp != prevHandset) {
    prevHandset = handsetUp;
    if  (handsetUp && appState == IDLE)    enterDialing();
    if (!handsetUp && appState == DIALING) enterIdle();  // replaced mid-dial = cancel
  }

  // ── 2. Button scan ──────────────────────────────
  const char* key = scanButtons();
  if (key) {
    if (appState == DIALING) {
      handleDialKey(key);
    } else {
      // IDLE — navigation controls always active
      if      (strcmp(key, "UP")     == 0) { nextTrack();    lcd.clear(); lcd.print("Next >>"); delay(400); pollNowPlaying(); showIdle(); }
      else if (strcmp(key, "DOWN")   == 0) { prevTrack();    lcd.clear(); lcd.print("<< Prev"); delay(400); pollNowPlaying(); showIdle(); }
      else if (strcmp(key, "REDIAL") == 0) { restartTrack(); lcd.clear(); lcd.print("Restarting..."); delay(800); showIdle(); }
    }
  }

  // ── 3. Dial timeout: 2s silence → auto confirm ──
  if (appState == DIALING && inputBuffer.length() > 0) {
    if (millis() - lastKeyTime > DIAL_TIMEOUT) confirmDial();
  }

  // ── 4. Poll now-playing every 3s (idle only) ────
  if (appState == IDLE && millis() - lastPollTime > POLL_INTERVAL) {
    lastPollTime = millis();
    pollNowPlaying();
    showIdle();
  }

  // ── 5. Refresh song cache every 10 min ──────────
  if (millis() - lastCacheTime > CACHE_INTERVAL) fetchCache();

  delay(50);  // matches your working test sketch's debounce timing
}
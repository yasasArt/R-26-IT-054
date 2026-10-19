/*
  GarmentCounterIoT - ESP32-C3 SuperMini BLE button firmware

  Board: ESP32-C3 SuperMini
  Buttons:
    A short press : start/restart BLE advertising / send CONNECT_REQUEST if connected
    A long press  : shutdown request + deep sleep
    B             : REWORK mode event
    C             : DOWNTIME mode event
    D             : RESET event

  Built-in LED: GPIO 8

  Required Arduino library:
    NimBLE-Arduino by h2zero

  BLE device name:
    GarmentCounter-IoT
*/

#include <Arduino.h>
#include <NimBLEDevice.h>
#include "esp_sleep.h"
#include "esp_idf_version.h"

// ------------------------- Pin configuration -------------------------
// Change these pins if your wiring is different.
static const uint8_t BUTTON_A_PIN = 2;
static const uint8_t BUTTON_B_PIN = 3;
static const uint8_t BUTTON_C_PIN = 4;
static const uint8_t BUTTON_D_PIN = 5;
static const uint8_t LED_PIN      = 8;

// Most ESP32-C3 SuperMini onboard LEDs are active LOW.
// If your LED works opposite, change this to false.
static const bool LED_ACTIVE_LOW = true;

// Optional hardware power latch OFF pin.
// Keep as -1 if you only use deep sleep.
static const int POWER_LATCH_OFF_PIN = -1;

// ------------------------- BLE configuration -------------------------
static const char* DEVICE_NAME = "GarmentCounter-IoT";
static const char* FIRMWARE_VERSION = "0.4.2";
static const char* SERVICE_UUID = "7d2ea28a-f7bd-485a-bd9d-92ad6ecfe93e";
static const char* EVENT_CHAR_UUID = "8f42b2f3-6d57-4f8b-8b66-7b6dfc3dd98a";

NimBLEServer* bleServer = nullptr;
NimBLECharacteristic* eventCharacteristic = nullptr;
volatile bool bleConnected = false;

// ------------------------- Timing constants -------------------------
static const uint32_t DEBOUNCE_MS = 35;
static const uint32_t BUTTON_A_LONG_PRESS_MS = 2200;
static const uint32_t ADVERTISING_WINDOW_MS = 60000;

uint32_t advertisingStartedAt = 0;
bool advertisingActive = false;

// ------------------------- Device mode -------------------------
enum class DeviceMode {
  BOOT,
  ADVERTISING,
  NORMAL,
  REWORK,
  DOWNTIME,
  RESET_ACK,
  SHUTDOWN
};

DeviceMode currentMode = DeviceMode::BOOT;
DeviceMode modeAfterAck = DeviceMode::NORMAL;
uint32_t modeStartedAt = 0;

// ------------------------- Button helper -------------------------
struct Button {
  uint8_t pin;
  bool stableState;       // HIGH = released, LOW = pressed when using INPUT_PULLUP
  bool lastReading;
  uint32_t lastChangeMs;
  uint32_t pressedAtMs;
  bool longFired;
};

Button buttonA{BUTTON_A_PIN, HIGH, HIGH, 0, 0, false};
Button buttonB{BUTTON_B_PIN, HIGH, HIGH, 0, 0, false};
Button buttonC{BUTTON_C_PIN, HIGH, HIGH, 0, 0, false};
Button buttonD{BUTTON_D_PIN, HIGH, HIGH, 0, 0, false};

// ------------------------- LED helper -------------------------
void setLed(bool on) {
  if (LED_ACTIVE_LOW) {
    digitalWrite(LED_PIN, on ? LOW : HIGH);
  } else {
    digitalWrite(LED_PIN, on ? HIGH : LOW);
  }
}

void setMode(DeviceMode mode) {
  currentMode = mode;
  modeStartedAt = millis();
}

void updateLedPattern() {
  const uint32_t now = millis();
  const uint32_t t = now - modeStartedAt;

  switch (currentMode) {
    case DeviceMode::BOOT:
      // 3 quick blinks, then move to advertising/normal.
      if (t < 900) {
        setLed((t / 120) % 2 == 0);
      } else {
        setMode(bleConnected ? DeviceMode::NORMAL : DeviceMode::ADVERTISING);
      }
      break;

    case DeviceMode::ADVERTISING:
      // Fast blink while waiting for software connection.
      setLed((now / 180) % 2 == 0);
      break;

    case DeviceMode::NORMAL:
      // Professional heartbeat: tiny blink every 3 seconds.
      setLed((now % 3000) < 90);
      break;

    case DeviceMode::REWORK:
      // Double blink every second.
      setLed((t % 1000 < 100) || (t % 1000 >= 220 && t % 1000 < 320));
      break;

    case DeviceMode::DOWNTIME:
      // Long warning blink every second.
      setLed((t % 1000) < 600);
      break;

    case DeviceMode::RESET_ACK:
      // One long confirmation blink, then return to normal.
      if (t < 700) {
        setLed(true);
      } else {
        setLed(false);
        setMode(modeAfterAck);
      }
      break;

    case DeviceMode::SHUTDOWN:
      // Slow shutdown pulse pattern before deep sleep.
      setLed((now / 400) % 2 == 0);
      break;
  }
}

// ------------------------- BLE callbacks -------------------------
class ServerCallbacks : public NimBLEServerCallbacks {
  void handleConnect() {
    bleConnected = true;
    advertisingActive = false;
    setMode(DeviceMode::RESET_ACK); // short success indication
    modeAfterAck = DeviceMode::NORMAL;
  }

  void handleDisconnect() {
    bleConnected = false;
    setMode(DeviceMode::ADVERTISING);
    NimBLEDevice::startAdvertising();
    advertisingStartedAt = millis();
    advertisingActive = true;
  }

  // NimBLE-Arduino v2.x callback signatures.
  // Your compile error happened because v2.x no longer uses
  // onConnect(NimBLEServer*) / onDisconnect(NimBLEServer*) as override methods.
  void onConnect(NimBLEServer* server, NimBLEConnInfo& connInfo) override {
    (void)server;
    (void)connInfo;
    handleConnect();
  }

  void onDisconnect(NimBLEServer* server, NimBLEConnInfo& connInfo, int reason) override {
    (void)server;
    (void)connInfo;
    (void)reason;
    handleDisconnect();
  }
};

void sendEvent(const char* eventName) {
  Serial.print("IoT event: ");
  Serial.println(eventName);

  if (eventCharacteristic != nullptr && bleConnected) {
    eventCharacteristic->setValue((uint8_t*)eventName, strlen(eventName));
    eventCharacteristic->notify();
  }
}

void startAdvertisingWindow() {
  NimBLEDevice::startAdvertising();
  advertisingStartedAt = millis();
  advertisingActive = true;
  setMode(DeviceMode::ADVERTISING);
  Serial.println("BLE advertising started/restarted.");
}

void setupBle() {
  NimBLEDevice::init(DEVICE_NAME);
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);

  bleServer = NimBLEDevice::createServer();
  bleServer->setCallbacks(new ServerCallbacks());

  NimBLEService* service = bleServer->createService(SERVICE_UUID);

  eventCharacteristic = service->createCharacteristic(
    EVENT_CHAR_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
  );
  eventCharacteristic->setValue("READY");

  service->start();

  NimBLEAdvertising* advertising = NimBLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  // A 128-bit service UUID and the full device name do not both fit reliably
  // in the 31-byte legacy advertising packet. NimBLE-Arduino v2 disables scan
  // response by default, so explicitly enable it before adding the name. This
  // lets Electron/macOS display "GarmentCounter-IoT" in the device picker.
  advertising->enableScanResponse(true);
  advertising->setName(DEVICE_NAME);
  advertising->start();

  advertisingStartedAt = millis();
  advertisingActive = true;
}

// ------------------------- Power / sleep -------------------------
void enterDeepSleep() {
  sendEvent("SHUTDOWN");
  setMode(DeviceMode::SHUTDOWN);

  const uint32_t started = millis();
  while (millis() - started < 2000) {
    updateLedPattern();
    delay(10);
  }

  setLed(false);
  delay(100);

  if (POWER_LATCH_OFF_PIN >= 0) {
    pinMode(POWER_LATCH_OFF_PIN, OUTPUT);
    digitalWrite(POWER_LATCH_OFF_PIN, LOW);
    delay(500);
  }

  // Wake when Button A is held/pressed LOW.
  // Arduino-ESP32 v3 uses ESP-IDF v5 APIs; older versions may use EXT0.
#if ESP_IDF_VERSION_MAJOR >= 5
  esp_deep_sleep_enable_gpio_wakeup((1ULL << BUTTON_A_PIN), ESP_GPIO_WAKEUP_GPIO_LOW);
#else
  esp_sleep_enable_ext0_wakeup((gpio_num_t)BUTTON_A_PIN, 0);
#endif

  Serial.println("Entering deep sleep. Press Button A to wake.");
  Serial.flush();
  esp_deep_sleep_start();
}

// ------------------------- Button logic -------------------------
void handleShortPress(uint8_t pin) {
  if (pin == BUTTON_A_PIN) {
    if (bleConnected) {
      sendEvent("CONNECT_REQUEST");
      setMode(DeviceMode::RESET_ACK);
      modeAfterAck = DeviceMode::NORMAL;
    } else {
      startAdvertisingWindow();
    }
    return;
  }

  if (pin == BUTTON_B_PIN) {
    sendEvent("REWORK");
    setMode(DeviceMode::REWORK);
    return;
  }

  if (pin == BUTTON_C_PIN) {
    sendEvent("DOWNTIME");
    setMode(DeviceMode::DOWNTIME);
    return;
  }

  if (pin == BUTTON_D_PIN) {
    sendEvent("RESET");
    modeAfterAck = bleConnected ? DeviceMode::NORMAL : DeviceMode::ADVERTISING;
    setMode(DeviceMode::RESET_ACK);
    return;
  }
}

void updateButton(Button& button) {
  const uint32_t now = millis();
  bool reading = digitalRead(button.pin);

  if (reading != button.lastReading) {
    button.lastChangeMs = now;
    button.lastReading = reading;
  }

  if ((now - button.lastChangeMs) > DEBOUNCE_MS && reading != button.stableState) {
    button.stableState = reading;

    if (button.stableState == LOW) {
      button.pressedAtMs = now;
      button.longFired = false;
    } else {
      uint32_t pressDuration = now - button.pressedAtMs;
      if (!button.longFired && pressDuration < BUTTON_A_LONG_PRESS_MS) {
        handleShortPress(button.pin);
      }
    }
  }

  // Fire Button A long press while still holding, not after release.
  if (button.pin == BUTTON_A_PIN && button.stableState == LOW && !button.longFired) {
    if ((now - button.pressedAtMs) >= BUTTON_A_LONG_PRESS_MS) {
      button.longFired = true;
      enterDeepSleep();
    }
  }
}

void setupButtons() {
  pinMode(BUTTON_A_PIN, INPUT_PULLUP);
  pinMode(BUTTON_B_PIN, INPUT_PULLUP);
  pinMode(BUTTON_C_PIN, INPUT_PULLUP);
  pinMode(BUTTON_D_PIN, INPUT_PULLUP);

  buttonA.stableState = buttonA.lastReading = digitalRead(BUTTON_A_PIN);
  buttonB.stableState = buttonB.lastReading = digitalRead(BUTTON_B_PIN);
  buttonC.stableState = buttonC.lastReading = digitalRead(BUTTON_C_PIN);
  buttonD.stableState = buttonD.lastReading = digitalRead(BUTTON_D_PIN);
}

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(LED_PIN, OUTPUT);
  setLed(false);

  setupButtons();
  setupBle();

  Serial.println("GarmentCounter-IoT firmware started.");
  Serial.println("BLE name: GarmentCounter-IoT");
  Serial.print("Firmware version: ");
  Serial.println(FIRMWARE_VERSION);

  setMode(DeviceMode::BOOT);
}

void loop() {
  updateButton(buttonA);
  updateButton(buttonB);
  updateButton(buttonC);
  updateButton(buttonD);

  if (advertisingActive && !bleConnected) {
    if (millis() - advertisingStartedAt > ADVERTISING_WINDOW_MS) {
      // Keep advertising stopped after the window to save battery.
      // Button A short press restarts advertising.
      NimBLEDevice::stopAdvertising();
      advertisingActive = false;
      setMode(DeviceMode::NORMAL); // idle heartbeat while not connected
      Serial.println("BLE advertising stopped to save battery.");
    }
  }

  if (!bleConnected && advertisingActive && currentMode != DeviceMode::ADVERTISING) {
    setMode(DeviceMode::ADVERTISING);
  }

  updateLedPattern();
  delay(5);
}

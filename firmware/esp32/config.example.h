#pragma once
// Copy to config.h. Do not commit personal credentials.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define MQTT_HOST "192.168.1.100" // Laptop LAN IPv4 address, never localhost
#define MQTT_PORT 1883
#define MQTT_USER ""
#define MQTT_PASSWORD ""
#define DEVICE_ID "device01"
#define TOPIC_PREFIX "home"
// Classic ESP32-WROOM DevKit only. Verify your exact board before wiring.
#define DHT_PIN 4
#define PIR_PIN 27
#define DOOR_PIN 26
#define GAS_PIN 34
#define BUZZER_PIN 25
#define GREEN_LED 18
#define YELLOW_LED 19
#define RED_LED 23
#define TELEMETRY_MS 2500UL
#define PIR_WARMUP_MS 60000UL
#define GAS_WARMUP_MS 180000UL
// Set true ONLY after sensor conditioning and baseline calibration.
// Manufacturer initial conditioning is at least 48 h; 180 s is not a substitute.
#define GAS_CONDITIONED false
#define TEMPERATURE_HIGH 35.0f
#define TEMPERATURE_CLEAR 33.0f
#define GAS_HIGH 2000.0f
#define GAS_CLEAR 1600.0f
#define CONFIRM_SAMPLES 3
// These are demonstration thresholds. gas is raw ADC, not ppm.

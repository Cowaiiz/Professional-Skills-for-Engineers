# ESP32 firmware and wiring

## Status and assumptions

Source targets classic ESP32-WROOM DevKit, Arduino-ESP32 2.x through PlatformIO espressif32 6.12.0. Full firmware build and hardware operation are **not verified**. Host C++ tests cover only the threshold/debounce rules. The DHT22 timing driver is included; validate its readings against a reference and expect invalid samples during timing interference.

## Pin map

Disconnect power while wiring. All circuits share GND. GPIOs are 3.3 V signals.

| Component | Connection | Notes |
|---|---|---|
| DHT22 | DATA -> GPIO4; VCC -> 3.3 V; GND -> GND | Add 4.7–10 kohm DATA-to-3.3 V pull-up unless module already includes it; verify package pin order |
| PIR HC-SR501 | OUT -> GPIO27; VCC -> suitable 5 V; GND | Verify OUT is 3.3 V before connection; allow 60 seconds startup settling |
| Reed switch | GPIO26 to GND through contact | INPUT_PULLUP; magnet closes contact: closed=LOW, open=HIGH. Requires magnet |
| MQ-2 module | VCC -> 5 V; GND; AO -> divider -> GPIO34 | ADC1 works with Wi-Fi. Leave DO unused; NEVER connect 5 V AO directly to GPIO |
| Active buzzer | Controlled by GPIO25 through driver | Active buzzer sounds on DC. Passive buzzer needs a tone/PWM implementation instead |
| Green LED | GPIO18 -> 330 ohm -> anode; cathode GND | Online, sensors ready, no active environment alert |
| Yellow LED | GPIO19 -> 330 ohm -> anode; cathode GND | Network disconnected or sensor not ready/fault |
| Red LED | GPIO23 -> 330 ohm -> anode; cathode GND | Temperature/gas alert active |

**MQ-2 divider:** AO -> 10 kohm -> junction GPIO34 -> 15 kohm -> GND. An ideal 5.0 V AO becomes 3.0 V. Verify resistor values, supply and measured maximum junction voltage before connecting. Readings remain raw ADC units; this is not a calibrated ppm measurement.

**Buzzer driver:** GPIO25 -> 1 kohm -> NPN base; 10 kohm base-to-GND pull-down; emitter GND; collector buzzer negative; buzzer positive to its rated supply. Select transistor for buzzer current. For an inductive buzzer add a flyback diode across it (cathode at positive). A suitable driver module is an alternative. Do not power an unknown buzzer directly from a GPIO.

The original list therefore needs a reed magnet, confirmed divider/pull-up/LED resistors, and a buzzer driver (plus diode if needed). An adequate regulated USB supply is needed for ESP32 radio and MQ-2 heater. Verify the DevKit's 5 V pin/power path; avoid backfeeding from two supplies.

## Mosquitto on the laptop

Install Mosquitto from https://mosquitto.org/download/ . Do not start the included demo broker at the same time.

From the project root in PowerShell:

```powershell
& 'C:\Program Files\mosquitto\mosquitto_passwd.exe' -c broker\passwords labuser
Copy-Item broker\mosquitto-lan.example.conf broker\mosquitto-lan.conf
notepad broker\mosquitto-lan.conf
```

Replace the example `password_file` with the actual absolute path to `broker/passwords`. Then:

```powershell
& 'C:\Program Files\mosquitto\mosquitto.exe' -c broker\mosquitto-lan.conf -v
```

Use this only on a trusted private LAN. If necessary, allow inbound TCP1883 for Mosquitto on the Windows **Private** network profile. No firewall changes are made by this project. MQTT1883 is not encrypted; do not forward it through the router. Set matching username/password in `config.local.json` and firmware `config.h`. A shared demo account is sufficient for a single node; per-device ACLs are future work.

## Build and upload

1. Copy `config.example.h` to `config.h` and set Wi-Fi name/password, MQTT host (laptop LAN IPv4), MQTT credentials. Keep the default device ID `device01`.
2. Keep `GAS_CONDITIONED false` initially. The manufacturer specifies at least 48 hours initial preheating under its test conditions. Follow the sensor documentation, record a stable baseline, choose a demonstration raw threshold, then explicitly set it true. The additional 180-second boot delay is not a substitute for initial conditioning.
3. In VS Code with PlatformIO, open this `firmware/esp32` folder. Build/upload and monitor at 115200 baud:

```powershell
pio run
pio run --target upload
pio device monitor --baud 115200
```

Arduino IDE alternative: open `esp32.ino` in this folder, select **ESP32 Dev Module** and the correct COM port. `esp32.ino` is an empty sketch entry; `main.cpp` contains `setup()` and `loop()` and is compiled alongside it. Keep all files in this folder together.

4. Stop the simulator. Run `python -m backend.app` from the project root; open the dashboard. Confirm **ESP32 HARDWARE** and fresh telemetry before claiming a hardware demo.
5. Test each sensor separately, then unplug Wi-Fi/broker while checking the local red LED/buzzer logic. Test gas alerts with simulated readings, not released fuel or open flames.

## Firmware behavior

Sensors sample every 2.5 seconds. Digital contacts are debounced for 50 ms. Three consecutive high valid samples activate temperature/gas alarms. Three samples below the lower clear threshold clear them. Invalid values do not clear an existing alert. Local buzzer/red LED use these rules independently of networking, which runs in a separate FreeRTOS task. Both thresholds must be synchronized manually between `config.h` and backend JSON if changed.

MQTT reconnects after Wi-Fi recovery; the last will reports offline. Latest telemetry is sent QoS0, not retained. There is no guaranteed offline replay. Diagnostic edge events have a bounded 16-entry queue; overflow drops the oldest. The backend derives canonical events from telemetry, so fast pulses between samples and events during outages may not appear in dashboard history. Motion/door changes are informational events, not an armed intrusion alarm. No remote buzzer silence or arming control is implemented.

References: [ESP32 ADC](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html), [MQ-2 manufacturer](https://www.winsen-sensor.com/product/mq-2.html), [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/).

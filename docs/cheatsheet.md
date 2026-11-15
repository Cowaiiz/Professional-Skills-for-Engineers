# Project Cheat Sheet — CC02 Group 8

**What it does:** monitors temperature, humidity, relative gas response, motion and door state. It records transitions and environmental alerts. It is a student monitoring prototype, not a certified fire alarm or intrusion classifier.

**Architecture:** sensors feed ESP32; ESP32 uses Wi-Fi/MQTT to a laptop broker. Python validates data and evaluates rules, SQLite preserves history, and the browser polls a local HTTP API. The simulator replaces the ESP32 during software demonstrations and is visibly labeled.

**Components:** DHT22 measures temperature/humidity; MQ-2 supplies an analog relative gas response; PIR detects movement; reed contact indicates door position. ESP32 reads inputs and operates buzzer/LEDs. Broker routes messages; backend gives them meaning; database remembers them; dashboard displays them.

**Data path:** sample -> JSON with device/boot/sequence -> telemetry topic -> validation/deduplication -> transaction storing reading/events/alerts -> HTTP response -> cards/charts. Server receipt time establishes freshness. Node `timestamp` may be null.

**Why ESP32:** enough GPIO/ADC for this small node, built-in Wi-Fi, low cost, local control without a Linux computer. Raspberry Pi is unnecessary for these tasks. The laptop handles history and the dashboard.

**MQTT versus HTTP:** MQTT is publish/subscribe between node, broker and backend. HTTP is request/response between browser and backend. Topics identify message streams. QoS0 has low complexity but no delivery guarantee.

**Abnormal detection:** three consecutive values above35 C or raw gas2000 activate; three below33 C or1600 clear. Hysteresis prevents toggling near one threshold. Two stable telemetry samples confirm motion/door transitions. Silence longer than20 seconds marks offline. Null readings mean faults, never “normal zero.” Gas warmup disables gas evaluation. These thresholds are demonstration choices.

## Lecturer questions and suggested answers

1. **What is the main problem?** Giving a user one place to see room conditions, recent changes and abnormal readings from a low-cost node.
2. **Why ESP32 rather than Raspberry Pi?** It already provides Wi-Fi, GPIO and ADC for this workload; a full operating system adds cost and complexity.
3. **Why MQTT?** It separates producers and consumers through topics, supports lightweight persistent connections and last-will presence messages.
4. **What does the broker do?** Routes messages. It does not know whether35 C is abnormal; our backend and local firmware implement that rule.
5. **What happens without Wi-Fi?** Local sampling and buzzer logic continue by design; remote history stops and the dashboard becomes offline. Hardware verification remains required.
6. **How do you avoid repeated alerts?** Persist active state, use consecutive samples and separate activate/clear thresholds. Generate events only on transitions.
7. **What is hysteresis?** Use one threshold to enter an alert and a lower one to leave it, reducing rapid oscillation near the boundary.
8. **Is MQ-2 output ppm?** No. We display raw ADC values after voltage division. Accurate concentration needs calibration, sensor characterization and environmental compensation.
9. **How do you protect ESP32 inputs?** Use3.3 V logic, a divider for potentially5 V MQ analog output, and a driver for an unknown buzzer load.
10. **What is an MQTT last will?** A message the broker publishes when it detects an unexpected client disconnect. A separate telemetry timeout also detects a connected but silent node.
11. **Does acknowledgement stop an alarm?** No. It records that the operator saw it. Only recovery below the clear threshold clears the condition.
12. **How do you handle repeated packets/reboots?** Device ID plus boot ID plus sequence identifies samples; duplicates/late samples do not refresh heartbeat. A new boot starts a new sequence.
13. **Can brief door pulses be missed?** Yes. Canonical events use periodic snapshots; fast edges may be visible only in firmware diagnostic topics. Guaranteed edge delivery is future work.
14. **What has actually been tested?** The Windows run passed 30 Python tests and the portable C++ rule checks. The Edge demo verified live data, alerts, acknowledgement and broker recovery. The full board build and hardware checks remain pending.
15. **What would you improve next?** Validate real hardware first, then use a maintained MQTT SDK, add authenticated/TLS deployment, bounded history retention and reliable event replay if requirements justify them.

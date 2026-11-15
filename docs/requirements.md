# Requirements and implementation traceability

Source: latest user-supplied implementation text plus hardware list. These are project requirements, not independently verified grading requirements. Home IoT Monitoring & Alert System is a student prototype for one home living room.

| ID | Requirement | Implementation | Verification state |
|---|---|---|---|
| FR01 | Acquire temperature/humidity, gas, motion, door | `firmware/esp32/main.cpp` | Source written; hardware pending |
| FR02 | Send structured JSON over Wi-Fi/MQTT | Firmware and `common/mqtt.py` | Simulator MQTT verified. ESP32 Wi-Fi pending. |
| FR03 | Validate and store telemetry | `common/protocol.py`, `backend/store.py` | Unit tests passed |
| FR04 | Threshold alerts with suppression | Backend engine and firmware rules | Python + portable C++ tests passed |
| FR05 | Motion/door events | Backend snapshot debounce; firmware contact debounce | Rule tests passed; physical timing pending |
| FR06 | Online/offline/reconnection | Timeout, boot ID, last will, MQTT retry | State and broker-restart checks passed |
| FR07 | Dashboard values, trends and events | `dashboard/` and HTTP API | Edge and live HTTP API verified |
| FR08 | Persistent alert acknowledgement | SQLite/API/dashboard | Browser acknowledgement and restart verified |
| FR09 | Simulate required scenarios without ESP32 | `simulator/` | Combined and normal published in Windows demo |
| FR11 | Replay a simulated camera entry and possible fall | `dashboard/camera-demo.js` | Edge replay verified |
| FR12 | Notify a linked Telegram chat for high gas or node offline | SQLite queue and `backend/telegram.py` | Preview verified and transport mocked |
| FR10 | Local buzzer and three LEDs | Firmware with independent network task | Hardware pending |

NFR01: Python3.11+, no external Python packages for software demo. NFR02: 2.5-second telemetry and 2-second UI polling are design settings, not measured latency guarantees. NFR03: parameterized SQL, known-device validation, bounded malformed diagnostics. NFR04: credentials excluded from delivered source. NFR05: minimal local architecture and low-cost ESP32 parts. NFR06: clear simulated/hardware labeling and honest test status.

Users: student demonstrator and household operator viewing room state. Use cases: view live measurements, inspect history, notice/acknowledge environmental alerts, inspect motion/door transitions, detect stale/offline device. Assumptions: one publisher/device ID; 2.4GHz reachable Wi-Fi; laptop broker/backend available; sensors wired with voltage protection; thresholds calibrated before a physical demonstration. Constraints: no safety certification, no real-time guarantees, Telegram delivery requires Internet and a linked private chat, camera uses synthetic scenes, no automatic arming. Expected prototype: breadboard node plus laptop dashboard, preceded by a software-only simulated demo.

# Home IoT Monitoring & Alert System Final Implementation Report

**CC02 · Group 8**

**Verification date:** 15 November 2026

**Scope:** Simulated monitoring for a home living room

## Purpose

Household and student operators can view temperature, humidity, relative gas response, motion and door state in one dashboard. Time-stamped history helps an operator review a change after it occurs. The door contact reports open and closed transitions. The system has no identity or authorization data.

## Starting artifacts and inventory

The project continues from `CC02_Group8_IoT_Source.zip` and `CC02_Group8_Implementation_Report_Final.pptx`. Both originals were kept intact.

| Existing component | Responsibility |
|---|---|
| `firmware/esp32/` | ESP32-WROOM DevKit sketch, configuration, sensor acquisition, local rules and LED/buzzer design |
| `simulator/` | Deterministic Python publisher with nine scenarios |
| `tools/`, `broker/` | Loopback demo broker and launcher, plus optional Mosquitto configuration examples |
| `common/` | Configuration, JSON validation and MQTT client |
| `backend/` | MQTT subscription, rule evaluation, SQLite writes, HTTP API and static assets |
| `dashboard/` | Plain HTML, CSS and JavaScript for readings, charts, events and acknowledgement |
| `tests/`, `docs/`, `diagrams/` | Python and portable C++ checks, project documentation and five Mermaid diagrams |

The original deck covers scope, objectives, architecture, hardware, interfaces, rules, dashboard, simulator, connection recovery, verification, feasibility and next steps. The revision keeps its 13 slides, layouts and Vietnamese speaker notes.

## Implementation

The simulator publishes JSON to `home/device01/telemetry` over the included loopback MQTT broker on TCP 1883. The backend subscribes, checks the configured device and telemetry fields, filters repeated or out-of-order packets, then writes accepted measurements and derived transitions to SQLite. The browser reads the local HTTP API on TCP 8080 and refreshes roughly every two seconds. The default simulator interval is 2.5 seconds. The existing MQTT prefix, payload fields, device ID and `home.db` path preserve compatibility with the existing firmware configuration and telemetry producers. The regular demo requires no external Python packages.

The first Windows walkthrough exposed an unintended disconnect about 20 seconds into continuous publishing. Outgoing QoS 0 packets reset the send timer but provide no reply. The client now probes the broker when incoming traffic is quiet even while telemetry is flowing. The new integration test reproduced the failure before the change and passed afterward.

| Condition | Behavior |
|---|---|
| Temperature | Activate after three valid samples above 35 °C. Clear after three below 33 °C. |
| Gas response | Activate after three valid samples above 2,000 ADC counts. Clear after three below 1,600 counts. Gas readiness gates evaluation. |
| Door and motion | Emit one event per confirmed transition after two stable samples. |
| Missing fresh telemetry | Mark offline after more than 20 seconds. Accept a new valid sample to resume online status. |
| Operator acknowledgement | Save the acknowledgement timestamp. The alert clears when its recovery rule is met. |

The nine retained scenarios are `normal`, `motion`, `door_open`, `high_temperature`, `high_gas`, `device_unstable`, `combined_event`, `noisy` and `sensor_fault`. Null sensor readings and sample gaps are covered by the existing rule tests.

## Previous release Windows verification

Environment: Windows 11 Pro build 26300, Python 3.11.9, Microsoft Edge 157.0.4341.46 in headless mode and g++ 14.2.0. The loopback demo ran without firewall changes.

| Check | Observed result |
|---|---|
| Python suite | 29 passed, including all seven integration methods and the 10,000-sample normal-case test. |
| Portable firmware rules | Compiled and ran successfully as a Windows host executable. |
| Startup and conflict handling | The one-command launcher started the broker, backend and simulator. A second launch reported the occupied MQTT port while the first remained online. |
| Telemetry through browser | Edge showed the lab location, **SIMULATED DATA**, fresh readings and all three charts. |
| Alert lifecycle and interaction | Combined input produced active gas and temperature alerts and a door-open event. Browser acknowledgement was saved while the alert remained active, the severity filter worked, and both alerts cleared after recovery. The device stayed online through the combined scenario. |
| SQLite persistence | After stopping and restarting the stack, the same samples, events, alert clear state and acknowledgement were retrievable. At that point the database held 23 telemetry records, nine events and two alerts. `PRAGMA integrity_check` returned `ok`. |
| Transport reconnection | The broker was stopped while the backend and simulator remained running. The browser showed broker disconnection, the backend timed out the node, and broker restart restored MQTT and online status. The simulator kept the same boot ID and advanced its sequence. |

See the accompanying Windows evidence ZIP for the test transcript, the live verification transcript, component logs and five Edge screenshots. The package is based on this Windows run. Earlier Linux results are historical.

## Incident review

From a recent alert, Review shows the measured trigger, when it was seen, when it cleared, elapsed duration and nearby logged events. The compact dashboard is intended for routine monitoring, and Present enlarges the key readings during a demo. Nearby events provide chronology. The displayed context is bounded by the dashboard’s recent event history.

## Shift handover

Operators can filter the recent alert queue and add timestamped notes to an incident. Notes are stored in SQLite with the alert ID and remain visible after restart. Retrying the same save request creates at most one note. The local prototype stores the note and time without identifying its author.

## Home release extensions

The Home IoT release adds two synthetic camera replays and a Telegram notification queue. The camera replays run in the browser independently of the ESP32. Telegram notices are generated from the gas-active and device-offline transitions. The default mode records a preview locally. Current Home release results are in [Windows verification](test-results.md).

## Conclusion

The final software release meets the Windows simulation demonstration scope. The revised dashboard offers a **Present** view with larger readings, visible trends and alerts, and the timeline hidden. **Export CSV** saves up to 300 recent readings for the selected node, including UTC receive time and source. Both controls were exercised in Edge. Slide 8 shows a real capture of the combined event and links to the live demo. The redesigned layout was checked in Edge at desktop width and at 390 pixels.

## Remaining bench checks

The ESP32 firmware design includes local outputs that run separately from network handling. Full board compilation, flashing, actual Wi-Fi/Mosquitto interoperability, sensor readings and the buzzer/LED behavior still need verification on the target hardware. The gas channel reports raw ADC counts, which require calibration for any concentration interpretation. MQTT QoS 0 allows message loss during outages. The prototype is intended for local demonstrations and has no safety certification.

Use the companion PowerShell demo guide to reproduce the software workflow.

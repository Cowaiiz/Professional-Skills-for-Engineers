# Architecture and data contract

## Working project scope

Home IoT Monitoring & Alert System, CC02 Group 8. The target room is a home living room. A sensor node reports environmental and contact measurements; a laptop stores and displays observations. The latest supplied implementation text and parts list are the working specification. No official assignment/rubric was available to establish course compliance. This implementation uses MQTT/DHT22 with PIR and reed switch. The browser camera scene is simulated. Optional Telegram delivery is handled by the backend.

| Component | Purpose / input | Output / connection |
|---|---|---|
| DHT22, MQ-2, PIR, reed | Observe room conditions and changes | Digital/analog signals to ESP32 |
| ESP32 | Sample, validate, debounce, apply local thresholds | JSON to broker over Wi-Fi/MQTT; buzzer/LED outputs |
| Simulator | Repeatable synthetic scenarios | Same telemetry schema with `source=simulator` |
| MQTT broker | Route named topics between publishers/subscribers | Telemetry/status delivered to backend |
| Python backend | Validate, deduplicate, detect events and device timeouts | SQLite transactions and local HTTP API |
| SQLite | Persist readings, event state and alert lifecycle | History queries; survives restart |
| Browser dashboard | Poll API every 2 seconds | Readings, trends, events, alerts and acknowledgement |

The dashboard is a reader of the backend; it does not connect directly to MQTT. HTTP is used between browser and backend, not as the sensor transport. The laptop must run the broker/backend to collect history; ESP32 local sensing/alarms can continue without the laptop.

## MQTT topics (QoS0, not retained)

| Topic | Publisher | Consumer and interpretation |
|---|---|---|
| `home/device01/telemetry` | ESP32 or simulator | Backend canonical sensor snapshots |
| `home/device01/status` | Node; broker last will on unexpected loss | Backend presence hint; online requires fresh telemetry |
| `home/device01/event` | Node | Optional diagnostic observer; not inserted again by backend |
| `home/device01/alert` | Node | Optional local-rule diagnostics; backend owns canonical alert records |

```json
{"device_id":"device01","boot_id":"exampleboot01","seq":1,"source":"esp32","uptime_ms":2500,"timestamp":null,"temperature":27.5,"humidity":64.0,"gas":410,"gas_ready":false,"motion":null,"door_open":false}
```

`boot_id` changes at each node restart; sequence increases within that boot. Missing required fields, incorrect types, nonfinite/out-of-range numbers, unknown devices and invalid timestamps are rejected. A sensor failure uses JSON `null`, not zero. `gas_ready=false` disables gas threshold evaluation. Server receipt time is authoritative for charts and liveness; optional node timestamps must include a timezone. ESP32 uses `null` until a real time source is implemented.

## Rules and storage

Default temperature threshold: above 35 C activates; below 33 C clears. Gas: above raw ADC2000 activates; below1600 clears. Require three consecutive valid samples, approximately 5–7.5 seconds from physical crossing at a 2.5-second interval. The band between thresholds preserves state and resets the candidate count. Invalid readings preserve active alerts and emit fault transitions. These are **demonstration settings**, not safety limits.

Motion/door require two consecutive snapshots before a canonical event. Only state transitions generate events. Sensor fault/recovery and offline/online also emit once per transition. No telemetry for more than20 seconds marks offline; a matching-boot last will can mark it sooner. A gap greater than10 seconds resets pending confirmations. Acknowledgement records operator awareness; it does not clear the condition or silence the hardware.

Tables: `devices` current state; `telemetry` uniquely keyed by device/boot/sequence; `events` timestamped transitions; `alerts` activation/clear/ack timestamps; `rejected_messages` bounded diagnostics (last100). Canonical ingestion is transactional. Active alerts are persisted; reconnects do not generate duplicate activation records. No automatic history retention/rotation is implemented: 2.5-second sampling gives about34,560 rows/day/device. Stop services and archive the database between long demos if needed.

## API

| Method/path | Result |
|---|---|
| GET `/api/health` | MQTT link state and server time |
| GET `/api/devices` | All configured device snapshots |
| GET `/api/devices/device01/state` | Latest values, rule state, alerts |
| GET `/api/devices/device01/history?limit=300` | Chronological readings; limit1..1000 |
| GET `/api/devices/device01/events?limit=100` | Newest events first |
| POST `/api/alerts/1/ack` with JSON `{}` | Acknowledge existing alert |

## Boundaries and limitations

Local-only web server by default, no accounts, TLS, external notification service, actuation beyond buzzer/LEDs, occupancy classification or gas-species estimation. Minimal MQTT code uses clean sessions and QoS0; packets can be lost. The bundled broker supports exact subscriptions, ping and last will only; no retained storage, wildcard topics, durable sessions or access control. Use Mosquitto for LAN hardware and a maintained MQTT SDK if extending the project. There is no claim of MQTT protocol conformance certification. The hardware and backend rules may differ temporarily due to packet loss; the local alarm remains independent.

The five `.mmd` diagrams in `diagrams/` are editable Mermaid sources, suitable for exporting to SVG in a Mermaid-capable editor.

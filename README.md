# Home IoT Monitoring & Alert System — CC02, Group 8

Living-room monitoring prototype for temperature/humidity, relative gas response, motion and door monitoring. The Windows 11 software demo has been verified with simulated inputs. ESP32 bench verification remains open. The dashboard includes animated camera scenarios. The camera demo uses synthetic observations.

## Start without hardware (Windows)

Install Python 3.11 or newer, extract this entire folder, and open PowerShell **inside `home-iot-monitoring`**. No pip packages are required.

```powershell
py -3.11 --version
py -3.11 -m tools.run_demo --scenario home_showcase
```

Open **http://127.0.0.1:8080**. Keep the terminal open; Ctrl+C stops the three processes. Log files are in `logs/`. If the Python launcher is unavailable, use `python` after confirming that it points to Python 3.11 or newer.

Select **My camera** and allow camera access to run local pose tracking and flag a **Possible fall**. Use one person, a fixed side-on view, and enough room to see shoulders through feet and the floor. **Demo camera** switches back to the scripted cases and stops the webcam. Live video and webcam events stay in the browser. See [webcam test steps](docs/test-case-camera.md).

Use **Person enters**, **Possible fall**, or select one of ten **Camera test case** replays. See [camera cases and expected results](docs/test-case-camera.md). The **Phone notifications** panel shows local previews for high gas and node offline in the default configuration. See the [Vietnamese feature list and presentation guide](docs/tinh-nang-va-demo.md) and [Telegram setup](docs/telegram.md).

`home_showcase` runs gas and temperature alerts, recovery and one telemetry pause. See [Windows verification](docs/test-results.md). The simulator also supports `normal`, `motion`, `door_open`, `high_temperature`, `high_gas`, `device_unstable`, `combined_event`, `noisy` and `sensor_fault`. Run one publisher for `device01` at a time.

## Optional dashboard sign-in

From the project folder, stop the demo and run the following command to create a local account. Enter your password at the prompts.

```powershell
py -3.11 -m tools.set_demo_login --username demo
py -3.11 -m tools.run_demo --scenario home_showcase
```

Open the dashboard and sign in with the account you just created. The project keeps a salted password digest in `auth.local.json`, which is excluded from Git. Sign out from the header when you are done. The password gate is intended for a small demo. Public sharing should use an HTTPS gateway with secure cookies.

## Run each component separately

Open three terminals in the project folder:

```powershell
# Terminal 1: included loopback-only demonstration broker
py -3.11 -m tools.demo_broker
```
```powershell
# Terminal 2: backend, database and dashboard server
py -3.11 -m backend.app
```
```powershell
# Terminal 3: simulated sensor node
py -3.11 -m simulator.device_simulator --scenario combined_event
```

The included broker implements only the MQTT subset needed for this demo. Use **Mosquitto** for the physical ESP32. It is not a replacement for a production MQTT broker.

## Files and responsibilities

| Folder | Contents |
|---|---|
| `firmware/esp32` | ESP32 Arduino sketch, PlatformIO project, local rules and pin configuration |
| `simulator` | Deterministic scenarios publishing JSON over MQTT |
| `common` | Configuration, payload validation and minimal MQTT client |
| `backend` | MQTT ingestion, rules, SQLite, HTTP API and Telegram sender (`telegram.py`) |
| `dashboard` | Base dashboard, camera replay (`camera-demo.js`) and notification display (`notifications.js`) |
| `broker` | Mosquitto configurations for localhost and authenticated LAN |
| `tests` | Python unit/integration tests and portable C++ rule tests |
| `diagrams` | Five editable Mermaid diagrams |
| `docs` | Architecture, requirements, demo, testing and lecturer Q&A |

## Configuration

Defaults are in `config.example.json`. To override them:

```powershell
Copy-Item config.example.json config.local.json
notepad config.local.json
```

Do not share `config.local.json` or firmware `config.h` if they contain passwords. MQTT host, port, username and password can also be set through `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` environment variables. Do not set these globally just for a demo. The backend creates `backend/database/home.db` automatically. Database content survives restarts. Back it up only with services stopped or SQLite's backup facility.

## Hardware setup

Follow [firmware setup and wiring](firmware/esp32/README.md). Assumed board: classic **ESP32-WROOM DevKit**, not ESP32-C3/S3. The MQ-2 analog output must pass through a voltage divider. The buzzer needs a suitable driver unless its module already has one. These details mean the purchase list needs checking before assembly.

## Verification

```powershell
py -3.11 -m unittest discover -s tests -v
```

See [test results](docs/test-results.md) for the Windows software run and hardware validation status.

## Troubleshooting

- `Address already in use`: stop your previous demo; do not run the included broker and Mosquitto on port 1883 simultaneously. If changing ports, update both server and device configuration.
- `Waiting for MQTT broker`: check `logs/broker.log`, broker address and port. For the included demo, keep host `127.0.0.1` and empty MQTT credentials.
- Empty dashboard: verify the simulator terminal publishes samples and `/api/health` reports `mqtt_connected: true`.
- Device offline: the dashboard needs fresh valid telemetry, not merely an MQTT connection.
- Gas not ready: hardware intentionally disables gas threshold evaluation until conditioning/calibration is acknowledged in `config.h`.
- Hardware cannot connect: ESP32 needs the laptop's LAN IPv4 address, the same reachable Wi-Fi network, and the authenticated LAN broker configuration. `localhost` on ESP32 means the ESP32 itself.
- This demo uses local HTTP and MQTT without TLS. Keep it on a trusted private network; no internet exposure is implemented.

Start with [demo guide](docs/demo-guide.md), then [architecture](docs/architecture.md), [test plan](docs/test-plan.md) and [cheat sheet](docs/cheatsheet.md).

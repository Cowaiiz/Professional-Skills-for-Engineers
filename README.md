# Home IoT Monitoring & Alert System — CC02, Group 8

Living-room monitoring prototype for temperature, humidity, relative gas response, motion and door events. The Windows 11 software demo uses simulated sensor inputs. ESP32 bench verification remains open.

The dashboard opens detailed readings from the sensor cards and keeps the latest three alerts visible while older alerts remain in the scrollable list. The room backdrop photo is by [Ksenia Chernaya on Pexels](https://www.pexels.com/photo/room-with-plants-and-sofa-4740485/).

## Start without hardware (Windows)

Install Python 3.11 or newer, extract this entire folder, and open PowerShell **inside `home-iot-monitoring`**. No pip packages are required.

```powershell
py -3.11 --version
py -3.11 -m tools.run_demo --scenario home_showcase
```

Open **http://127.0.0.1:8080**. On your first visit choose **Create an account**, then sign in. Keep the terminal open; Ctrl+C stops the three processes. Log files are in `logs/`. If the Python launcher is unavailable, use `python` after confirming that it points to Python 3.11 or newer.

The camera panel has **My camera** and **Dataset video**. Use My camera to start your webcam. Under Dataset video, choose one of the 160 included clips or open your own video. The same browser-based detector draws boxes for standing, walking, sitting and possible falls. Webcam footage, local files and camera detections are processed on the device. See [camera steps and GMDCSA-24 results](docs/test-case-camera.md).

The **Phone notifications** panel shows local previews for high gas and node offline by default. See the [Vietnamese feature list and presentation guide](docs/tinh-nang-va-demo.md) and [Telegram setup](docs/telegram.md).

`home_showcase` runs gas and temperature alerts, recovery and one telemetry pause. See [Windows verification](docs/test-results.md). The simulator also supports `normal`, `motion`, `door_open`, `high_temperature`, `high_gas`, `device_unstable`, `combined_event`, `noisy` and `sensor_fault`. Run one publisher for `device01` at a time.

## Host the GMDCSA-24 clip library

A Git clone or **Code → Download ZIP** includes all 160 original GMDCSA-24 v2.1 videos, about 1.1 GB. All clips are available at startup under **Dataset video**. **Suggested clips** includes **Subject 1 / ADL / 13** (walking and sitting) and **Subject 4 / Fall / 07** (a fall). See the [dataset credits and license](datasets/gmdcsa24/ATTRIBUTION.md).

To use a separate copy of GMDCSA-24, set `HOME_IOT_DATASET_DIR` to the folder that contains `Subject 1` through `Subject 4` on the machine running the backend, then restart the app.

```powershell
$env:HOME_IOT_DATASET_DIR = 'D:\Data\GMDCSA24-v2.1'
py -3.11 -m tools.run_demo --scenario home_showcase
```

If that folder has no valid clips, the app uses the included library. On a remote server, set the variable to a path on that server. **Open local video** in the dashboard plays an MP4 from the viewer's device.

## Dashboard accounts

The demo launcher opens the sign-in screen and enables **Create an account** by default. Each installation keeps its own accounts. To create a demo account from PowerShell, stop the demo and run the following commands. Enter your password at the prompts.

```powershell
py -3.11 -m tools.set_demo_login --username demo
py -3.11 -m tools.run_demo --scenario home_showcase
```

Open the dashboard and sign in. The project keeps a salted password digest in `auth.local.json`, which is excluded from Git.

Accounts created through the browser use password digests in `accounts.local.db`, outside Git. To hide registration, set `$env:HOME_IOT_ALLOW_SIGNUP = '0'` before starting the launcher. Existing accounts can still sign in. Sign out from the header when you are done. Use an HTTPS gateway with secure cookies when sharing the demo.

## Keep the demo online when your computer is off

A Cloudflare Quick Tunnel reaches the backend on the machine that runs it. The link stops working when that machine shuts down and changes when you create a new Quick Tunnel. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

For a stable public URL, run the project on an always-on server or VM with Python 3.11 or newer. Clone the repo onto that machine, set `TELEGRAM_MODE=preview` for the shared demo, and run `python3 -m tools.run_demo --scenario home_showcase` from the checkout. Enable the app and the HTTPS gateway at boot. Keep the HTTP backend on `127.0.0.1:8080` and point the gateway to that address. For example, use a named Cloudflare Tunnel on your domain with Cloudflare Access to restrict visitors. The included library is available on the VM as soon as the app starts. Store SQLite and account files on persistent disk if you need to keep their contents across server rebuilds. [Cloudflare Tunnel setup](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)

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
| `dashboard` | Sensor dashboard, webcam and clip player, pose detection and notification display |
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
- This demo uses local HTTP and MQTT on loopback by default. When sharing the dashboard, keep MQTT on loopback and use an authenticated HTTPS gateway as described above.

Start with [demo guide](docs/demo-guide.md), then [architecture](docs/architecture.md), [test plan](docs/test-plan.md) and [cheat sheet](docs/cheatsheet.md).

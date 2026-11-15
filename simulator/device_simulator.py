import argparse
import json
import sys
import threading
import time
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import mqtt
from common.config import load_config
from common.protocol import utc_text
from backend.engine import evaluate, initial_state, reset_candidates
from simulator.scenarios import SCENARIOS, values

def main():
    parser = argparse.ArgumentParser(description='Publish simulated ESP32 readings over real MQTT')
    parser.add_argument('--scenario', choices=SCENARIOS, default='normal')
    parser.add_argument('--device', default='device01')
    parser.add_argument('--interval', type=float, default=2.5)
    parser.add_argument('--count', type=int, default=0, help='0 runs until Ctrl+C')
    parser.add_argument('--config')
    args = parser.parse_args()
    if args.interval < 0.05 or args.count < 0:
        parser.error('interval must be >=0.05 and count must be >=0')
    cfg = load_config(args.config)
    if args.device not in cfg['devices']:
        parser.error('device must be listed in config')
    boot = uuid.uuid4().hex[:16]
    prefix = f"{cfg['mqtt']['prefix']}/{args.device}"
    client = mqtt.Client(client_id=f'sim-{args.device}-{boot}', clean_session=True)
    if cfg['mqtt']['username']:
        client.username_pw_set(cfg['mqtt']['username'], cfg['mqtt']['password'])
    status = {'device_id': args.device, 'boot_id': boot, 'status': 'offline'}
    client.will_set(prefix + '/status', json.dumps(status), qos=0, retain=False)
    connected = threading.Event()
    def on_connect(c, userdata, flags, reason, properties):
        if not reason.is_failure:
            connected.set()
            c.publish(prefix + '/status', json.dumps({**status, 'status': 'online'}), qos=0)
    def on_disconnect(c, userdata, flags, reason, properties):
        connected.clear()
    client.on_connect, client.on_disconnect = on_connect, on_disconnect
    client.reconnect_delay_set(1, 10)
    client.connect_async(cfg['mqtt']['host'], cfg['mqtt']['port'], keepalive=10)
    client.loop_start()
    start, state, tick, last_sent = time.monotonic(), initial_state(), 0, None
    try:
        while not args.count or tick < args.count:
            if not connected.wait(1):
                print('Waiting for MQTT broker...', flush=True)
                continue
            if (args.scenario, tick) in {('device_unstable', 10), ('home_showcase', 23)}:
                print('Pausing telemetry while MQTT remains connected: timeout demonstration', flush=True)
                time.sleep(cfg['rules']['offline_seconds'] + 3)
                reset_candidates(state)
            sample = dict(device_id=args.device, boot_id=boot, seq=tick, source='simulator', uptime_ms=int((time.monotonic()-start)*1000) % 4294967296, timestamp=utc_text(time.time()), **values(args.scenario, tick))
            if last_sent is not None and time.monotonic()-last_sent > cfg['rules']['max_sample_gap']:
                reset_candidates(state)
            # Only publish current data. Do not replay old telemetry as a fresh heartbeat.
            info = client.publish(prefix + '/telemetry', json.dumps(sample), qos=0, retain=False)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                for event in evaluate(state, sample, cfg['rules']):
                    channel = 'alert' if event['transition'] else 'event'
                    client.publish(prefix + '/' + channel, json.dumps(dict(device_id=args.device, boot_id=boot, seq=tick, timestamp=sample['timestamp'], **event)), qos=0, retain=False)
                last_sent = time.monotonic()
                print(f"{tick:04d} {args.scenario}: T={sample['temperature']} gas={sample['gas']} door={sample['door_open']}", flush=True)
                tick += 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('Stopping simulator', flush=True)
    finally:
        if connected.is_set():
            info = client.publish(prefix + '/status', json.dumps(status), qos=0)
            try:
                info.wait_for_publish(timeout=2)
            except RuntimeError:
                pass
        client.disconnect(); client.loop_stop()

if __name__ == '__main__':
    main()

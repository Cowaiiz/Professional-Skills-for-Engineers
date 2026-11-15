import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from uuid import uuid4
from common.config import load_config
from common.mqtt import Client, extract, packet
from backend.store import Store
from backend.app import create_server, start_mqtt
from tools.demo_broker import Broker

def reading(seq=0, **changes):
    d=dict(device_id='device01',boot_id='boot01',seq=seq,source='simulator',uptime_ms=seq*2500,timestamp=None,temperature=27.0,humidity=65.0,gas=400,gas_ready=True,motion=False,door_open=False)
    d.update(changes);return d

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.cfg=load_config();self.now=1000000.0;self.seq=0
        self.store=Store(Path(self.temp.name)/'test.db',self.cfg,lambda:self.now)
    def tearDown(self): self.store.close();self.temp.cleanup()
    def send(self, **changes):
        d=reading(changes.pop('seq',self.seq),**changes);self.seq+=1;self.now+=2.5
        return self.store.ingest('home/device01/telemetry',json.dumps(d).encode())
    def types(self): return [e['event_type'] for e in self.store.events('device01',1000)]
    def state(self): return self.store.snapshot('device01')
    def test_TC01_normal(self):
        for _ in range(10): self.assertTrue(self.send())
        self.assertEqual(self.state()['status'],'online');self.assertEqual(self.types(),['DEVICE_ONLINE'])
    def test_TC02_motion_and_clear(self):
        self.send()
        for _ in range(4):self.send(motion=True)
        for _ in range(3):self.send(motion=False)
        self.assertEqual(self.types().count('MOTION_DETECTED'),1);self.assertEqual(self.types().count('MOTION_CLEARED'),1)
    def test_TC03_door(self):
        self.send();self.send(door_open=True);self.send(door_open=True)
        self.assertIn('DOOR_OPENED',self.types())
    def test_TC04_door_repeated(self):
        self.send()
        for _ in range(3):
            for _ in range(3):self.send(door_open=True)
            for _ in range(3):self.send(door_open=False)
        self.assertEqual(self.types().count('DOOR_OPENED'),3);self.assertEqual(self.types().count('DOOR_CLOSED'),3)
    def test_TC05_temperature_hysteresis(self):
        for _ in range(3):self.send(temperature=36)
        self.assertEqual(len(self.state()['alerts']),1)
        for _ in range(5):self.send(temperature=34)
        self.assertIsNone(self.state()['alerts'][0]['cleared_at'])
        for _ in range(3):self.send(temperature=32)
        self.assertIsNotNone(self.state()['alerts'][0]['cleared_at'])
    def test_TC06_gas_activation_and_clear(self):
        for _ in range(8):self.send(gas=2600)
        self.assertEqual(len(self.state()['alerts']),1)
        for _ in range(3):self.send(gas=400)
        self.assertIsNotNone(self.state()['alerts'][0]['cleared_at'])
    def test_TC07_missing_field(self):
        d=reading();del d['humidity']
        self.assertFalse(self.store.ingest('home/device01/telemetry',json.dumps(d)))
        self.assertIsNone(self.state()['last_seen'])
    def test_TC08_wrong_types(self):
        for field,value in [('temperature','27'),('humidity',True),('gas',-1),('motion',1),('door_open','false'),('humidity',101),('seq',False)]:
            with self.subTest(field=field,value=value):
                self.assertFalse(self.store.ingest('home/device01/telemetry',json.dumps(reading(**{field:value}))))
    def test_TC09_invalid_json(self):
        for payload in [b'{broken',b'[]',b'null',b'\xff',b'{"temperature":NaN}',b'x'*20000]:
            self.assertFalse(self.store.ingest('home/device01/telemetry',payload))
        self.assertTrue(self.send())
    def test_TC11_timeout_once(self):
        self.send();self.now+=21;self.store.sweep();self.store.sweep()
        self.assertEqual(self.state()['status'],'offline');self.assertEqual(self.types().count('DEVICE_OFFLINE'),1)
    def test_TC12_reconnect(self):
        self.send();self.now+=21;self.store.sweep();self.send()
        self.assertEqual(self.state()['status'],'online');self.assertEqual(self.types().count('DEVICE_ONLINE'),2)
    def test_TC13_combined(self):
        for _ in range(4):self.send(gas=2600,temperature=38,motion=True,door_open=True)
        self.assertEqual(len(self.state()['alerts']),2)
        self.assertTrue({'GAS_ALERT','HIGH_TEMPERATURE','MOTION_DETECTED','DOOR_OPENED'}.issubset(self.types()))
    def test_TC14_noise(self):
        for i in range(50):self.send(temperature=36 if i%2 else 34,door_open=bool(i%2))
        self.assertEqual(self.types(),['DEVICE_ONLINE'])
    def test_TC15_10000_normal_samples(self):
        for _ in range(10000):self.send()
        self.assertEqual(self.types(),['DEVICE_ONLINE']);self.assertEqual(len(self.store.history('device01',1000)),1000)
    def test_null_is_fault_not_normal_or_clear(self):
        for _ in range(3):self.send(temperature=38)
        for _ in range(5):self.send(temperature=None)
        self.assertEqual(self.types().count('SENSOR_FAULT'),1)
        self.assertIsNone(self.state()['alerts'][0]['cleared_at'])
        self.send(temperature=34);self.assertIn('SENSOR_RECOVERED',self.types())
    def test_warmup_does_not_trigger_or_clear(self):
        for _ in range(4):self.send(gas=2600,gas_ready=False)
        self.assertEqual(self.state()['alerts'],[])
    def test_duplicate_out_of_order_no_heartbeat(self):
        self.send(seq=5);last=self.state()['last_seen'];self.now+=30
        for seq in [5,4]:self.assertFalse(self.store.ingest('home/device01/telemetry',json.dumps(reading(seq))))
        self.assertEqual(self.state()['last_seen'],last);self.store.sweep();self.assertEqual(self.state()['status'],'offline')
    def test_retained_and_mismatched_device(self):
        self.assertFalse(self.store.ingest('home/device01/telemetry',json.dumps(reading()),True))
        self.assertFalse(self.store.ingest('home/device02/telemetry',json.dumps(reading())))
        self.assertIsNone(self.state()['last_seen'])
    def test_ack_not_clear_and_persistence(self):
        for _ in range(3):self.send(gas=2600)
        alert=self.state()['alerts'][0];self.assertTrue(self.store.acknowledge(alert['id']))
        self.store.close();self.store=Store(Path(self.temp.name)/'test.db',self.cfg,lambda:self.now)
        self.send(gas=2600)
        self.assertEqual(len(self.state()['alerts']),1);self.assertIsNone(self.state()['alerts'][0]['cleared_at']);self.assertIsNotNone(self.state()['alerts'][0]['acknowledged_at'])
    def test_gap_resets_confirmation(self):
        self.send(temperature=36);self.send(temperature=36);self.now+=15;self.send(temperature=36)
        self.assertEqual(self.state()['alerts'],[])
    def test_old_boot_lwt_ignored(self):
        self.send();self.send(boot_id='boot02');self.store.ingest('home/device01/status',json.dumps(dict(device_id='device01',boot_id='boot01',status='offline')))
        self.assertEqual(self.state()['status'],'online')
    def test_old_boot_telemetry_ignored(self):
        self.send();self.send(boot_id='boot02');self.assertFalse(self.send(boot_id='boot01'))
    def test_nan_and_timestamp_rejected(self):
        for changes in [dict(temperature=float('nan')),dict(timestamp='2026-11-09T12:00:00'),dict(timestamp='bad')]:
            self.assertFalse(self.store.ingest('home/device01/telemetry',json.dumps(reading(**changes))))

def until(condition, timeout=6):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if condition():return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for condition')

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Report sandbox restrictions explicitly, never treat these as passes.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            try:
                with socket.create_connection(listener.getsockname(),timeout=1):pass
            except OSError as exc:
                if getattr(exc,'winerror',None)==10013:
                    raise unittest.SkipTest('Windows sandbox denies loopback TCP (WinError 10013)')
                raise
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.cfg=load_config();self.cfg['rules']['offline_seconds']=.3
        self.broker=Broker(('127.0.0.1',0));self.bt=threading.Thread(target=self.broker.serve_forever,daemon=True);self.bt.start()
        self.cfg['mqtt']['port']=self.broker.server_address[1]
        self.store=Store(Path(self.tmp.name)/'db.sqlite',self.cfg);self.health={'mqtt_connected':False}
        self.worker=start_mqtt(self.store,self.cfg,self.health)
        self.client=Client('integration-simulator');self.client.connect_async('127.0.0.1',self.cfg['mqtt']['port'],10);self.client.loop_start()
        until(lambda:self.health['mqtt_connected'] and self.client.connected)
        until(lambda:any('home/device01/telemetry' in peer.topics for peer in list(self.broker.clients.values())))
        self.server=create_server(self.store,self.health,port=0);self.web=threading.Thread(target=self.server.serve_forever,daemon=True);self.web.start()
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.web.join()
        self.client.disconnect();self.client.loop_stop();self.worker.disconnect();self.worker.loop_stop()
        self.broker.disconnect_clients();self.broker.shutdown();self.broker.server_close();self.bt.join();self.store.close();self.tmp.cleanup()
    def send(self,seq,**changes):
        self.assertEqual(self.client.publish('home/device01/telemetry',json.dumps(reading(seq,**changes))).rc,0)
        until(lambda:len(self.store.history('device01'))>=seq+1)
    def fetch(self,path):
        with urllib.request.urlopen(self.url+path,timeout=3) as r:return json.load(r)
    def test_mqtt_database_web_alert_ack(self):
        for i in range(4):self.send(i,gas=2600,temperature=38,motion=True,door_open=True)
        state=self.fetch('/api/devices/device01/state');self.assertEqual(state['latest']['gas'],2600)
        self.assertEqual(len(self.fetch('/api/devices/device01/history')),4);self.assertEqual(len(state['alerts']),2)
        alert_id=state['alerts'][0]['id'];req=urllib.request.Request(self.url+f'/api/alerts/{alert_id}/ack',data=b'{}',headers={'Content-Type':'application/json'})
        self.assertTrue(json.load(urllib.request.urlopen(req))['ok'])
        with urllib.request.urlopen(self.url) as r:self.assertIn(b'Home IoT Monitoring',r.read())
    def test_TC10_transport_disconnect_reconnect(self):
        self.send(0);self.broker.disconnect_clients()
        until(lambda:not self.health['mqtt_connected']);time.sleep(.35);self.store.sweep()
        self.assertEqual(self.store.snapshot('device01')['status'],'offline')
        until(lambda:self.health['mqtt_connected'] and self.client.connected)
        until(lambda:any('home/device01/telemetry' in peer.topics for peer in list(self.broker.clients.values())))
        self.send(1);self.assertEqual(self.store.snapshot('device01')['status'],'online')
    def test_publish_only_client_keeps_connection_alive(self):
        disconnected = threading.Event()
        publisher = Client('publish-only')
        publisher.on_disconnect = lambda *args: disconnected.set()
        publisher.connect_async('127.0.0.1', self.cfg['mqtt']['port'], keepalive=1)
        publisher.loop_start()
        try:
            until(lambda: publisher.connected)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                self.assertFalse(disconnected.is_set(), 'Continuous publishing lost its MQTT connection')
                self.assertEqual(publisher.publish('home/device01/event', '{}').rc, 0)
                time.sleep(.1)
        finally:
            publisher.disconnect()
            publisher.loop_stop()

    def test_notification_preview_records_only_transitions(self):
        self.cfg['telegram']['mode'] = 'preview'
        for seq in range(5):
            self.send(seq, gas=2600)
        items = self.fetch('/api/notifications')
        self.assertEqual(items['mode'], 'preview')
        self.assertEqual(len(items['items']), 1)
        self.assertEqual(items['items'][0]['event_type'], 'GAS_ALERT')
        self.assertIn('2600 ADC', items['items'][0]['message'])
        self.assertTrue(items['items'][0]['message'].startswith('[SIMULATED]'))

        time.sleep(0.35)
        self.store.sweep()
        self.store.sweep()
        rows = self.fetch('/api/notifications')['items']
        self.assertEqual([row['event_type'] for row in rows], ['DEVICE_OFFLINE', 'GAS_ALERT'])
        self.assertTrue(all(row['status'] == 'preview' for row in rows))
        self.assertNotIn('token', items)
        self.assertNotIn('chat_id', items)

    def test_live_notification_requires_opt_in_for_simulation(self):
        self.cfg['telegram'].update(mode='live', recipient_key='test', allow_simulated=False)
        for seq in range(3):
            self.send(seq, gas=2600)
        self.assertEqual(self.store.notifications()[0]['status'], 'skipped')
        self.assertIsNone(self.store.claim_notification())

        time.sleep(0.35)
        self.cfg['telegram']['allow_simulated'] = True
        self.store.sweep()
        entry = self.store.claim_notification()
        self.assertIn('Sensor node offline', entry['message'])
        self.assertIsNone(self.store.claim_notification())
        self.store.mark_interrupted_notifications()
        self.assertEqual(self.store.notifications()[0]['status'], 'unknown')
        self.assertIsNone(self.store.claim_notification())

    def test_disabling_simulated_delivery_cancels_an_unsent_item(self):
        self.cfg['telegram'].update(mode='live', recipient_key='test', allow_simulated=True)
        for seq in range(3):
            self.send(seq, gas=2600)
        self.assertEqual(self.store.notifications()[0]['status'], 'queued')
        self.cfg['telegram']['allow_simulated'] = False
        self.assertIsNone(self.store.claim_notification())
        self.assertEqual(self.store.notifications()[0]['status'], 'skipped')

    def test_handover_notes_are_validated_and_retry_safe(self):
        for seq in range(3):
            self.send(seq, gas=2600)
        alert = self.fetch('/api/devices/device01/state')['alerts'][0]
        path = f'/api/alerts/{alert["id"]}/notes'
        self.assertEqual(self.fetch(path), {'notes': []})

        def post(body, request_id, route=path):
            request = urllib.request.Request(
                self.url + route,
                data=json.dumps(dict(body=body, request_id=request_id), ensure_ascii=False).encode(),
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.load(response)

        request_id = str(uuid4())
        first = post('  Đã kiểm tra kho.  ', request_id)
        self.assertEqual(first['notes'][0]['body'], 'Đã kiểm tra kho.')
        self.assertEqual(post('Đã kiểm tra kho.', request_id), first)
        later = post('Tiếp tục theo dõi.', str(uuid4()))
        self.assertEqual(len(later['notes']), 2)
        self.assertEqual(self.fetch(path), later)
        for body, key, route, status in [
            (' ', str(uuid4()), path, 400),
            ('x' * 401, str(uuid4()), path, 400),
            ('valid', 'invalid', path, 400),
            ('valid', str(uuid4()), '/api/alerts/9999/notes', 404),
        ]:
            with self.subTest(status=status, body=body[:10]):
                with self.assertRaises(urllib.error.HTTPError) as exc:
                    post(body, key, route)
                self.assertEqual(exc.exception.code, status)

    def test_malformed_does_not_kill_mqtt_worker(self):
        self.client.publish('home/device01/telemetry','{bad');self.send(0)
        self.assertTrue(self.health['mqtt_connected']);self.assertEqual(self.store.snapshot('device01')['latest']['temperature'],27)
    def test_api_limits_and_origin(self):
        for path in ['/api/devices/no/state','/assets/../config.example.json','/api/devices/device01/history?limit=bad']:
            with self.assertRaises(urllib.error.HTTPError):self.fetch(path)
        req=urllib.request.Request(self.url+'/api/alerts/1/ack',data=b'{}',headers={'Content-Type':'application/json','Origin':'http://evil.example'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
        self.assertEqual(error.exception.code,403)
    def test_protocol_fragmented_frame(self):
        full=packet(0x30,b'a'*300);buf=bytearray(full[:2]);self.assertIsNone(extract(buf));buf.extend(full[2:]);self.assertEqual(extract(buf),(0x30,b'a'*300));self.assertEqual(buf,bytearray())

if __name__=='__main__':unittest.main(verbosity=2)

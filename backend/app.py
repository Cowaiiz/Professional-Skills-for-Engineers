"""Local web/API server and MQTT worker. No pip dependencies."""
import argparse
import json
import logging
import mimetypes
import threading
import time
from uuid import UUID
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote
from common import mqtt
from common.config import ROOT, load_config
from backend.store import Store
from backend.telegram import run_notifications

def create_server(store, health, host='127.0.0.1', port=8080):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def respond(self, payload, status=200, content_type='application/json'):
            raw = json.dumps(payload, allow_nan=False).encode() if content_type=='application/json' else payload
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            try: self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError): pass
        def do_GET(self):
            url = urlsplit(self.path);parts = url.path.strip('/').split('/')
            if url.path == '/api/notifications':
                return self.respond({'mode': store.cfg['telegram']['mode'], 'items': store.notifications()})
            if url.path == '/api/health': return self.respond(dict(health, server_time=time.time()))
            if url.path == '/api/devices':
                store.sweep();return self.respond([store.snapshot(d) for d in store.cfg['devices']])
            if len(parts)==4 and parts[:2]==['api','devices']:
                device, resource = parts[2:]
                if device not in store.cfg['devices']: return self.respond({'error':'Unknown device'},404)
                store.sweep()
                if resource == 'state': return self.respond(store.snapshot(device))
                if resource in ('history','events'):
                    try: limit = min(1000,max(1,int(parse_qs(url.query).get('limit',['300'])[0])))
                    except ValueError: return self.respond({'error':'limit must be an integer'},400)
                    return self.respond(getattr(store, resource)(device,limit))
                return self.respond({'error':'Unknown resource'},404)
            if len(parts) == 4 and parts[:2] == ['api', 'alerts'] and parts[3] == 'notes':
                alert_id = self.alert_id(parts[2])
                if alert_id is None:
                    return self.respond({'error': 'Invalid alert ID'}, 400)
                return self.respond_notes(store.handover_notes(alert_id))
            if url.path=='/': filename = 'index.html'
            elif url.path.startswith('/assets/'): filename = unquote(url.path[8:])
            else: return self.respond({'error':'Not found'},404)
            root = (ROOT/'dashboard').resolve();file = (root/filename).resolve()
            if not file.is_relative_to(root) or not file.is_file(): return self.respond({'error':'Not found'},404)
            return self.respond(file.read_bytes(),content_type=(mimetypes.guess_type(file.name)[0] or 'application/octet-stream')+'; charset=utf-8')
        @staticmethod
        def alert_id(raw):
            try:
                value = int(raw)
            except ValueError:
                return None
            return value if 0 < value <= 2**63 - 1 else None

        def respond_notes(self, notes):
            if notes is None:
                return self.respond({'error': 'Unknown alert'}, 404)
            return self.respond({'notes': notes})

        def save_note(self, alert_id):
            try:
                size = int(self.headers.get('Content-Length', ''))
            except ValueError:
                return self.respond({'error': 'Content length required'}, 411)
            if not 0 < size <= 4096:
                return self.respond({'error': 'Invalid note size'}, 413)
            try:
                data = json.loads(self.rfile.read(size))
                body = data['body'].strip()
                request_id = str(UUID(data['request_id']))
                body.encode('utf-8')
            except (ValueError, KeyError, AttributeError, TypeError):
                return self.respond({'error': 'Invalid handover note'}, 400)
            if not 0 < len(body) <= 400 or '\0' in body:
                return self.respond({'error': 'Note must be 1 to 400 characters'}, 400)
            return self.respond_notes(store.add_handover_note(alert_id, request_id, body))

        def do_POST(self):
            parts = urlsplit(self.path).path.strip('/').split('/')
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'): return self.respond({'error':'Cross-origin denied'},403)
            if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.respond({'error':'JSON required'},415)
            if len(parts) != 4 or parts[:2] != ['api', 'alerts'] or parts[3] not in ('ack', 'notes'):
                return self.respond({'error': 'Not found'}, 404)
            alert_id = self.alert_id(parts[2])
            if alert_id is None:
                return self.respond({'error': 'Invalid alert ID'}, 400)
            if parts[3] == 'notes':
                return self.save_note(alert_id)
            if not store.acknowledge(alert_id): return self.respond({'error':'Unknown alert'},404)
            return self.respond({'ok':True})
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server

def start_mqtt(store, cfg, health):
    client = mqtt.Client(client_id='home-backend')
    if cfg['mqtt']['username']: client.username_pw_set(cfg['mqtt']['username'],cfg['mqtt']['password'])
    client.reconnect_delay_set(1,10)
    def on_connect(c, userdata, flags, reason, properties):
        health['mqtt_connected'] = not reason.is_failure
        if not reason.is_failure:
            for device in cfg['devices']:
                for channel in ('telemetry','status'): c.subscribe(f"{cfg['mqtt']['prefix']}/{device}/{channel}")
    def on_disconnect(c, userdata, flags, reason, properties): health['mqtt_connected'] = False
    def on_message(c, userdata, msg):
        try: store.ingest(msg.topic,msg.payload,retained=msg.retain)
        except Exception: logging.exception('Message/database processing failure')
    client.on_connect,client.on_disconnect,client.on_message = on_connect,on_disconnect,on_message
    client.connect_async(cfg['mqtt']['host'],cfg['mqtt']['port'],keepalive=15);client.loop_start()
    return client

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config');cfg=load_config(parser.parse_args().config)
    store=Store(ROOT/cfg['database'],cfg);health={'mqtt_connected':False};client=start_mqtt(store,cfg,health)
    stop=threading.Event()
    def monitor():
        while not stop.wait(1): store.sweep()
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    notifier = None
    if cfg['telegram']['mode'] == 'live':
        notifier = threading.Thread(target=run_notifications, args=(store, stop), daemon=True)
        notifier.start()
    server=create_server(store,health,cfg['web']['host'],cfg['web']['port'])
    print(f"Dashboard: http://{cfg['web']['host']}:{cfg['web']['port']}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        stop.set();thread.join(2);client.disconnect();client.loop_stop();server.server_close()
        if notifier:
            notifier.join(6)
        if not notifier or not notifier.is_alive():
            store.close()

if __name__=='__main__': main()

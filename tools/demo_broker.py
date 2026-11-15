"""Loopback-only MQTT demo broker. QoS0 delivery, exact subscriptions, LWT.
No authentication, TLS, wildcards, retained storage or persistence.
Use Mosquitto for physical hardware. Never expose this broker to a LAN.
"""
import argparse
import socket
import socketserver
import struct
import threading
import time
from common.mqtt import packet, string, extract, read_string

class Broker(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    def __init__(self, address):
        self.clients, self.lock = {}, threading.RLock()
        super().__init__(address, Handler)
    def broadcast(self, topic, payload):
        with self.lock: clients = list(self.clients.values())
        for peer in clients:
            if topic in peer.topics:
                try: peer.send(packet(0x30, string(topic) + payload))
                except OSError: pass
    def disconnect_clients(self):
        with self.lock: clients = list(self.clients.values())
        for peer in clients:
            try: peer.request.shutdown(socket.SHUT_RDWR)
            except OSError: pass

class Handler(socketserver.BaseRequestHandler):
    def send(self, data):
        with self.write_lock: self.request.sendall(data)
    def handle(self):
        self.write_lock, self.topics = threading.Lock(), set()
        self.client_id, self.will, self.graceful = None, None, False
        keepalive, last = 15, time.monotonic()
        self.request.settimeout(.25);buf = bytearray()
        try:
            while True:
                try:
                    raw = self.request.recv(4096)
                    if not raw: break
                    buf.extend(raw)
                except socket.timeout:
                    if time.monotonic()-last > keepalive*1.5: break
                item = extract(buf)
                while item:
                    header, body = item;kind = header >> 4;last = time.monotonic()
                    if kind == 1:
                        protocol, pos = read_string(body)
                        if protocol != 'MQTT' or body[pos] != 4: raise ValueError('MQTT 3.1.1 required')
                        flags = body[pos+1];keepalive = struct.unpack_from('!H', body, pos+2)[0] or 60
                        self.client_id, pos = read_string(body, pos+4)
                        if flags & 4:
                            topic, pos = read_string(body, pos);message, pos = read_string(body, pos)
                            self.will = (topic, message.encode())
                        with self.server.lock:
                            old = self.server.clients.get(self.client_id)
                            if old and old is not self: old.request.shutdown(socket.SHUT_RDWR)
                            self.server.clients[self.client_id] = self
                        self.send(packet(0x20, b'\0\0'))
                    elif not self.client_id: raise ValueError('CONNECT required')
                    elif kind == 8:
                        pos, grants = 2, bytearray()
                        while pos < len(body):
                            topic, pos = read_string(body, pos);self.topics.add(topic);pos += 1;grants.append(0)
                        self.send(packet(0x90, body[:2]+grants))
                    elif kind == 3:
                        topic, pos = read_string(body);qos = (header >> 1) & 3
                        if qos > 1: raise ValueError('Unsupported QoS')
                        if qos == 1: self.send(packet(0x40, body[pos:pos+2]));pos += 2
                        self.server.broadcast(topic, body[pos:])
                    elif kind == 12: self.send(packet(0xd0))
                    elif kind == 14: self.graceful = True;return
                    item = extract(buf)
        except (OSError, ValueError, IndexError, struct.error): pass
        finally:
            with self.server.lock:
                if self.server.clients.get(self.client_id) is self: self.server.clients.pop(self.client_id)
            if self.will and not self.graceful: self.server.broadcast(*self.will)

if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--port', type=int, default=1883)
    with Broker(('127.0.0.1', parser.parse_args().port)) as broker:
        print(f'Demo MQTT broker listening on {broker.server_address}', flush=True)
        try: broker.serve_forever()
        except KeyboardInterrupt: pass

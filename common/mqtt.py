"""MQTT 3.1.1 subset client: TCP, clean sessions, QoS0, reconnect, last will.
No TLS or offline replay. Use a full SDK when extending beyond this prototype.
"""
import socket
import struct
import threading
import time
import logging
from types import SimpleNamespace
MQTT_ERR_SUCCESS = 0

def string(value):
    raw = value.encode('utf-8')
    return struct.pack('!H', len(raw)) + raw

def packet(header, body=b''):
    length, encoded = len(body), bytearray()
    while True:
        digit = length % 128; length //= 128
        encoded.append(digit | (128 if length else 0))
        if not length: return bytes([header]) + encoded + body

def extract(buffer):
    if len(buffer) < 2: return None
    length = 0
    for i in range(1, 5):
        if len(buffer) <= i: return None
        digit = buffer[i];length += (digit & 127) * (128 ** (i-1))
        if length > 65536: raise ValueError('MQTT packet too large')
        if not digit & 128:
            end = i + 1 + length
            if len(buffer) < end: return None
            result = (buffer[0], bytes(buffer[i+1:end]));del buffer[:end];return result
    raise ValueError('Invalid MQTT remaining length')

def read_string(body, offset=0):
    if offset + 2 > len(body): raise ValueError('Truncated MQTT string')
    length = struct.unpack_from('!H', body, offset)[0];end = offset + 2 + length
    if end > len(body): raise ValueError('Truncated MQTT string')
    return body[offset+2:end].decode('utf-8'), end

class PublishInfo:
    def __init__(self, rc): self.rc = rc
    def wait_for_publish(self, timeout=None):
        if self.rc: raise RuntimeError('Disconnected')

class Client:
    def __init__(self, client_id, clean_session=True):
        self.client_id, self.username, self.password = client_id, '', ''
        self.will, self.socket = None, None
        self.on_connect = self.on_disconnect = self.on_message = None
        self.stop = threading.Event(); self.write_lock = threading.RLock();self.connected = False
        self.retry_min, self.retry_max, self.packet_id = 1, 10, 0
        self.last_received = self.last_sent = time.monotonic();self.buffer = bytearray()
    def username_pw_set(self, user, password): self.username, self.password = user, password
    def will_set(self, topic, payload, qos=0, retain=False): self.will = (topic, payload, retain)
    def reconnect_delay_set(self, low, high): self.retry_min, self.retry_max = low, high
    def connect_async(self, host, port, keepalive=15): self.host, self.port, self.keepalive = host, port, keepalive
    def loop_start(self):
        self.thread = threading.Thread(target=self._run, daemon=True);self.thread.start()
    def loop_stop(self):
        self.stop.set()
        if hasattr(self, 'thread'): self.thread.join(5)
    def _send(self, data):
        with self.write_lock:
            if not self.socket: raise OSError('Disconnected')
            self.socket.sendall(data);self.last_sent = time.monotonic()
    def _close(self):
        with self.write_lock:
            if self.socket:
                try: self.socket.close()
                except OSError: pass
            self.socket, self.connected = None, False
    def disconnect(self):
        self.stop.set()
        try: self._send(packet(0xe0))
        except OSError: pass
        self._close()
    def subscribe(self, topic, qos=0):
        self.packet_id = self.packet_id % 65535 + 1
        self._send(packet(0x82, struct.pack('!H', self.packet_id) + string(topic) + b'\0'))
    def publish(self, topic, payload, qos=0, retain=False):
        if not self.connected: return PublishInfo(1)
        if isinstance(payload, str): payload = payload.encode()
        try:
            self._send(packet(0x30 | int(retain), string(topic) + payload));return PublishInfo(0)
        except OSError:
            self._close();return PublishInfo(1)
    def _run(self):
        retry = self.retry_min
        while not self.stop.is_set():
            try:
                self.socket = socket.create_connection((self.host, self.port), timeout=2);self.socket.settimeout(.25)
                flags = 2; payload = string(self.client_id)
                if self.will:
                    flags |= 4 | (32 if self.will[2] else 0);payload += string(self.will[0]) + string(self.will[1])
                if self.username:
                    flags |= 192;payload += string(self.username) + string(self.password)
                self._send(packet(0x10, string('MQTT') + bytes([4, flags]) + struct.pack('!H', self.keepalive) + payload))
                self.buffer.clear();self.last_received = time.monotonic()
                last_ping = self.last_received
                while not self.stop.is_set():
                    try:
                        chunk = self.socket.recv(4096)
                        if not chunk: raise OSError('Broker closed socket')
                        self.buffer.extend(chunk)
                    except socket.timeout: pass
                    item = extract(self.buffer)
                    while item:
                        header, body = item;self.last_received = time.monotonic();kind = header >> 4
                        if kind == 2:
                            if len(body) != 2 or body[1] != 0: raise OSError('MQTT connection refused')
                            self.connected, retry = True, self.retry_min
                            if self.on_connect: self.on_connect(self, None, None, SimpleNamespace(is_failure=False), None)
                        elif kind == 3:
                            topic, pos = read_string(body);qos = (header >> 1) & 3
                            if qos > 1: raise ValueError('QoS 2 unsupported')
                            if qos == 1: self._send(packet(0x40, body[pos:pos+2]));pos += 2
                            if self.on_message: self.on_message(self, None, SimpleNamespace(topic=topic, payload=body[pos:], retain=bool(header&1)))
                        item = extract(self.buffer)
                    now = time.monotonic()
                    if now-self.last_received > self.keepalive*2: raise OSError('Broker timeout')
                    # Outgoing QoS 0 publishes receive no reply. Probe quiet
                    # inbound connections even while telemetry is being sent.
                    ping_interval = self.keepalive / 2
                    if (self.connected and now - last_ping >= ping_interval
                            and now - min(self.last_sent, self.last_received) >= ping_interval):
                        self._send(packet(0xc0))
                        last_ping = now
            except (OSError, ValueError, AttributeError) as exc:
                logging.debug('MQTT reconnect: %s', exc)
            finally:
                self._close()
                if self.on_disconnect: self.on_disconnect(self, None, None, None, None)
            if self.stop.wait(retry): break
            retry = min(self.retry_max, retry*2)

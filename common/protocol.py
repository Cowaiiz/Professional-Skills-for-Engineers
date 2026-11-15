"""One wire contract for the simulator, firmware and backend."""
import json
import math
import re
from datetime import datetime, timezone

IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{1,48}$')
NUMERIC = {'temperature': (-40, 80), 'humidity': (0, 100), 'gas': (0, 4095)}

def utc_text(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec='milliseconds')

def decode(payload):
    if len(payload) > 16384:
        raise ValueError('Message exceeds 16 KiB')
    def invalid_constant(value):
        raise ValueError('Non-finite JSON constant: ' + value)
    obj = json.loads(payload, parse_constant=invalid_constant)
    if not isinstance(obj, dict):
        raise ValueError('Expected a JSON object')
    return obj

def validate_telemetry(obj, device):
    if obj.get('device_id') != device or not IDENTIFIER.fullmatch(device):
        raise ValueError('Topic/payload device mismatch')
    if not isinstance(obj.get('boot_id'), str) or not IDENTIFIER.fullmatch(obj['boot_id']):
        raise ValueError('Invalid boot_id')
    if type(obj.get('seq')) is not int or not 0 <= obj['seq'] <= 2147483647:
        raise ValueError('seq must be a nonnegative 31-bit integer')
    if obj.get('source') not in ('simulator', 'esp32'):
        raise ValueError('source must be simulator or esp32')
    if type(obj.get('uptime_ms')) is not int or not 0 <= obj['uptime_ms'] <= 4294967295:
        raise ValueError('Invalid uptime_ms')
    for field, (low, high) in NUMERIC.items():
        if field not in obj:
            raise ValueError('Missing sensor field: ' + field)
        value = obj[field]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high):
            raise ValueError('Invalid sensor value: ' + field)
    for field in ('motion', 'door_open'):
        if field not in obj or (obj[field] is not None and type(obj[field]) is not bool):
            raise ValueError(field + ' must be boolean or null')
    if type(obj.get('gas_ready')) is not bool:
        raise ValueError('gas_ready must be boolean')
    if 'timestamp' in obj and obj['timestamp'] is not None:
        if not isinstance(obj['timestamp'], str):
            raise ValueError('timestamp must be ISO 8601 or null')
        stamp = datetime.fromisoformat(obj['timestamp'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timestamp must include timezone')
    return {k: obj.get(k) for k in ('device_id', 'boot_id', 'seq', 'source', 'uptime_ms', 'timestamp', 'temperature', 'humidity', 'motion', 'door_open', 'gas', 'gas_ready')}

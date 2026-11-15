import json
import sqlite3
import threading
import time
from pathlib import Path
from common.protocol import decode, validate_telemetry, utc_text
from backend.engine import initial_state, evaluate, reset_candidates

SCHEMA = '''
CREATE TABLE IF NOT EXISTS devices(device_id TEXT PRIMARY KEY,name TEXT NOT NULL,location TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'offline',last_seen REAL,boot_id TEXT,state TEXT NOT NULL DEFAULT '{}',latest TEXT);
CREATE TABLE IF NOT EXISTS telemetry(id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,boot_id TEXT NOT NULL,seq INTEGER NOT NULL,received_at REAL NOT NULL,payload TEXT NOT NULL,UNIQUE(device_id,boot_id,seq));
CREATE INDEX IF NOT EXISTS telemetry_device_time ON telemetry(device_id,received_at);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,received_at REAL NOT NULL,event_type TEXT NOT NULL,severity TEXT NOT NULL,message TEXT NOT NULL,transition TEXT,value REAL,boot_id TEXT,seq INTEGER);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY,device_id TEXT NOT NULL,event_type TEXT NOT NULL,opened_at REAL NOT NULL,cleared_at REAL,acknowledged_at REAL,activation_event_id INTEGER NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_alert ON alerts(device_id,event_type) WHERE cleared_at IS NULL;
CREATE TABLE IF NOT EXISTS handover_notes(
  id INTEGER PRIMARY KEY,
  alert_id INTEGER NOT NULL REFERENCES alerts(id),
  request_id TEXT NOT NULL,
  body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 400),
  created_at REAL NOT NULL,
  UNIQUE(alert_id, request_id)
);
CREATE TABLE IF NOT EXISTS rejected_messages(id INTEGER PRIMARY KEY,received_at REAL NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(
    event_id INTEGER PRIMARY KEY REFERENCES events(id),
    message TEXT NOT NULL,
    status TEXT NOT NULL,
    recipient_key TEXT,
    updated_at REAL NOT NULL
);
'''

class Store:
    def __init__(self, path, cfg, clock=time.time):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)
        self.lock, self.cfg, self.clock = threading.RLock(), cfg, clock
        with self.db:
            for device, info in cfg['devices'].items():
                self.db.execute('INSERT INTO devices(device_id,name,location,state) VALUES(?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET name=excluded.name,location=excluded.location', (device, info['name'], info['location'], json.dumps(initial_state())))

    def close(self):
        self.db.close()

    def reject(self, reason):
        with self.lock, self.db:
            self.db.execute('INSERT INTO rejected_messages(received_at,reason) VALUES(?,?)', (self.clock(), str(reason)[:240]))
            # Bound malformed-message diagnostics rather than retaining arbitrary payloads.
            self.db.execute('DELETE FROM rejected_messages WHERE id <= (SELECT COALESCE(MAX(id),0)-100 FROM rejected_messages)')

    def _event(self, device, kind, message, severity='INFO', transition=None, value=None, boot_id=None, seq=None, source=None):
        now = self.clock()
        cur = self.db.execute('INSERT INTO events(device_id,received_at,event_type,severity,message,transition,value,boot_id,seq) VALUES(?,?,?,?,?,?,?,?,?)', (device, now, kind, severity, message, transition, value, boot_id, seq))
        if (kind == 'GAS_ALERT' and transition == 'active') or kind == 'DEVICE_OFFLINE':
            self.queue_notification(cur.lastrowid, device, kind, message, value, source, now)
        if transition == 'active':
            self.db.execute('INSERT OR IGNORE INTO alerts(device_id,event_type,opened_at,activation_event_id) VALUES(?,?,?,?)', (device, kind, now, cur.lastrowid))
        elif transition == 'clear':
            self.db.execute('UPDATE alerts SET cleared_at=? WHERE device_id=? AND event_type=? AND cleared_at IS NULL', (now, device, kind))

    def ingest(self, topic, payload, retained=False):
        try:
            parts = topic.split('/')
            if len(parts) != 3 or parts[0] != self.cfg['mqtt']['prefix'] or parts[1] not in self.cfg['devices']:
                raise ValueError('Unknown topic or device')
            device, channel = parts[1:]
            if channel not in ('telemetry', 'status'):
                return False  # Edge event/alert channels are diagnostic, not a second event writer.
            if retained:
                return False  # Retained presence or old snapshots cannot establish freshness.
            obj = decode(payload)
            if channel == 'status':
                if obj.get('device_id') != device or obj.get('status') not in ('online', 'offline'):
                    raise ValueError('Invalid status')
                with self.lock, self.db:
                    row = self.db.execute('SELECT * FROM devices WHERE device_id=?', (device,)).fetchone()
                    if obj['status'] == 'offline' and row['boot_id'] == obj.get('boot_id'):
                        self._offline(row, 'MQTT disconnect')
                return True
            sample = validate_telemetry(obj, device)
            with self.lock, self.db:
                row = self.db.execute('SELECT * FROM devices WHERE device_id=?', (device,)).fetchone()
                # Duplicate and late packets do not refresh last_seen or evaluate rules.
                highest = self.db.execute('SELECT MAX(seq) FROM telemetry WHERE device_id=? AND boot_id=?', (device, sample['boot_id'])).fetchone()[0]
                if highest is not None and sample['seq'] <= highest:
                    return False
                # An old boot must not replace the current boot after a reboot.
                if row['boot_id'] and row['boot_id'] != sample['boot_id'] and highest is not None:
                    return False
                state = json.loads(row['state'])
                if not state.get('thresholds') and not state.get('digital'):
                    state = initial_state()
                if row['boot_id'] != sample['boot_id'] or row['last_seen'] is None or self.clock()-row['last_seen'] > self.cfg['rules']['max_sample_gap']:
                    reset_candidates(state)
                self.db.execute('INSERT INTO telemetry(device_id,boot_id,seq,received_at,payload) VALUES(?,?,?,?,?)', (device, sample['boot_id'], sample['seq'], self.clock(), json.dumps(sample)))
                if row['status'] != 'online':
                    self._event(device, 'DEVICE_ONLINE', 'Fresh telemetry received')
                for event in evaluate(state, sample, self.cfg['rules']):
                    self._event(device, event['event_type'], event['message'], event['severity'], event['transition'], event['value'], sample['boot_id'], sample['seq'], sample['source'])
                self.db.execute('UPDATE devices SET status=?,last_seen=?,boot_id=?,state=?,latest=? WHERE device_id=?', ('online', self.clock(), sample['boot_id'], json.dumps(state), json.dumps(sample), device))
            return True
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            self.reject(exc)
            return False

    def _offline(self, row, reason):
        if row['status'] == 'online':
            self.db.execute("UPDATE devices SET status='offline' WHERE device_id=?", (row['device_id'],))
            previous = json.loads(row['latest']) if row['latest'] else {}
            self._event(row['device_id'], 'DEVICE_OFFLINE', reason, 'WARNING', source=previous.get('source'))

    def sweep(self):
        with self.lock, self.db:
            for row in self.db.execute("SELECT * FROM devices WHERE status='online'").fetchall():
                if self.clock() - row['last_seen'] > self.cfg['rules']['offline_seconds']:
                    self._offline(row, 'Telemetry timeout')

    def snapshot(self, device):
        with self.lock:
            row = self.db.execute('SELECT * FROM devices WHERE device_id=?', (device,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result['latest'] = json.loads(row['latest']) if row['latest'] else None
            result['state'] = json.loads(row['state'])
            result['age_seconds'] = max(0, self.clock() - row['last_seen']) if row['last_seen'] is not None else None
            result['last_seen_iso'] = utc_text(row['last_seen']) if row['last_seen'] is not None else None
            result['rules'] = self.cfg['rules']
            result['alerts'] = [dict(r) for r in self.db.execute('SELECT * FROM alerts WHERE device_id=? ORDER BY id DESC LIMIT 50', (device,))]
            return result

    def history(self, device, limit=300):
        with self.lock:
            rows = self.db.execute('SELECT * FROM telemetry WHERE device_id=? ORDER BY id DESC LIMIT ?', (device, limit)).fetchall()
            return [dict(received_at=r['received_at'], **json.loads(r['payload'])) for r in reversed(rows)]

    def events(self, device, limit=100):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT * FROM events WHERE device_id=? ORDER BY id DESC LIMIT ?', (device, limit))]

    def acknowledge(self, alert_id):
        with self.lock, self.db:
            cur = self.db.execute('UPDATE alerts SET acknowledged_at=COALESCE(acknowledged_at,?) WHERE id=?', (self.clock(), alert_id))
            return cur.rowcount > 0


    def handover_notes(self, alert_id):
        with self.lock:
            if not self.db.execute('SELECT 1 FROM alerts WHERE id=?', (alert_id,)).fetchone():
                return None
            rows = self.db.execute(
                'SELECT id, body, created_at FROM handover_notes WHERE alert_id=? ORDER BY id DESC LIMIT 20',
                (alert_id,),
            )
            return [dict(row) for row in rows]

    def add_handover_note(self, alert_id, request_id, body):
        with self.lock, self.db:
            self.db.execute(
                'INSERT INTO handover_notes(alert_id, request_id, body, created_at) '
                'SELECT id, ?, ?, ? FROM alerts WHERE id=? '
                'ON CONFLICT(alert_id, request_id) DO NOTHING',
                (request_id, body, self.clock(), alert_id),
            )
            return self.handover_notes(alert_id)


    def queue_notification(self, event_id, device, kind, reason, value, source, now):
        settings = self.cfg['telegram']
        mode = settings['mode']
        if mode == 'off':
            return
        label = 'Gas response high' if kind == 'GAS_ALERT' else 'Sensor node offline'
        detail = f'{value:g} ADC' if kind == 'GAS_ALERT' and value is not None else reason
        prefix = '' if source == 'esp32' else '[SIMULATED] '
        location = self.cfg['devices'][device]['location']
        message = f'{prefix}Home IoT | {location} ({device})\n{label} · {detail}\n{utc_text(now)}'
        status = 'preview' if mode == 'preview' else 'queued'
        if status == 'queued' and source != 'esp32' and not settings['allow_simulated']:
            status = 'skipped'
        self.db.execute(
            'INSERT INTO notifications(event_id,message,status,recipient_key,updated_at) VALUES(?,?,?,?,?)',
            (event_id, message, status, settings['recipient_key'], now),
        )

    def notifications(self):
        with self.lock:
            return [dict(row) for row in self.db.execute(
                'SELECT n.event_id,n.status,n.message,n.updated_at,e.event_type '
                'FROM notifications n JOIN events e ON n.event_id=e.id '
                'ORDER BY n.event_id DESC LIMIT 12'
            )]

    def claim_notification(self):
        with self.lock, self.db:
            now = self.clock()
            key = self.cfg['telegram']['recipient_key']
            self.db.execute(
                "UPDATE notifications SET status='expired',updated_at=? "
                "WHERE status='queued' AND (recipient_key IS NOT ? OR updated_at < ?)",
                (now, key, now - 300),
            )
            if not self.cfg['telegram']['allow_simulated']:
                self.db.execute(
                    "UPDATE notifications SET status='skipped',updated_at=? "
                    "WHERE status='queued' AND message LIKE '[SIMULATED] %'",
                    (now,),
                )
            row = self.db.execute(
                "SELECT event_id,message FROM notifications WHERE status='queued' ORDER BY event_id LIMIT 1"
            ).fetchone()
            if row:
                self.db.execute(
                    "UPDATE notifications SET status='sending',updated_at=? WHERE event_id=?",
                    (now, row['event_id']),
                )
            return row

    def finish_notification(self, event_id, status):
        with self.lock, self.db:
            self.db.execute(
                'UPDATE notifications SET status=?,updated_at=? WHERE event_id=?',
                (status, self.clock(), event_id),
            )

    def mark_interrupted_notifications(self):
        with self.lock, self.db:
            self.db.execute(
                "UPDATE notifications SET status='unknown',updated_at=? WHERE status='sending'",
                (self.clock(),),
            )


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

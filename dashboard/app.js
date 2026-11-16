'use strict';
const $ = id => document.getElementById(id);
let selected = '', recentEvents = [], lastHistory = [], currentAlerts = [];
let reviewing = null, pendingNote = null, noteSession = 0;
let measurementTrigger = null, renderedAlertKey = '';
const signals = {
  temperature: {label: 'Temperature', unit: ' °C', color: '#af583b'},
  humidity: {label: 'Humidity', unit: ' %', color: '#39847c'},
  gas: {label: 'Gas response', unit: ' ADC', color: '#a66c23'},
  door_open: {label: 'Door', states: ['Closed', 'Open'], color: '#82634e'},
  motion: {label: 'Motion', states: ['Quiet', 'Detected'], color: '#5d744c'}
};
const text = (id, value) => { $(id).textContent = value; };
const when = epoch => new Date(epoch * 1000).toLocaleString();
const sensor = (value, unit = '') => value == null ? 'Unavailable' : `${Number(value).toFixed(unit === ' ADC' ? 0 : 1)}${unit}`;
async function get(url) { const r = await fetch(url, {signal: AbortSignal.timeout(4000)}); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }
function measurementValue(row, field) {
  const value = row[field];
  if (field === 'gas' && !row.gas_ready) return null;
  if (signals[field].states) {
    if (value === true || value === 1) return 1;
    if (value === false || value === 0) return 0;
    return null;
  }
  return Number.isFinite(value) ? value : null;
}

function formatMeasurement(field, value) {
  const info = signals[field];
  return value == null ? 'Unavailable' : info.states ? info.states[value] : sensor(value, info.unit);
}

function lineChart(canvas, field, history) {
  const info = signals[field];
  const width = canvas.clientWidth, height = canvas.clientHeight, ratio = window.devicePixelRatio || 1;
  if (!width || !height) return;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const samples = history.map(row => ({time: row.received_at, value: measurementValue(row, field)}));
  const valid = samples.filter(row => row.value !== null);
  ctx.font = '12px Segoe UI';
  ctx.fillStyle = '#6e5547';
  if (!valid.length) {
    ctx.fillText('No valid readings yet', 10, height / 2);
    return;
  }
  const min = Math.min(...valid.map(row => row.value)), max = Math.max(...valid.map(row => row.value));
  const padding = Math.max((max - min) * 0.15, field === 'gas' ? 30 : 1);
  const low = info.states ? -0.15 : min - padding;
  const high = info.states ? 1.15 : max + padding;
  const first = samples[0].time, last = samples.at(-1).time;
  const gutter = info.states ? 62 : 42;
  const x = time => gutter + (time - first) / Math.max(last - first, 1) * (width - gutter - 10);
  const y = value => 12 + (high - value) / (high - low) * (height - 42);
  for (const value of info.states ? [0, 1] : [low, (high + low) / 2, high]) {
    const py = y(value);
    ctx.strokeStyle = '#e7dacf';
    ctx.beginPath();
    ctx.moveTo(gutter - 2, py);
    ctx.lineTo(width - 5, py);
    ctx.stroke();
    ctx.fillText(info.states ? info.states[value] : value.toFixed(0), 0, py + 4);
  }
  ctx.strokeStyle = info.color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  let previous = null;
  for (const {time, value} of samples) {
    if (value === null) {
      previous = null;
      continue;
    }
    if (!previous || time - previous.time > 10) ctx.moveTo(x(time), y(value));
    else {
      if (info.states) ctx.lineTo(x(time), y(previous.value));
      ctx.lineTo(x(time), y(value));
    }
    previous = {time, value};
  }
  ctx.stroke();
  if (valid.length === 1) {
    ctx.beginPath();
    ctx.arc(x(valid[0].time), y(valid[0].value), 3, 0, Math.PI * 2);
    ctx.fillStyle = info.color;
    ctx.fill();
  }
  ctx.fillStyle = '#6e5547';
  ctx.fillText(new Date(first * 1000).toLocaleTimeString(), gutter, height - 8);
  if (last > first && width >= 205) {
    ctx.textAlign = 'right';
    ctx.fillText(new Date(last * 1000).toLocaleTimeString(), width - 3, height - 8);
  }
}

function drawCharts() {
  for (const field of ['temperature', 'humidity', 'gas']) {
    lineChart($(field + '-chart'), field, lastHistory);
  }
}

function renderMeasurement() {
  const field = $('measurement-field').value;
  const info = signals[field];
  const valid = lastHistory.map(row => measurementValue(row, field)).filter(value => value !== null);
  text('measurement-title', info.label + ' history');
  const source = lastHistory.at(-1)?.source;
  const origin = source === 'simulator' ? 'Simulated data' : source === 'esp32' ? 'ESP32 hardware' : '';
  const count = lastHistory.length;
  text('measurement-summary', count ? count + (count === 1 ? ' sample' : ' samples') +
    (origin ? ' · ' + origin : '') : 'No history yet');
  text('measurement-latest', formatMeasurement(field, valid.at(-1)));
  text('measurement-stat-a-label', info.states ? 'Changes recorded' : 'Minimum');
  text('measurement-stat-b-label', info.states ? 'Valid samples' : 'Maximum');
  if (info.states) {
    const changes = valid.filter((value, i) => i > 0 && value !== valid[i - 1]).length;
    text('measurement-stat-a', changes);
    text('measurement-stat-b', valid.length);
  } else {
    text('measurement-stat-a', valid.length ? formatMeasurement(field, Math.min(...valid)) : 'Unavailable');
    text('measurement-stat-b', valid.length ? formatMeasurement(field, Math.max(...valid)) : 'Unavailable');
  }
  const table = $('measurement-rows');
  const rows = lastHistory.slice(-20).reverse().map(row => {
    const tr = document.createElement('tr');
    const time = document.createElement('td'), reading = document.createElement('td');
    time.textContent = when(row.received_at);
    reading.textContent = field === 'gas' && !row.gas_ready ? 'Sensor not ready' :
      formatMeasurement(field, measurementValue(row, field));
    tr.append(time, reading);
    return tr;
  });
  if (!rows.length) {
    const row = document.createElement('tr'), cell = document.createElement('td');
    cell.colSpan = 2;
    cell.textContent = 'No samples recorded for this device yet.';
    row.append(cell);
    rows.push(row);
  }
  table.replaceChildren(...rows);
  $('measurement-chart').setAttribute('aria-label', info.label + ' readings over time');
  lineChart($('measurement-chart'), field, lastHistory);
}
function renderEvents() {
  $('events').replaceChildren();
  const rows=recentEvents.filter(e=>$('event-filter').value==='ALL'||e.severity===$('event-filter').value);
  if(!rows.length){$('events').textContent='No matching events yet.';return;}
  for(const e of rows){const row=document.createElement('div');row.className='event '+e.severity;const time=document.createElement('time');time.textContent=new Date(e.received_at*1000).toLocaleTimeString();time.title=when(e.received_at);const detail=document.createElement('div'),title=document.createElement('strong'),desc=document.createElement('p');title.textContent=e.event_type+(e.transition?' · '+e.transition.toUpperCase():'');desc.textContent=e.message;detail.append(title,desc);row.append(time,detail);$('events').append(row);}
}
function alertLabel(alert) {
  return alert.event_type === 'GAS_ALERT' ? 'Gas alert' : 'High temperature';
}

function renderIncident() {
  const alert = currentAlerts.find(row => row.id === reviewing);
  const facts = $('incident-facts');
  const events = $('incident-events');
  facts.replaceChildren();
  events.replaceChildren();
  if (!alert) {
    text('incident-title', 'Alert details');
    text('incident-status', 'This alert is outside the latest 50.');
    $('incident-status').dataset.active = 'false';
    return;
  }
  text('incident-title', alertLabel(alert));
  text('incident-status', alert.cleared_at ? 'Cleared' : 'Active');
  $('incident-status').dataset.active = String(!alert.cleared_at);
  const activation = recentEvents.find(event => event.id === alert.activation_event_id);
  const unit = alert.event_type === 'GAS_ALERT' ? ' ADC' : ' °C';
  const duration = Math.max(0, Math.floor(alert.cleared_at - alert.opened_at));
  const details = [
    ['Opened', when(alert.opened_at)],
    ['Acknowledged', alert.acknowledged_at ? when(alert.acknowledged_at) : 'Awaiting acknowledgement'],
    ['Cleared', alert.cleared_at ? when(alert.cleared_at) : 'In progress'],
    ['Duration', alert.cleared_at ? Math.floor(duration / 60) + ' min ' + (duration % 60) + ' s' : 'Ongoing'],
    ['Trigger reading', activation?.value == null ? 'Outside recent event history' : sensor(activation.value, unit)]
  ];
  for (const [label, value] of details) {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    const description = document.createElement('dd');
    term.textContent = label;
    description.textContent = value;
    item.append(term, description);
    facts.append(item);
  }
  const nearby = recentEvents
    .filter(event => Math.abs(event.received_at - alert.opened_at) <= 60)
    .slice(0, 8).reverse();
  for (const event of nearby) {
    const row = document.createElement('li');
    const time = document.createElement('time');
    time.textContent = new Date(event.received_at * 1000).toLocaleTimeString();
    row.append(time, event.message);
    events.append(row);
  }
  if (!nearby.length) {
    const row = document.createElement('li');
    row.textContent = 'No nearby events in the recent history.';
    events.append(row);
  }
}

function showNotes(notes) {
  const list = $('handover-notes');
  list.replaceChildren();
  if (!notes.length) {
    const empty = document.createElement('li');
    empty.textContent = 'No handover notes yet.';
    list.append(empty);
    return;
  }
  for (const note of notes) {
    const row = document.createElement('li');
    const timestamp = document.createElement('time');
    timestamp.textContent = when(note.created_at);
    const body = document.createElement('p');
    body.textContent = note.body;
    row.append(timestamp, body);
    list.append(row);
  }
}

function updateSaveButton() {
  const form = $('handover-form');
  $('handover-save').disabled = !reviewing || form.dataset.saving === 'true' ||
    !$('handover-body').value.trim();
}

async function openHandover(alertId) {
  const form = $('handover-form');
  const session = ++noteSession;
  form.reset();
  $('handover-body').disabled = true;
  form.dataset.saving = 'false';
  $('handover-notes').replaceChildren();
  text('handover-status', 'Loading notes…');
  updateSaveButton();
  try {
    const result = await get('/api/alerts/' + alertId + '/notes');
    if (noteSession !== session) return;
    showNotes(result.notes);
    text('handover-status', '');
  } catch {
    if (noteSession === session) text('handover-status', 'Unable to load notes. Reopen Review to retry.');
  } finally {
    if (noteSession === session) $('handover-body').disabled = false;
  }
}

async function saveHandover(event) {
  event.preventDefault();
  const alertId = reviewing;
  const body = $('handover-body').value.trim();
  if (!alertId || !body || $('handover-save').disabled) return;
  if (!pendingNote || pendingNote.alertId !== alertId || pendingNote.body !== body) {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const requestId = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
    pendingNote = {alertId, body, requestId};
  }
  const note = pendingNote;
  const session = noteSession;
  const form = $('handover-form');
  form.dataset.saving = 'true';
  $('handover-body').disabled = true;
  updateSaveButton();
  text('handover-status', 'Saving…');
  try {
    const response = await fetch('/api/alerts/' + alertId + '/notes', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({body, request_id: note.requestId}),
      signal: AbortSignal.timeout(4000)
    });
    if (!response.ok) throw Error();
    const result = await response.json();
    if (pendingNote === note) pendingNote = null;
    if (noteSession === session) {
      showNotes(result.notes);
      form.reset();
      text('handover-status', 'Note saved.');
    }
  } catch {
    if (noteSession === session) text('handover-status', 'Could not confirm save. Retry to save this note.');
  } finally {
    if (noteSession === session) {
      form.dataset.saving = 'false';
      $('handover-body').disabled = false;
      updateSaveButton();
    }
  }
}

function fitAlerts() {
  const list = $('alerts');
  const third = list.children[2];
  list.style.maxHeight = list.children.length > 3
    ? (third.offsetTop + third.offsetHeight) + 'px' : '';
}

const alertResize = new ResizeObserver(fitAlerts);

function renderAlerts(rows, resetScroll = false) {
  const list = $('alerts');
  const filter = $('alert-filter').value;
  const matches = rows.filter(alert => filter === 'all' ||
    (filter === 'open' && !alert.cleared_at) ||
    (filter === 'unseen' && !alert.acknowledged_at) ||
    (filter === 'cleared' && Boolean(alert.cleared_at)))
    .sort((a, b) => b.opened_at - a.opened_at || b.id - a.id);
  const key = JSON.stringify([filter, Boolean(rows.length), matches]);
  if (renderedAlertKey === key && !resetScroll) return;
  renderedAlertKey = key;
  const scrollTop = resetScroll ? 0 : list.scrollTop;
  const focusedAction = list.contains(document.activeElement) ? document.activeElement.dataset.action : null;
  alertResize.disconnect();
  list.replaceChildren();
  const scrollHint = $('alert-scroll-hint');
  scrollHint.hidden = matches.length < 4;
  scrollHint.textContent = matches.length < 4 ? '' : 'Showing the 3 latest. Scroll for older alerts.';
  list.tabIndex = matches.length > 3 ? 0 : -1;
  if (!matches.length) {
    list.textContent = rows.length ? 'No alerts match this filter.' : 'No threshold alerts recorded.';
    fitAlerts();
    return;
  }
  for (const alert of matches) {
    const box = document.createElement('article');
    box.className = 'alert ' + (alert.cleared_at ? 'cleared' : alert.event_type === 'GAS_ALERT' ? 'critical' : '');
    const title = document.createElement('strong');
    title.textContent = alertLabel(alert).toUpperCase() + (alert.cleared_at ? ' · CLEARED' : ' · ACTIVE');
    const info = document.createElement('p');
    info.textContent = 'Opened ' + when(alert.opened_at) +
      (alert.acknowledged_at ? ' · Acknowledged ' + when(alert.acknowledged_at) : '');
    const actions = document.createElement('div');
    actions.className = 'alert-actions';
    const review = document.createElement('button');
    review.type = 'button';
    review.className = 'review-link';
    review.dataset.action = 'review-' + alert.id;
    review.textContent = 'Review';
    review.addEventListener('click', () => {
      reviewing = alert.id;
      renderIncident();
      $('incident').showModal();
      openHandover(alert.id);
    });
    actions.append(review);
    if (!alert.acknowledged_at) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.action = 'ack-' + alert.id;
      button.textContent = 'Acknowledge';
      button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const result = await fetch('/api/alerts/' + alert.id + '/ack', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
          });
          if (!result.ok) throw Error();
          button.textContent = 'Acknowledged';
        } catch {
          button.textContent = 'Retry acknowledgement';
          button.disabled = false;
        }
      });
      actions.append(button);
    }
    box.append(title, info, actions);
    list.append(box);
  }
  fitAlerts();
  if (matches.length > 3) {
    Array.from(list.children).slice(0, 3).forEach(box => alertResize.observe(box));
  }
  list.scrollTop = scrollTop;
  if (focusedAction) {
    list.querySelector('[data-action="' + focusedAction + '"]')?.focus({preventScroll: true});
  }
}

function downloadHistory() {
  if (!lastHistory.length) return;
  const rows = lastHistory.map(row => [
    new Date(row.received_at * 1000).toISOString(), row.temperature, row.humidity,
    row.gas, row.gas_ready, row.door_open, row.motion, row.source
  ]);
  const columns = ['received_at_utc', 'temperature_c', 'humidity_percent', 'gas_adc',
    'gas_ready', 'door_open', 'motion', 'source'];
  const csv = [columns, ...rows].map(row => row.join(',')).join('\r\n') + '\r\n';
  const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'home-iot-' + new Date().toISOString().slice(0, 10) + '.csv';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function refresh() {
  try {
    const [devices,health]=await Promise.all([get('/api/devices'),get('/api/health')]);
    if(!selected && devices.length){for(const d of devices){const op=document.createElement('option');op.value=d.device_id;op.textContent=d.name;$('device').append(op);} selected=devices[0].device_id;}
    const d=devices.find(x=>x.device_id===selected);if(!d)throw Error('No configured device');
    const devicePath = '/api/devices/' + encodeURIComponent(d.device_id);
    const t=d.latest||{}, [history,events]=await Promise.all([get(devicePath+'/history'),get(devicePath+'/events')]);
    if (selected !== d.device_id) return;
    const online=d.status==='online';$('connection').className='connection'+(!health.mqtt_connected?' error':!online?' offline':'');
    text('connection',!health.mqtt_connected?'MQTT broker disconnected · readings may be stale':online?'Device online · receiving telemetry':'Device offline · last readings are stale');
    text('location',d.location);text('source',t.source==='simulator'?'SIMULATED DATA':t.source==='esp32'?'ESP32 HARDWARE':'NO DATA');
    text('last-seen',d.last_seen_iso?`Last received: ${when(d.last_seen)} · ${Math.floor(d.age_seconds)} seconds ago`:'No telemetry received yet');
    text('temperature',sensor(t.temperature,' °C'));text('humidity',sensor(t.humidity,' %'));text('gas',sensor(t.gas,' ADC'));
    text('door',t.door_open==null?'Unknown':t.door_open?'Open':'Closed');text('motion',t.motion==null?'Unknown':t.motion?'Detected':'Quiet');
    const active=d.alerts.filter(a=>!a.cleared_at);
    text('temperature-status',!online?'STALE':t.temperature==null?'SENSOR FAULT':active.some(a=>a.event_type==='HIGH_TEMPERATURE')?'WARNING ACTIVE':'Normal / confirming');
    text('humidity-status',!online?'STALE':t.humidity==null?'SENSOR FAULT':'Valid measurement');
    text('gas-status',!online?'STALE':!t.gas_ready?'NOT READY / WARMING UP':t.gas==null?'SENSOR FAULT':active.some(a=>a.event_type==='GAS_ALERT')?'CRITICAL ALERT':'Relative response · not ppm');
    $('export').disabled = !history.length;
    lastHistory=history;recentEvents=events;currentAlerts=d.alerts;drawCharts();renderEvents();renderAlerts(currentAlerts);
    if ($('measurement').open) renderMeasurement();
    if ($('incident').open) renderIncident();
  } catch(error) { $('export').disabled = true; $('connection').className='connection error';text('connection','Backend unavailable · displayed readings are stale');for(const id of ['temperature-status','humidity-status','gas-status'])text(id,'STALE · backend unavailable'); }
  finally { setTimeout(refresh,2000); }
}
$('device').addEventListener('change', () => {
  selected = $('device').value;
  $('export').disabled = true;
  lastHistory = [];
  currentAlerts = [];
  renderAlerts(currentAlerts, true);
  if ($('measurement').open) $('measurement').close();
  if ($('incident').open) $('incident').close();
});
for (const button of document.querySelectorAll('[data-measurement]')) {
  button.addEventListener('click', () => {
    measurementTrigger = button;
    $('measurement-field').value = button.dataset.measurement;
    $('measurement').showModal();
    $('measurement-rows').closest('.measurement-table-scroll').scrollTop = 0;
    renderMeasurement();
  });
}
$('measurement-field').addEventListener('change', () => {
  $('measurement-rows').closest('.measurement-table-scroll').scrollTop = 0;
  renderMeasurement();
});
$('measurement').addEventListener('close', () => {
  measurementTrigger?.focus({preventScroll: true});
  measurementTrigger = null;
});
$('incident').addEventListener('close', () => {
  noteSession += 1;
  $('alerts').querySelector('[data-action="review-' + reviewing + '"]')?.focus();
  reviewing = null;
});
$('handover-form').addEventListener('submit', saveHandover);
$('handover-body').addEventListener('input', updateSaveButton);
$('alert-filter').addEventListener('change', () => renderAlerts(currentAlerts, true));
$('export').addEventListener('click', downloadHistory);
$('event-filter').addEventListener('change', renderEvents);
window.addEventListener('resize', () => {
  drawCharts();
  if ($('measurement').open) lineChart($('measurement-chart'), $('measurement-field').value, lastHistory);
});
refresh();

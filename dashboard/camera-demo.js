import { scenes } from './camera-scenarios.js';

const element = id => document.getElementById(id);
const svg = 'http://www.w3.org/2000/svg';
const stage = element('camera-actors');
const status = element('camera-status');
const events = element('camera-events');
const select = element('camera-case');
let replay = 0;

for (const [key, [label]] of Object.entries(scenes)) {
  select.add(new Option(label, key));
}

function addEvent(kind, message) {
  const row = document.createElement('li');
  row.dataset.kind = kind;
  row.textContent = 'SIMULATED · ' + message;
  events.append(row);
}

function createActor(id) {
  const color = id === 'A' ? '#b8f6de' : '#acd9ff';
  const group = document.createElementNS(svg, 'g');
  group.dataset.actor = id;
  group.setAttribute('color', color);
  const figure = document.createElementNS(svg, 'use');
  figure.setAttribute('href', '#camera-figure');
  const label = document.createElementNS(svg, 'text');
  label.setAttribute('class', 'camera-actor-label');
  label.setAttribute('fill', color);
  label.textContent = id;
  group.append(figure, label);
  stage.append(group);
  return {figure, label, entered: false, limited: false, floorSince: null, warned: false};
}

function draw({x, y, pose}, {figure, label}) {
  figure.setAttribute('transform', pose === 'floor'
    ? 'translate(' + (x - 25) + ' ' + y + ') rotate(80)'
    : 'translate(' + x + ' ' + y + ')');
  label.setAttribute('x', Math.min(540, Math.max(10, x - 5)));
  label.setAttribute('y', y - (pose === 'floor' ? 20 : 73));
}

function evaluate({id, x, pose, visible}, track, elapsed) {
  if (!visible) {
    track.floorSince = null;
    track.previousX = null;
    if (!track.limited) {
      addEvent('limited', 'Person ' + id + ': partial view · insufficient evidence');
      track.limited = true;
    }
    return;
  }
  if (!track.entered && track.previousX != null && track.previousX <= 211 && x > 211) {
    addEvent('entry', 'Person ' + id + ' entered the room zone');
    track.entered = true;
  }
  track.previousX = x;
  if (pose !== 'floor') {
    track.floorSince = null;
    return;
  }
  track.floorSince ??= elapsed;
  if (!track.warned && elapsed - track.floorSince >= 3) {
    addEvent('fall', 'Person ' + id + ': possible fall · on floor for 3 s');
    track.warned = true;
  }
}

function reset() {
  replay += 1;
  stage.replaceChildren();
  events.replaceChildren();
  status.textContent = 'Ready to replay a synthetic scene.';
}

function play(key) {
  reset();
  select.value = key;
  const run = replay;
  const [, duration, observe] = scenes[key];
  const start = performance.now();
  const tracks = new Map();
  status.textContent = 'Replay running · synthetic observations';

  function frame(now) {
    if (run !== replay) return;
    const elapsed = Math.max(0, (now - start) / 1000);
    for (const observation of observe(elapsed)) {
      if (!tracks.has(observation.id)) tracks.set(observation.id, createActor(observation.id));
      const track = tracks.get(observation.id);
      draw(observation, track);
      evaluate(observation, track, elapsed);
    }
    if (elapsed < duration) {
      requestAnimationFrame(frame);
      return;
    }
    const count = kind => [...events.children].filter(row => row.dataset.kind === kind).length;
    status.textContent = 'Replay complete · ' + count('entry') + ' entry · ' +
      count('fall') + ' possible fall · ' + count('limited') + ' limited view';
  }
  requestAnimationFrame(frame);
}

element('camera-case-form').addEventListener('submit', event => {
  event.preventDefault();
  play(select.value);
});
element('camera-entry').addEventListener('click', () => play('entry'));
element('camera-fall').addEventListener('click', () => play('center_fall'));
element('camera-reset').addEventListener('click', reset);

const demoButton = element('camera-mode-demo');
const liveButton = element('camera-mode-live');
const retryButton = element('camera-retry');
const video = element('camera-video');
let stream = null;
let cameraRequest = 0;
let poseSession = null;

function stopLive() {
  cameraRequest += 1;
  poseSession?.abort();
  poseSession = null;
  element('camera-live-status').removeAttribute('data-state');
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
    stream = null;
  }
  video.srcObject = null;
  video.hidden = true;
}

function showSource(live) {
  demoButton.setAttribute('aria-pressed', String(!live));
  liveButton.setAttribute('aria-pressed', String(live));
  element('camera-replay').hidden = live;
  element('camera-live').hidden = !live;
  element('camera-badge').textContent = live ? 'LOCAL WEBCAM' : 'SIMULATED SCENE';
}

function showCameraError(message) {
  element('camera-live-status').textContent = message;
  retryButton.hidden = false;
}

async function startLive() {
  stopLive();
  reset();
  showSource(true);
  const request = cameraRequest;
  retryButton.hidden = true;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    showCameraError('Open this link directly in Edge or Chrome over HTTPS, or use localhost.');
    return;
  }
  element('camera-live-status').textContent = 'Allow camera access in your browser to start.';
  try {
    const capture = await navigator.mediaDevices.getUserMedia({video: true, audio: false});
    if (request !== cameraRequest) {
      capture.getTracks().forEach(track => track.stop());
      return;
    }
    stream = capture;
    video.srcObject = stream;
    video.hidden = false;
    await video.play();
    if (request !== cameraRequest) return;
    for (const track of capture.getVideoTracks()) {
      track.addEventListener('ended', () => {
        if (stream !== capture) return;
        stopLive();
        showCameraError('The camera disconnected. Reconnect it and retry.');
      }, {once: true});
    }
    void detectLiveFalls(request);
  } catch (error) {
    if (request !== cameraRequest) return;
    stopLive();
    if (error.name === 'NotAllowedError') {
      showCameraError('Camera access was blocked. Allow it in browser site settings and retry.');
    } else if (error.name === 'NotFoundError') {
      showCameraError('No camera was found on this device.');
    } else {
      showCameraError('Could not start the camera. Close other apps using it and retry.');
    }
  }
}

async function detectLiveFalls(request) {
  const status = element('camera-live-status');
  const session = new AbortController();
  poseSession = session;
  status.textContent = 'Loading the on-device pose model…';
  try {
    const {startFallPreview} = await import('./camera-live-fall.js');
    if (session.signal.aborted) return;
    await startFallPreview({
      video,
      canvas: element('camera-overlay'),
      status,
      signal: session.signal,
      onAlert: () => {
        const list = element('live-camera-events');
        const item = document.createElement('li');
        item.textContent = new Date().toLocaleTimeString() + ' · Possible fall detected';
        list.prepend(item);
        if (list.children.length > 8) list.lastElementChild.remove();
      },
    });
  } catch {
    if (request === cameraRequest) {
      status.textContent = 'Pose model unavailable. Webcam preview is active; switch to Demo camera and retry.';
      status.dataset.state = 'limited';
    }
  }
}

function useDemo() {
  stopLive();
  showSource(false);
}

demoButton.addEventListener('click', useDemo);
liveButton.addEventListener('click', () => {
  if (liveButton.getAttribute('aria-pressed') === 'false') startLive();
});
retryButton.addEventListener('click', startLive);
window.addEventListener('pagehide', useDemo);

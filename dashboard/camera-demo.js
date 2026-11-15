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

import assert from 'node:assert/strict';
import test from 'node:test';
import { MotionFallRule, readFallEvidence } from '../dashboard/fall-rule.mjs';

function evidence(shoulder, hip, knee, foot) {
  const marks = Array(33).fill(null);
  for (const [base, point] of [[11, shoulder], [23, hip], [25, knee], [27, foot]]) {
    if (!point) continue;
    const [x, y] = point;
    marks[base] = {x: x - .02, y, visibility: .92};
    marks[base + 1] = {x: x + .02, y, visibility: .92};
  }
  return readFallEvidence(marks, 16 / 9);
}

const upright = evidence([.51, .24], [.51, .49], [.5, .65], [.51, .86]);
const seated = evidence([.51, .33], [.51, .56], [.66, .56], [.68, .86]);
const floor = evidence([.38, .80], [.53, .81], null, null);
const lyingOnBed = evidence([.38, .58], [.53, .56], [.62, .56], [.68, .57]);
const limited = evidence(null, [.53, .81], null, null);

function replay(rule, from, to, pose) {
  const states = [];
  for (let now = from; now <= to; now += 100) states.push(rule.update(pose, now));
  return states;
}

test('a seated fall can alert using clear shoulders and hips while feet are hidden', () => {
  const rule = new MotionFallRule();
  replay(rule, 0, 600, seated);
  const states = replay(rule, 700, 2400, floor);
  assert.equal(states.filter(state => state === 'new-alert').length, 1);
  assert.equal(states.at(-1), 'alert');
});

test('a brief descent followed by recovery does not raise an alert', () => {
  const rule = new MotionFallRule();
  replay(rule, 0, 600, upright);
  assert(!replay(rule, 700, 900, floor).includes('new-alert'));
  assert(!replay(rule, 1000, 2400, upright).includes('new-alert'));
});

test('insufficient visibility can never confirm a fall', () => {
  const rule = new MotionFallRule();
  assert.equal(limited, null);
  replay(rule, 0, 600, upright);
  assert(replay(rule, 700, 2100, limited).every(state => state === 'limited'));
  assert(!replay(rule, 2200, 4000, floor).includes('new-alert'));
});

test('lying down on a bed without a hip drop does not trigger a fall', () => {
  const rule = new MotionFallRule();
  replay(rule, 0, 600, seated);
  assert(!replay(rule, 700, 4000, lyingOnBed).includes('new-alert'));
});

test('a sustained floor event alerts only once and can rearm after recovery', () => {
  const rule = new MotionFallRule();
  replay(rule, 0, 600, upright);
  assert.equal(replay(rule, 700, 2800, floor).filter(state => state === 'new-alert').length, 1);
  replay(rule, 2900, 4000, upright);
  assert.equal(replay(rule, 4100, 6200, floor).filter(state => state === 'new-alert').length, 1);
});

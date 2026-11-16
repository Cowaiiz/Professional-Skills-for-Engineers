import assert from 'node:assert/strict';
import test from 'node:test';
import { FallRule, readPose } from '../dashboard/fall-rule.mjs';

const point = (x, y, visibility = 0.95) => ({x, y, visibility});
const upright = [point(.52, .24), point(.52, .49), point(.52, .69), point(.52, .90)];
const fallen = [point(.32, .82), point(.50, .84), point(.64, .84), point(.74, .84)];
const sitting = [point(.39, .39), point(.39, .63), point(.53, .64), point(.53, .89)];
const sofa = [point(.32, .59), point(.49, .62), point(.61, .63), point(.73, .64)];
const landmarks = joints => {
  const marks = Array(33).fill(null);
  [11, 23, 25, 27].forEach((index, i) => { marks[index] = joints[i]; });
  return marks;
};
const pose = joints => readPose(landmarks(joints), 1.33);

function during(rule, joints, start, end) {
  const states = [];
  for (let now = start; now <= end; now += 100) states.push(rule.update(joints && pose(joints), now));
  return states;
}

function armedRule() {
  const rule = new FallRule();
  assert.equal(during(rule, upright, 0, 800).at(-1), 'armed');
  return rule;
}

test('fast descent and three seconds near the floor fire once', () => {
  const rule = armedRule();
  assert(!during(rule, fallen, 900, 3800).includes('new-alert'));
  assert.equal(rule.update(pose(fallen), 3900), 'new-alert');
  assert(during(rule, fallen, 4000, 6000).every(state => state === 'alert'));
});

test('sitting and lying on a high sofa yield no fall', () => {
  assert(!during(armedRule(), sitting, 900, 4900).includes('new-alert'));
  assert(!during(armedRule(), sofa, 900, 4900).includes('new-alert'));
});

test('slow transition and a person already on the floor yield no fall', () => {
  const rule = armedRule();
  during(rule, sitting, 900, 2500);
  assert(!during(rule, fallen, 2600, 6000).includes('new-alert'));
  assert(!during(new FallRule(), fallen, 0, 3900).includes('new-alert'));
});

test('recovery before three seconds cancels the pending fall', () => {
  const rule = armedRule();
  during(rule, fallen, 900, 1900);
  assert(!during(rule, upright, 2000, 3000).includes('new-alert'));
  assert.equal(rule.update(pose(upright), 3100), 'armed');
});

test('a brief missed pose is not counted and recovery of tracking can confirm a fall', () => {
  const rule = armedRule();
  assert(!during(rule, fallen, 900, 2000).includes('new-alert'));
  assert.equal(rule.update(null, 2100), 'limited');
  assert(!during(rule, fallen, 2200, 3800).includes('new-alert'));
  assert.equal(rule.update(pose(fallen), 3900), 'new-alert');
});

test('a sustained occlusion or a long frame gap resets the fall candidate', () => {
  assert.equal(pose([fallen[0], fallen[1], fallen[2], point(.74, .84, .2)]), null);
  const rule = armedRule();
  during(rule, fallen, 900, 2000);
  assert(during(rule, null, 2100, 2600).every(state => state === 'limited'));
  assert(!during(rule, fallen, 2700, 6300).includes('new-alert'));
  const interrupted = armedRule();
  during(interrupted, fallen, 900, 1800);
  assert(!during(interrupted, fallen, 6500, 10300).includes('new-alert'));
});

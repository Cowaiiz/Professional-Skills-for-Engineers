import assert from 'node:assert/strict';
import test from 'node:test';
import {readPose} from '../dashboard/fall-rule.mjs';
import {PersonActivity, readPersonFrame} from '../dashboard/person-frame.mjs';

function landmarks(hipX = .48, sitting = false) {
  const marks = Array(33).fill(null);
  for (const [index, x, y] of [
    [0, hipX, .1], [11, hipX - .04, .21], [12, hipX + .04, .21],
    [23, hipX - .03, .47], [24, hipX + .03, .47],
    [25, hipX - .03, sitting ? .49 : .66], [26, hipX + .03, sitting ? .49 : .66],
    [27, hipX - .03, .89], [28, hipX + .03, .89],
  ]) {
    marks[index] = {x, y, visibility: .99};
  }
  return marks;
}

test('person box encloses visible joints and stays within the image', () => {
  const marks = landmarks(.03);
  const box = readPersonFrame(marks);
  assert.equal(box.x, 0);
  assert(box.y < .1 && box.y + box.height > .89);
  assert(box.x + box.width < .2);
  marks[11] = marks[12] = null;
  assert.equal(readPersonFrame(marks), null);
});

test('standing, walking, sitting and an alert use distinct labels', () => {
  const activity = new PersonActivity();
  const update = (marks, now, alarm = false) => activity.update(readPose(marks, 1.33), marks, now, alarm);
  assert.equal(update(landmarks(), 0), 'standing');
  assert.equal(update(landmarks(), 290), 'standing');
  assert.equal(update(landmarks(.56), 460), 'walking');
  assert.equal(update(landmarks(.56, true), 560), 'tracking');
  assert.equal(update(landmarks(.56, true), 960), 'sitting');
  assert.equal(update(landmarks(.56), 1060, true), 'fall');
  assert.equal(update(landmarks(.56), 1160), 'standing');
});

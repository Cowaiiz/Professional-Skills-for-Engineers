const visible = point => point && point.visibility >= 0.55 &&
  Number.isFinite(point.x) && Number.isFinite(point.y);
const clamp = value => Math.min(1, Math.max(0, value));
const joint = (marks, indices) => {
  const points = indices.map(index => marks[index]).filter(visible);
  if (!points.length) return null;
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  };
};

export function readPersonFrame(marks) {
  if (!marks || !joint(marks, [11, 12]) || !joint(marks, [23, 24])) return null;
  const points = marks.filter(visible);
  if (points.length < 6) return null;
  const xs = points.map(point => point.x);
  const ys = points.map(point => point.y);
  const left = Math.min(...xs);
  const top = Math.min(...ys);
  const right = Math.max(...xs);
  const bottom = Math.max(...ys);
  const padX = Math.max(0.012, (right - left) * 0.07);
  const padY = Math.max(0.012, (bottom - top) * 0.05);
  const x = clamp(left - padX);
  const y = clamp(top - padY);
  const width = clamp(right + padX) - x;
  const height = clamp(bottom + padY) - y;
  return width >= 0.035 && height >= 0.035 ? {x, y, width, height} : null;
}

export class PersonActivity {
  constructor() {
    this.reset();
  }

  reset() {
    this.uprightSamples = [];
    this.sittingSince = null;
  }

  update(pose, marks, now, alarm) {
    if (alarm || !pose || !marks) {
      this.reset();
      return alarm ? 'fall' : 'tracking';
    }
    const hip = joint(marks, [23, 24]);
    const torsoVertical = pose.hipY - pose.shoulderY;
    const sitting = [[23, 25, 27], [24, 26, 28]].some(indices => {
      const [sideHip, knee, ankle] = indices.map(index => marks[index]);
      return [sideHip, knee, ankle].every(visible) &&
        Math.abs(knee.y - sideHip.y) <= pose.torso * 0.3 &&
        ankle.y - knee.y >= pose.torso * 0.35;
    });
    if (torsoVertical >= pose.torso * 0.7 && sitting) {
      this.uprightSamples = [];
      this.sittingSince ??= now;
      return now - this.sittingSince >= 350 ? 'sitting' : 'tracking';
    }
    this.sittingSince = null;
    if (!pose.upright || !hip) {
      this.uprightSamples = [];
      return 'tracking';
    }
    // Compare hip movement and apparent size over roughly half a second.
    this.uprightSamples = this.uprightSamples.filter(sample => now - sample.at <= 650);
    const first = this.uprightSamples[0];
    this.uprightSamples.push({x: hip.x, torso: pose.torso, at: now});
    if (first && now - first.at >= 280 &&
      (Math.abs(hip.x - first.x) >= pose.torso * 0.17 ||
        Math.abs(pose.torso - first.torso) >= first.torso * 0.19)) return 'walking';
    return 'standing';
  }
}

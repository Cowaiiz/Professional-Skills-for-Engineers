const visible = point => point && point.visibility >= 0.55 &&
  point.x > 0.01 && point.x < 0.99 && point.y > 0.01 && point.y < 0.99;

export function readPose(points, aspect) {
  if (!points) return null;
  const sides = [[11, 23, 25, 27], [12, 24, 26, 28]]
    .map(indices => indices.map(index => points[index]))
    .filter(joints => joints.every(visible));
  if (!sides.length) return null;
  const centers = [0, 1, 2, 3].map(index => ({
    x: sides.reduce((total, side) => total + side[index].x, 0) / sides.length,
    y: sides.reduce((total, side) => total + side[index].y, 0) / sides.length,
  }));
  const [shoulder, hip, knee, ankle] = centers;
  const vertical = hip.y - shoulder.y;
  const horizontal = Math.abs(hip.x - shoulder.x) * aspect;
  const torso = Math.hypot(vertical, horizontal);
  if (torso < 0.065) return null;
  return {
    torso, hipY: hip.y, shoulderY: shoulder.y, footY: ankle.y,
    upright: vertical >= torso * 0.86 && knee.y - hip.y >= torso * 0.35 &&
      ankle.y - hip.y >= torso * 0.85,
    horizontal: horizontal >= torso * 0.82,
  };
}

// Fixed side-on camera, one person, with the floor and full body in view.
export class FallRule {
  constructor() {
    this.lastFrame = null;
    this.reset();
  }

  reset() {
    this.standSince = null;
    this.baseline = null;
    this.onFloorSince = null;
    this.alerted = false;
  }

  update(pose, now) {
    if (this.lastFrame !== null && now - this.lastFrame > 550) this.reset();
    this.lastFrame = now;
    if (!pose) {
      this.reset();
      return 'limited';
    }
    if (pose.upright) {
      if (this.onFloorSince !== null) this.baseline = null;
      this.standSince ??= now;
      this.onFloorSince = null;
      this.alerted = false;
      if (now - this.standSince >= 650) {
        this.baseline = {...pose, at: now};
        return 'armed';
      }
      return 'standing';
    }

    this.standSince = null;
    const ref = this.baseline;
    const low = ref && pose.horizontal &&
      pose.hipY - ref.hipY >= ref.torso * 0.50 &&
      pose.shoulderY - ref.shoulderY >= ref.torso * 0.85 &&
      Math.abs(ref.footY - pose.hipY) <= ref.torso * 0.60;
    if (!low) {
      if (this.onFloorSince !== null || (ref && now - ref.at > 1350)) this.baseline = null;
      this.onFloorSince = null;
      this.alerted = false;
      return ref ? 'tracking' : 'waiting';
    }
    if (this.onFloorSince === null) {
      if (now - ref.at > 1350) {
        this.baseline = null;
        return 'waiting';
      }
      this.onFloorSince = now;
    }
    if (this.alerted) return 'alert';
    if (now - this.onFloorSince < 3000) return 'checking';
    this.alerted = true;
    return 'new-alert';
  }
}

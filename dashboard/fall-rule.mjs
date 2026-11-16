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
const MAX_FRAME_GAP = 550;
const MAX_POSE_GAP = 450;
const TRANSITION_WINDOW = 1350;
const CONFIRM_WINDOW = 3000;
const MIN_LOW_EVIDENCE = 2400;

export class FallRule {
  constructor() {
    this.lastFrame = null;
    this.reset();
  }

  reset() {
    this.standSince = null;
    this.baseline = null;
    this.lastPoseAt = null;
    this.resetCandidate();
  }

  resetCandidate() {
    this.onFloorSince = null;
    this.lastLowAt = null;
    this.lowEvidence = 0;
    this.previousSampleLow = false;
    this.alerted = false;
  }

  update(pose, now) {
    const previousFrame = this.lastFrame;
    if (previousFrame !== null && now - previousFrame > MAX_FRAME_GAP) this.reset();
    this.lastFrame = now;
    if (this.lastPoseAt !== null && now - this.lastPoseAt > MAX_POSE_GAP) this.reset();
    if (this.lastLowAt !== null && now - this.lastLowAt > MAX_POSE_GAP) this.resetCandidate();

    if (!pose) {
      this.standSince = null;
      this.previousSampleLow = false;
      return 'limited';
    }
    this.lastPoseAt = now;
    if (pose.upright) {
      if (this.onFloorSince !== null) this.baseline = null;
      this.standSince ??= now;
      this.resetCandidate();
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
      Math.abs(ref.footY - pose.hipY) <= ref.torso * 0.75;
    if (!low) {
      this.previousSampleLow = false;
      if (this.onFloorSince !== null) return 'checking';
      if (ref && now - ref.at > TRANSITION_WINDOW) this.baseline = null;
      return this.baseline ? 'tracking' : 'waiting';
    }
    if (this.onFloorSince === null) {
      if (now - ref.at > TRANSITION_WINDOW) {
        this.baseline = null;
        return 'waiting';
      }
      this.onFloorSince = now;
    }
    // Brief tracking noise is tolerated. Only adjacent low poses add evidence.
    if (this.previousSampleLow) this.lowEvidence += now - previousFrame;
    this.previousSampleLow = true;
    this.lastLowAt = now;
    if (this.alerted) return 'alert';
    if (now - this.onFloorSince < CONFIRM_WINDOW || this.lowEvidence < MIN_LOW_EVIDENCE) return 'checking';
    this.alerted = true;
    return 'new-alert';
  }
}

const tracked = (point, limit) => point && point.visibility >= limit &&
  point.x > -0.01 && point.x < 1.01 && point.y > -0.01 && point.y < 1.01;

function center(points, ids, limit) {
  const visible = ids.map(id => points[id]).filter(point => tracked(point, limit));
  if (!visible.length) return null;
  return {
    x: visible.reduce((sum, point) => sum + point.x, 0) / visible.length,
    y: visible.reduce((sum, point) => sum + point.y, 0) / visible.length,
  };
}

export function readFallEvidence(points, aspect) {
  if (!points) return null;
  const shoulders = center(points, [11, 12], .48);
  const hips = center(points, [23, 24], .48);
  if (!shoulders || !hips) return null;
  const footYs = [27, 28, 29, 30, 31, 32].map(id => points[id])
    .filter(point => tracked(point, .55)).map(point => point.y);
  const foot = footYs.length ? Math.max(...footYs) : null;
  const vertical = hips.y - shoulders.y;
  const horizontal = (hips.x - shoulders.x) * aspect;
  const scale = Math.hypot(vertical, horizontal);
  if (scale < .045) return null;
  return {
    scale, torsoUpright: vertical / scale,
    centroidY: (hips.y + shoulders.y) / 2,
    hipY: hips.y, shoulderY: shoulders.y, footY: foot,
    elevated: foot !== null && foot - hips.y >= scale * .52,
  };
}

const motionThresholds = {
  anchorCosine: .70,
  descentWindow: 1800,
  settleWindow: 800,
  evidence: 400,
  riseTolerance: .5,
  maxGap: 600,
  settleCosine: .75,
  initiateCosine: .75,
  downward: .68,
  hipDrop: .25,
  footMargin: .79,
  quickDrop: .35,
  stableAnchor: 100,
};

// Compare the last upright torso with a quick drop and a sustained low, tilted pose.
export class MotionFallRule {
  constructor() {
    this.reset();
  }

  reset() {
    this.previous = null;
    this.previousAt = null;
    this.anchorSince = null;
    this.anchors = [];
    this.candidate = null;
    this.alerted = false;
    this.recoverSince = null;
  }

  update(pose, now) {
    const c = motionThresholds;
    if (this.previousAt !== null && now - this.previousAt > c.maxGap) this.reset();
    this.anchors = this.anchors.filter(anchor => now - anchor.at <= c.descentWindow);
    if (this.candidate && now - this.candidate.lastLowAt > c.maxGap) {
      this.candidate = null;
    }
    if (!pose) {
      this.previous = null;
      this.anchorSince = null;
      this.recoverSince = null;
      return 'limited';
    }
    const delta = this.previousAt === null ? 0 : now - this.previousAt;
    const previous = this.previous;
    this.previousAt = now;
    this.previous = pose;
    const isVertical = pose.torsoUpright >= c.anchorCosine;
    if (isVertical) {
      this.anchorSince ??= now;
      this.recoverSince ??= now;
      if (now - this.recoverSince >= 550) this.alerted = false;
    } else {
      this.recoverSince = null;
      this.anchorSince = null;
    }

    if (this.candidate) {
      const candidate = this.candidate;
      const risen = pose.centroidY < candidate.maxCentroid - candidate.ref.scale * c.riseTolerance;
      if (risen || (isVertical && pose.elevated)) {
        this.candidate = null;
      } else if (pose.torsoUpright <= c.settleCosine) {
        candidate.maxCentroid = Math.max(candidate.maxCentroid, pose.centroidY);
        candidate.lastLowAt = now;
        if (previous && previous.torsoUpright <= c.settleCosine && delta <= 260) {
          candidate.evidence += delta;
        }
        if (this.alerted) return 'alert';
        if (now - candidate.startedAt >= c.settleWindow && candidate.evidence >= c.evidence) {
          this.alerted = true;
          return 'new-alert';
        }
        return 'checking';
      } else {
        return 'checking';
      }
    }

    if (!this.alerted && pose.torsoUpright <= c.initiateCosine) {
      const ref = this.anchors.find(anchor => {
        const scale = anchor.scale;
        const duration = now - anchor.at;
        if (duration < 180) return false;
        const shoulderDrop = (pose.shoulderY - anchor.shoulderY) / scale;
        const hipDrop = (pose.hipY - anchor.hipY) / scale;
        const centroidDrop = (pose.centroidY - anchor.centroidY) / scale;
        const nearFoot = anchor.footY !== null && anchor.footY - pose.hipY <= scale * c.footMargin;
        const currentFloor = pose.footY !== null && pose.footY - pose.hipY <= scale * c.footMargin;
        const fast = centroidDrop >= c.quickDrop * duration / 650;
        return shoulderDrop >= c.downward && hipDrop >= c.hipDrop && fast &&
          (nearFoot || currentFloor || centroidDrop >= .96);
      });
      if (ref) {
        this.candidate = {ref, startedAt: now, lastLowAt: now, evidence: 0, maxCentroid: pose.centroidY};
        return 'checking';
      }
    }
    if (isVertical && !this.alerted && now - this.anchorSince >= c.stableAnchor) {
      this.anchors.push({...pose, at: now});
      return 'armed';
    }
    return isVertical ? 'standing' : 'tracking';
  }
}

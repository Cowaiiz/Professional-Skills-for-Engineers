import { FilesetResolver, PoseLandmarker } from './vendor/mediapipe/vision_bundle.mjs';
import { FallRule, readPose } from './fall-rule.mjs';

const edges = [[11, 12], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28]];
const labels = {
  limited: 'Limited view · show one person from shoulders to feet.',
  standing: 'Hold a standing position to calibrate.',
  armed: 'Fall detection ready.',
  tracking: 'Tracking body position.',
  waiting: 'Stand fully in frame to arm fall detection.',
  checking: 'Checking for a sustained position near the floor…',
  alert: 'Possible fall · check whether the person needs help.',
};

function drawPose(canvas, video, marks, alarm) {
  const width = video.clientWidth;
  const height = video.clientHeight;
  if (!width || !height) return;
  canvas.width = width;
  canvas.height = height;
  if (!marks) return;
  const ctx = canvas.getContext('2d');
  const scale = Math.min(width / video.videoWidth, height / video.videoHeight);
  const drawnWidth = video.videoWidth * scale;
  const drawnHeight = video.videoHeight * scale;
  const left = (width - drawnWidth) / 2;
  const top = (height - drawnHeight) / 2;
  ctx.strokeStyle = alarm ? '#ff637d' : '#7bf1dc';
  ctx.lineWidth = 3;
  for (const [i, j] of edges) {
    const a = marks[i], b = marks[j];
    if (a.visibility < 0.55 || b.visibility < 0.55) continue;
    ctx.beginPath();
    ctx.moveTo(left + a.x * drawnWidth, top + a.y * drawnHeight);
    ctx.lineTo(left + b.x * drawnWidth, top + b.y * drawnHeight);
    ctx.stroke();
  }
}

export async function startFallPreview({video, canvas, status, onAlert, signal}) {
  const assets = './vendor/mediapipe/';
  const wasm = await FilesetResolver.forVisionTasks(new URL(assets + 'wasm', import.meta.url).href);
  if (signal.aborted) return;
  const poseModel = await PoseLandmarker.createFromOptions(wasm, {
    baseOptions: {
      modelAssetPath: new URL(assets + 'pose_landmarker_lite.task', import.meta.url).href,
      delegate: 'CPU',
    },
    runningMode: 'VIDEO',
    numPoses: 2,
  });
  if (signal.aborted) {
    poseModel.close();
    return;
  }
  const rule = new FallRule();
  let frame;
  let last = -Infinity;
  let lastVideoTime = -1;
  let closed = false;
  const cleanup = () => {
    if (closed) return;
    closed = true;
    cancelAnimationFrame(frame);
    poseModel.close();
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  };
  signal.addEventListener('abort', cleanup, {once: true});

  function detect(now) {
    if (closed) return;
    if (video.readyState >= 2 && now - last >= 100 && video.currentTime !== lastVideoTime) {
      last = now;
      lastVideoTime = video.currentTime;
      try {
        const {landmarks} = poseModel.detectForVideo(video, now);
        const marks = landmarks.length === 1 ? landmarks[0] : null;
        const pose = readPose(marks, video.videoWidth / video.videoHeight);
        const state = rule.update(pose, now);
        const alarm = state === 'alert' || state === 'new-alert';
        const label = landmarks.length > 1 ? 'Multiple people in view · show one person.' :
          labels[alarm ? 'alert' : state];
        if (status.textContent !== label) status.textContent = label;
        status.dataset.state = alarm ? 'alert' : state;
        drawPose(canvas, video, pose ? marks : null, alarm);
        if (state === 'new-alert') onAlert();
      } catch {
        cleanup();
        status.textContent = 'Pose detection paused. Switch to Demo camera and reopen My camera to retry.';
        status.dataset.state = 'limited';
        return;
      }
    }
    frame = requestAnimationFrame(detect);
  }
  status.textContent = 'Show one person from shoulders to feet.';
  frame = requestAnimationFrame(detect);
}

import { FilesetResolver, PoseLandmarker } from './vendor/mediapipe/vision_bundle.mjs';
import { MotionFallRule, readFallEvidence, readPose } from './fall-rule.mjs';
import { PersonActivity, readPersonFrame } from './person-frame.mjs';

const labels = {
  limited: 'Limited view · keep the shoulders and hips visible.',
  standing: 'Monitoring movement.',
  armed: 'Fall detection ready.',
  tracking: 'Monitoring movement.',
  checking: 'Checking a possible fall…',
  alert: 'Possible fall · check whether the person needs help.',
};
const captions = {
  fall: 'Fall Detected',
  walking: 'Walking',
  standing: 'Standing',
  sitting: 'Sitting',
  tracking: 'Tracking',
};

function showPersonFrame(overlay, video, frame, activity) {
  const {clientWidth, clientHeight, videoWidth, videoHeight} = video;
  if (!frame || !clientWidth || !clientHeight || !videoWidth || !videoHeight) {
    overlay.setAttribute('hidden', '');
    return;
  }
  const [box, tag, label] = overlay.children;
  const scale = Math.min(clientWidth / videoWidth, clientHeight / videoHeight);
  const width = videoWidth * scale;
  const height = videoHeight * scale;
  const left = (clientWidth - width) / 2;
  const top = (clientHeight - height) / 2;
  const x = left + frame.x * width;
  const y = top + frame.y * height;
  const viewBox = '0 0 ' + clientWidth + ' ' + clientHeight;
  if (overlay.getAttribute('viewBox') !== viewBox) overlay.setAttribute('viewBox', viewBox);
  overlay.removeAttribute('hidden');
  if (overlay.dataset.activity !== activity) overlay.dataset.activity = activity;
  box.setAttribute('x', x);
  box.setAttribute('y', y);
  box.setAttribute('width', frame.width * width);
  box.setAttribute('height', frame.height * height);
  if (label.textContent !== captions[activity]) {
    label.textContent = captions[activity];
    tag.setAttribute('width', Math.ceil(label.getComputedTextLength()) + 12);
  }
  const tagWidth = Number(tag.getAttribute('width'));
  const tagX = Math.max(left, Math.min(x, left + width - tagWidth));
  const tagY = y - top >= 19 ? y - 19 : y;
  tag.setAttribute('x', tagX);
  tag.setAttribute('y', tagY);
  label.setAttribute('x', tagX + 6);
  label.setAttribute('y', tagY + 14);
}

export async function startFallPreview({video, overlay, status, onAlert, signal, dataset = false}) {
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
  const rule = new MotionFallRule();
  const classifier = new PersonActivity();
  let personFrame = null;
  let activity = 'tracking';
  let frame;
  let last = -Infinity;
  let lastVideoTime = -Infinity;
  let closed = false;
  const showState = (state, label) => {
    if (status.textContent !== label) status.textContent = label;
    if (status.dataset.state !== state) status.dataset.state = state;
  };
  const renderPerson = () => showPersonFrame(overlay, video, personFrame, activity);
  const observer = new ResizeObserver(renderPerson);
  observer.observe(video);
  const resetAfterSeek = () => {
    rule.reset();
    classifier.reset();
    personFrame = null;
    renderPerson();
    lastVideoTime = -Infinity;
    showState('tracking', 'Position changed · play from before the movement to check for a fall.');
  };
  const cleanup = () => {
    if (closed) return;
    closed = true;
    cancelAnimationFrame(frame);
    observer.disconnect();
    video.removeEventListener('seeking', resetAfterSeek);
    poseModel.close();
    overlay.setAttribute('hidden', '');
  };
  signal.addEventListener('abort', cleanup, {once: true});
  if (dataset) video.addEventListener('seeking', resetAfterSeek);

  function detect(now) {
    if (closed) return;
    const time = video.currentTime;
    const advancing = dataset ? !video.paused && !video.seeking && (time - lastVideoTime) >= 0.099 :
      now - last >= 100 && time !== lastVideoTime;
    if (video.readyState >= 2 && advancing) {
      last = now;
      lastVideoTime = time;
      try {
        const {landmarks} = poseModel.detectForVideo(video, now);
        const marks = landmarks.length === 1 ? landmarks[0] : null;
        const aspect = video.videoWidth / video.videoHeight;
        const pose = readPose(marks, aspect);
        if (landmarks.length > 1) rule.reset();
        const timestamp = dataset ? time * 1000 : now;
        const state = rule.update(readFallEvidence(marks, aspect), timestamp);
        const alarm = state === 'alert' || state === 'new-alert';
        personFrame = readPersonFrame(marks);
        activity = classifier.update(state === 'checking' ? null : pose, marks, timestamp, alarm);
        renderPerson();
        const label = landmarks.length > 1 ? 'Limited view · multiple people detected.' :
          dataset && state === 'limited' ? 'Limited view · the shoulders or hips are hard to see.' :
          labels[alarm ? 'alert' : state];
        const activeLabel = activity === 'walking' || activity === 'sitting' ? captions[activity] + ' · ' : '';
        showState(alarm ? 'alert' : state, activeLabel + label);
        if (state === 'new-alert') onAlert();
      } catch {
        cleanup();
        showState('limited', dataset ? 'Fall detection stopped. Switch sources and reopen the clip to retry.' :
          'Fall detection stopped. Stop and restart the camera to retry.');
        return;
      }
    }
    frame = requestAnimationFrame(detect);
  }
  showState('tracking', dataset ? 'Press Play to analyze this clip.' : 'Keep one person in view, including shoulders and hips.');
  frame = requestAnimationFrame(detect);
}

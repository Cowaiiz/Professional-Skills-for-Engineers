const element = id => document.getElementById(id);
const buttons = {
  live: element('camera-mode-live'),
  dataset: element('camera-mode-dataset'),
};
const webcamControls = element('camera-webcam-controls');
const datasetControls = element('camera-dataset-controls');
const cameraToggle = element('camera-toggle');
const catalogStatus = element('camera-catalog-status');
const category = element('camera-category');
const clips = element('camera-clip');
const caption = element('camera-clip-caption');
const videoFile = element('camera-video-file');
const video = element('camera-video');
const overlay = element('camera-person-overlay');
const empty = element('camera-empty');
const emptyTitle = element('camera-empty-title');
const emptyHelp = element('camera-empty-help');
const previewStatus = element('camera-live-status');
const fallEvents = element('live-camera-events');
const examples = new Set(['subject-4-fall-07', 'subject-1-adl-13']);

let mode = 'dataset';
let stream = null;
let objectUrl = null;
let requestingCamera = false;
let mediaRequest = 0;
let poseSession = null;
let library = null;
let fetchingLibrary = false;

function stopMedia() {
  mediaRequest += 1;
  requestingCamera = false;
  poseSession?.abort();
  poseSession = null;
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  video.pause();
  video.srcObject = null;
  if (video.hasAttribute('src')) {
    video.removeAttribute('src');
    video.load();
  }
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = null;
  video.hidden = true;
  video.controls = false;
  empty.hidden = false;
  overlay.setAttribute('hidden', '');
  previewStatus.textContent = '';
  delete previewStatus.dataset.state;
  fallEvents.replaceChildren();
  cameraToggle.textContent = 'Start camera';
}

function selectMode(next) {
  if (next === mode) return;
  stopMedia();
  mode = next;
  datasetControls.hidden = mode !== 'dataset';
  webcamControls.hidden = mode !== 'live';
  for (const [name, button] of Object.entries(buttons)) {
    button.setAttribute('aria-pressed', String(name === mode));
  }
  clips.value = '';
  caption.hidden = true;
  if (mode === 'live') {
    emptyTitle.textContent = 'Camera off';
    emptyHelp.textContent = 'Start the camera to check for possible falls.';
  } else {
    emptyTitle.textContent = 'Choose a video clip';
    emptyHelp.textContent = 'Select a dataset clip or open a local video.';
    void loadCatalog();
  }
}

function populateClips() {
  const visible = [...library.values()].filter(item => category.value === 'all' || item.category === category.value);
  clips.replaceChildren(new Option('Choose a clip', ''));
  const groups = new Map();
  for (const item of visible) {
    const name = examples.has(item.id) ? 'Suggested clips' : item.subject;
    if (!groups.has(name)) {
      const group = document.createElement('optgroup');
      group.label = name;
      groups.set(name, group);
    }
    const number = item.id.split('-').at(-1);
    const type = item.category === 'fall' ? 'Fall' : 'Daily activity';
    const prefix = examples.has(item.id) ? item.subject + ' · ' : '';
    groups.get(name).append(new Option(prefix + type + ' ' + number + ' · ' + item.title, item.id));
  }
  const suggested = groups.get('Suggested clips');
  groups.delete('Suggested clips');
  if (suggested) clips.append(suggested);
  clips.append(...groups.values());
  clips.disabled = visible.length === 0;
  catalogStatus.textContent = '';
  if (visible.length || library.size) {
    catalogStatus.append(visible.length + (visible.length === 1 ? ' clip · ' : ' clips · '));
    const credit = document.createElement('a');
    credit.href = 'https://doi.org/10.5281/zenodo.13354453';
    credit.target = '_blank';
    credit.rel = 'noopener';
    credit.textContent = 'GMDCSA-24 v2.1';
    catalogStatus.append(credit);
  } else {
    catalogStatus.textContent = 'No hosted clips available. You can open a local video.';
  }
}

async function loadCatalog() {
  if (library || fetchingLibrary) return;
  fetchingLibrary = true;
  catalogStatus.textContent = 'Loading the GMDCSA-24 catalog…';
  try {
    const response = await fetch('/api/camera/clips', {headers: {Accept: 'application/json'}});
    if (!response.ok) throw Error('Unexpected catalog response');
    const payload = await response.json();
    library = new Map(payload.clips
      .filter(item => /^\/media\/gmdcsa24\/[a-z0-9-]+\.mp4$/.test(item?.url))
      .map(item => [item.id, item]));
    category.disabled = library.size === 0;
    populateClips();
  } catch {
    library = null;
    catalogStatus.textContent = 'Could not load the catalog. You can open a local video.';
  } finally {
    fetchingLibrary = false;
  }
}

async function toggleCamera() {
  if (stream || requestingCamera) {
    stopMedia();
    return;
  }
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    previewStatus.textContent = 'Camera access needs HTTPS or localhost.';
    return;
  }
  const request = mediaRequest;
  requestingCamera = true;
  cameraToggle.textContent = 'Cancel';
  previewStatus.textContent = 'Allow camera access to start.';
  try {
    const capture = await navigator.mediaDevices.getUserMedia({video: true, audio: false});
    if (request !== mediaRequest) {
      capture.getTracks().forEach(track => track.stop());
      return;
    }
    requestingCamera = false;
    stream = capture;
    cameraToggle.textContent = 'Stop camera';
    capture.getVideoTracks().forEach(track => track.addEventListener('ended', () => {
      if (stream !== capture) return;
      stopMedia();
      previewStatus.textContent = 'Camera disconnected. Reconnect it and start again.';
    }, {once: true}));
    video.srcObject = capture;
    video.hidden = false;
    empty.hidden = true;
    await video.play();
    if (request === mediaRequest) void detectFalls(request, false);
  } catch (error) {
    if (request !== mediaRequest) return;
    stopMedia();
    if (error.name === 'NotAllowedError') {
      previewStatus.textContent = 'Camera access was blocked. Allow it in your browser settings and try again.';
    } else if (error.name === 'NotFoundError') {
      previewStatus.textContent = 'No camera was found on this device.';
    } else {
      previewStatus.textContent = 'Could not start the camera. Close other apps using it and try again.';
    }
  }
}

function openClip(url, name, file) {
  stopMedia();
  if (file) objectUrl = URL.createObjectURL(file);
  caption.textContent = name;
  caption.hidden = false;
  video.src = objectUrl || url;
  video.hidden = false;
  empty.hidden = true;
  void detectFalls(mediaRequest, true);
}

async function detectFalls(request, dataset) {
  const session = new AbortController();
  poseSession = session;
  previewStatus.textContent = 'Loading the on-device pose model…';
  try {
    const {startFallPreview} = await import('./camera-live-fall.js');
    if (session.signal.aborted) return;
    await startFallPreview({
      video,
      overlay,
      status: previewStatus,
      signal: session.signal,
      dataset,
      onAlert: () => {
        const item = document.createElement('li');
        const seconds = Math.floor(video.currentTime);
        const time = dataset
          ? Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0')
          : new Date().toLocaleTimeString();
        item.textContent = time + ' · Possible fall detected';
        fallEvents.prepend(item);
        if (fallEvents.children.length > 8) fallEvents.lastElementChild.remove();
      },
    });
  } catch {
    if (request === mediaRequest) {
      previewStatus.textContent = dataset ? 'Fall detection unavailable. Reopen the video to retry.' :
        'Fall detection unavailable. Stop and restart the camera to retry.';
      previewStatus.dataset.state = 'limited';
    }
  } finally {
    if (request === mediaRequest && dataset) video.controls = true;
  }
}

for (const [name, button] of Object.entries(buttons)) {
  button.addEventListener('click', () => selectMode(name));
}
cameraToggle.addEventListener('click', toggleCamera);
category.addEventListener('change', () => {
  const current = clips.value;
  populateClips();
  if ([...clips.options].some(option => option.value === current)) {
    clips.value = current;
  } else {
    stopMedia();
    caption.hidden = true;
  }
});
clips.addEventListener('change', () => {
  const clip = library?.get(clips.value);
  if (clip) {
    openClip(clip.url, clip.subject + ' · ' + clip.title);
  } else {
    stopMedia();
    caption.hidden = true;
  }
});
element('camera-open-file').addEventListener('click', () => videoFile.click());
videoFile.addEventListener('change', () => {
  const file = videoFile.files[0];
  if (!file) return;
  clips.value = '';
  videoFile.value = '';
  openClip(null, file.name, file);
});
video.addEventListener('error', () => {
  if (mode !== 'dataset' || !video.hasAttribute('src') || !video.error) return;
  const local = Boolean(objectUrl);
  stopMedia();
  clips.value = '';
  caption.hidden = true;
  previewStatus.textContent = local ? 'Could not open this video. Try a compatible MP4 or WebM.' :
    'Could not load this clip. Choose it again or open a local video.';
});
window.addEventListener('pagehide', () => {
  stopMedia();
  clips.value = '';
  caption.hidden = true;
});
void loadCatalog();

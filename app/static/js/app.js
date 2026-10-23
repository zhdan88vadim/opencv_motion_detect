import { api } from './api.js';
import { createStore } from './store.js';
import { connectSSE } from './sse.js';
import { RoiCanvas } from './roi.js';
import { attachStream } from './stream.js';
import { Alerts, CameraAudio } from './audio.js';

const $ = (id) => document.getElementById(id);

const store = createStore({
  camera: '', cameras: {}, hasAudio: false,
  detection: true, recording: false, recordingEnabled: false,
  motion: false, motionArea: 0,
  threshold: 200, minArea: 5,
  roi: { x: 0, y: 0, width: 1, height: 1, enabled: false },
  connected: false,
});

const stream = attachStream($('stream'), $('mask'));
const roiCanvas = new RoiCanvas($('roiCanvas'), $('stream'), async (roi) => {
  try {
    await api.setRoi(store.get().camera, roi);
    store.set({ roi });
    toast('ROI saved');
  } catch (e) { toast('ROI save failed: ' + e.message, 'error'); }
});
const alerts = new Alerts();
const camAudio = new CameraAudio($('camAudio'));

function toast(msg, kind = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${kind === 'error' ? 'toast--error' : kind === 'warn' ? 'toast--warn' : ''}`;
  el.textContent = msg;
  $('toasts').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function renderPills(s) {
  const conn = $('pill-conn');
  conn.textContent = s.connected ? 'connected' : 'offline';
  conn.className = `pill ${s.connected ? 'pill--ok' : 'pill--danger'}`;

  $('pill-cam').textContent = s.camera || '—';

  const mo = $('pill-motion');
  mo.textContent = s.motion ? `motion ${s.motionArea.toFixed(0)}` : 'no motion';
  mo.className = `pill ${s.motion ? 'pill--danger' : ''}`;

  const rec = $('pill-rec');
  rec.textContent = s.recording ? 'recording' : 'rec off';
  rec.className = `pill ${s.recording ? 'pill--danger' : ''}`;

  $('btnDetection').textContent = `Detection: ${s.detection ? 'on' : 'off'}`;
  $('btnDetection').classList.toggle('is-off', !s.detection);

  $('btnRecord').textContent = `Record: ${s.recordingEnabled ? 'on' : 'off'}`;
  $('btnRecord').classList.toggle('is-off', !s.recordingEnabled);

  $('btnRoiToggle').textContent = s.roi.enabled ? 'Disable ROI' : 'Enable ROI';
  $('btnRoiToggle').classList.toggle('is-off', !s.roi.enabled);

  $('roiX').value = s.roi.x.toFixed(2);
  $('roiY').value = s.roi.y.toFixed(2);
  $('roiW').value = s.roi.width.toFixed(2);
  $('roiH').value = s.roi.height.toFixed(2);

  // Values from server. Don't fight the user while they're dragging.
  $('thrVal').textContent = s.threshold;
  $('minVal').textContent = s.minArea;
  if (document.activeElement !== $('threshold')) $('threshold').value = s.threshold;
  if (document.activeElement !== $('minArea')) $('minArea').value = s.minArea;

  const btnAudio = $('btnAudio');
  if (!s.hasAudio) {
    btnAudio.disabled = true;
    btnAudio.classList.add('is-off');
    btnAudio.textContent = 'Camera audio: unavailable';
  } else {
    btnAudio.disabled = false;
    btnAudio.textContent = camAudio.playing ? 'Camera audio: on' : 'Camera audio: off';
    btnAudio.classList.toggle('is-off', !camAudio.playing);
  }
}

store.subscribe(s => {
  renderPills(s);
  roiCanvas.setRoi(s.roi);
});

connectSSE('/events', (msg) => {
  if (msg.kind === 'status') {
    const prev = store.get();
    store.set({
      camera: msg.camera_name ?? prev.camera,
      motion: msg.motion_detected,
      motionArea: msg.motion_area,
      threshold: msg.threshold,
      minArea: msg.min_area,
      detection: msg.detection_enabled,
      recording: msg.recording,
      recordingEnabled: msg.recording_enabled,
      hasAudio: msg.has_audio,
    });
    if (msg.motion_detected && !prev.motion) alerts.startMotion();
    if (!msg.motion_detected && prev.motion) alerts.stopMotion();
  } else if (msg.kind === 'camera') {
    store.set({ camera: msg.camera_name });
    loadCameraSettings(msg.camera_name);
    if (camAudio.playing) {
      camAudio.stop();
      toast('Camera audio stopped (camera changed)');
    }
  }
}, (state) => store.set({ connected: state === 'open' }));

async function loadCameras() {
  const data = await api.cameras();
  const sel = $('cameraSelect');
  sel.innerHTML = '';
  for (const [name, cfg] of Object.entries(data.cameras)) {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    opt.dataset.audio = cfg.has_audio ? '1' : '0';
    if (name === data.selected) opt.selected = true;
    sel.appendChild(opt);
  }
  store.set({ cameras: data.cameras, camera: data.selected });
  await loadCameraSettings(data.selected);
}

async function loadCameraSettings(camera) {
  try {
    const [roi, params] = await Promise.all([
      api.getRoi(camera),
      api.getParams(camera),
    ]);
    store.set({ roi, threshold: params.threshold, minArea: params.min_area });
    $('threshold').value = params.threshold;
    $('minArea').value = params.min_area;
    $('thrVal').textContent = params.threshold;
    $('minVal').textContent = params.min_area;
  } catch (e) {
    toast('Camera settings load failed', 'error');
  }
}

$('cameraSelect').addEventListener('change', async (e) => {
  const name = e.target.value;
  try {
    await api.switchCamera(name);
    store.set({ camera: name });
    await loadCameraSettings(name);
    stream.reload();
    toast(`Switched to ${name}`);
  } catch (err) { toast('Switch failed: ' + err.message, 'error'); }
});

$('btnDetection').addEventListener('click', async () => {
  const next = !store.get().detection;
  await api.setDetection(next); store.set({ detection: next });
});

$('btnRecord').addEventListener('click', async () => {
  const next = !store.get().recordingEnabled;
  await api.setRecording(next); store.set({ recordingEnabled: next });
});

$('btnAudio').addEventListener('click', async () => {
  const on = await camAudio.toggle();
  if (on) toast('Camera audio playing');
  else if (camAudio.available) toast('Camera audio stopped');
  else toast('Camera audio unavailable for this stream', 'warn');
  renderPills(store.get());
});

$('btnRoiToggle').addEventListener('click', async () => {
  const roi = { ...store.get().roi, enabled: !store.get().roi.enabled };
  await api.setRoi(store.get().camera, roi);
  store.set({ roi });
});

$('btnRoiDraw').addEventListener('click', () => {
  const active = !$('roiCanvas').classList.contains('drawing');
  roiCanvas.setMode(active);
  $('drawHint').hidden = !active;
  $('btnRoiDraw').classList.toggle('is-off', !active);
});

$('btnRoiReset').addEventListener('click', async () => {
  if (!confirm('Reset ROI to full frame?')) return;
  const roi = await api.resetRoi(store.get().camera);
  store.set({ roi });
  toast('ROI reset');
});

let sliderTimer = null;
function debounceParams() {
  clearTimeout(sliderTimer);
  sliderTimer = setTimeout(async () => {
    const threshold = Number($('threshold').value);
    const minArea = Number($('minArea').value);
    store.set({ threshold, minArea });
    try {
      const data = await api.setParams(store.get().camera, threshold, minArea);
      // Server echo — authoritative.
      $('thrVal').textContent = data.threshold;
      $('minVal').textContent = data.min_area;
    } catch (e) {
      toast('Save failed: ' + e.message, 'error');
    }
  }, 200);
}
$('threshold').addEventListener('input', () => {
  $('thrVal').textContent = $('threshold').value;
  debounceParams();
});
$('minArea').addEventListener('input', () => {
  $('minVal').textContent = $('minArea').value;
  debounceParams();
});

['roiX', 'roiY', 'roiW', 'roiH'].forEach(id => {
  $(id).addEventListener('change', async () => {
    const roi = {
      x: Number($('roiX').value), y: Number($('roiY').value),
      width: Number($('roiW').value), height: Number($('roiH').value),
      enabled: store.get().roi.enabled,
    };
    try {
      await api.setRoi(store.get().camera, roi);
      store.set({ roi });
    } catch (e) { toast('ROI invalid', 'error'); }
  });
});

loadCameras().catch(e => toast('Init failed: ' + e.message, 'error'));

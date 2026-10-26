async function call(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${text || res.statusText}`);
  }
  return res.json().catch(() => null);
}

export const api = {
  cameras: () => call('/api/cameras'),
  switchCamera: (name) => call('/api/camera', { method: 'POST', body: JSON.stringify({ name }) }),
  setDetection: (enabled) => call('/api/detection', { method: 'POST', body: JSON.stringify({ enabled }) }),
  setRecording: (enabled) => call('/api/recording', { method: 'POST', body: JSON.stringify({ enabled }) }),
  setParams: (camera_name, threshold, min_area) =>
    call('/api/params', {
      method: 'POST',
      body: JSON.stringify({ camera_name, threshold, min_area }),
    }),
  getParams: (name) => call(`/api/params/${encodeURIComponent(name)}`),
  getPanelMode: () => call('/api/panel'),
  setPanelMode: (mode) => call('/api/panel', { method: 'POST', body: JSON.stringify({ mode }) }),
  getRoi: (name) => call(`/api/roi/${encodeURIComponent(name)}`),
  setRoi: (camera_name, roi) =>
    call('/api/roi', { method: 'POST', body: JSON.stringify({ camera_name, roi }) }),
  resetRoi: (name) => call(`/api/roi/${encodeURIComponent(name)}/reset`, { method: 'POST' }),
  recordings: () => call('/api/recordings'),
};

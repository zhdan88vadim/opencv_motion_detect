export function attachStream(imgEl, panelEl) {
  let mode = 'mask';
  const panelUrl = () => `/panel.mjpg?t=${Date.now()}&m=${mode}`;

  imgEl.src = `/stream.mjpg?t=${Date.now()}`;
  if (panelEl) panelEl.src = panelUrl();

  return {
    reload() {
      imgEl.src = `/stream.mjpg?t=${Date.now()}`;
    },
    setPanelMode(next) {
      if (next === mode) return;
      mode = next;
      if (panelEl) panelEl.src = panelUrl();
    },
  };
}

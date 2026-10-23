export function attachStream(imgEl, maskEl) {
  imgEl.src = `/stream.mjpg?t=${Date.now()}`;
  if (maskEl) maskEl.src = `/mask.mjpg?t=${Date.now()}`;
  return {
    reload() {
      imgEl.src = `/stream.mjpg?t=${Date.now()}`;
      if (maskEl) maskEl.src = `/mask.mjpg?t=${Date.now()}`;
    },
  };
}

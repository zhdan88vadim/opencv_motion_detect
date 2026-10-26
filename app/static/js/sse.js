export function connectSSE(url, onEvent, onState) {
  let es = null, backoff = 1000, stopped = false;

  const open = () => {
    es = new EventSource(url);
    es.onopen = () => { backoff = 1000; onState?.('open'); };
    es.onerror = () => {
      onState?.('error');
      es.close();
      if (stopped) return;
      setTimeout(open, backoff);
      backoff = Math.min(backoff * 1.5, 15000);
    };
    es.onmessage = (ev) => {
      try { onEvent(JSON.parse(ev.data)); } catch {}
    };
  };
  open();
  return { close() { stopped = true; es?.close(); } };
}

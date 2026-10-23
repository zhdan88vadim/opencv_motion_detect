// Beep alerts for motion. Unchanged from before.
export class Alerts {
  constructor() {
    this.ctx = null; this.interval = null; this.enabled = true;
  }
  _init() {
    if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === 'suspended') this.ctx.resume();
    return this.ctx;
  }
  beep(freq = 880, dur = 0.12, vol = 0.25) {
    if (!this.enabled) return;
    const ctx = this._init();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = freq;
    g.gain.setValueAtTime(0, ctx.currentTime);
    g.gain.linearRampToValueAtTime(vol, ctx.currentTime + 0.01);
    g.gain.linearRampToValueAtTime(0, ctx.currentTime + dur);
    o.connect(g); g.connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime + dur + 0.02);
  }
  startMotion() {
    if (this.interval) return;
    const tick = () => { this.beep(880, 0.12); setTimeout(() => this.beep(1100, 0.1), 160); };
    tick();
    this.interval = setInterval(tick, 3000);
  }
  stopMotion() { if (this.interval) { clearInterval(this.interval); this.interval = null; } }
  setEnabled(on) {
    this.enabled = on;
    if (!on) this.stopMotion();
    else this._init();
  }
}

// Camera audio: play the streaming WAV from /audio.wav.
// The src is set on the first play() so the browser sees it on a user gesture.
export class CameraAudio {
  constructor(el) {
    this.el = el;
    this.playing = false;
    this.available = true;
    // Recover from mid-stream disconnects (RTSP hiccup, camera switch).
    this.el.addEventListener('error', () => {
      if (!this.playing) return;
      setTimeout(() => this._restart(), 1000);
    });
  }

  async play() {
    // Fresh src each start avoids Chrome's "already buffered" cache.
    this.el.src = `/audio.wav?t=${Date.now()}`;
    try {
      await this.el.play();
      this.playing = true;
      this.available = true;
      return true;
    } catch (e) {
      // 404 = camera has no audio; anything else is likely autoplay policy.
      this.playing = false;
      if (e.name === 'NotSupportedError') this.available = false;
      return false;
    }
  }

  stop() {
    this.playing = false;
    this.el.pause();
    // Drop the stream — the backend unsubscribes the client on disconnect.
    this.el.removeAttribute('src');
    this.el.load();
  }

  toggle() {
    if (this.playing) { this.stop(); return Promise.resolve(false); }
    return this.play();
  }

  _restart() {
    if (!this.playing) return;
    this.el.src = `/audio.wav?t=${Date.now()}`;
    this.el.play().catch(() => {});
  }
}

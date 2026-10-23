export class RoiCanvas {
  constructor(canvas, streamImg, onSave) {
    this.c = canvas; this.img = streamImg; this.ctx = canvas.getContext('2d');
    this.onSave = onSave;
    this.mode = false;
    this.start = null; this.end = null;
    this.roi = { x: 0, y: 0, width: 1, height: 1, enabled: false };
    this._bind();
  }

  _bind() {
    this.c.addEventListener('mousedown', e => this._down(e.clientX, e.clientY));
    this.c.addEventListener('mousemove', e => this.start ? this._move(e.clientX, e.clientY) : null);
    window.addEventListener('mouseup', e => this.start ? this._up(e.clientX, e.clientY) : null);
    this.c.addEventListener('touchstart', e => { e.preventDefault(); const t = e.touches[0]; this._down(t.clientX, t.clientY); }, { passive: false });
    this.c.addEventListener('touchmove', e => { e.preventDefault(); if (!this.start) return; const t = e.touches[0]; this._move(t.clientX, t.clientY); }, { passive: false });
    this.c.addEventListener('touchend', e => { e.preventDefault(); const t = e.changedTouches[0]; this._up(t.clientX, t.clientY); }, { passive: false });
    window.addEventListener('resize', () => this.resize());
    this.img.addEventListener('load', () => this.resize());
  }

  resize() {
    const r = this.img.getBoundingClientRect();
    this.c.width = r.width; this.c.height = r.height;
    this.draw();
  }

  setMode(on) {
    this.mode = on;
    this.c.classList.toggle('drawing', on);
    if (!on) { this.start = null; this.end = null; this.draw(); }
  }

  setRoi(roi) { this.roi = { ...roi }; this.draw(); }

  _pt(clientX, clientY) {
    const r = this.c.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (clientY - r.top) / r.height)),
    };
  }

  _down(x, y) { if (!this.mode) return; this.start = this._pt(x, y); this.end = this.start; this.draw(); }
  _move(x, y) { this.end = this._pt(x, y); this.draw(); }
  _up(x, y) {
    if (!this.start) return;
    this.end = this._pt(x, y);
    const x0 = Math.min(this.start.x, this.end.x);
    const y0 = Math.min(this.start.y, this.end.y);
    const w = Math.abs(this.end.x - this.start.x);
    const h = Math.abs(this.end.y - this.start.y);
    this.start = null; this.end = null;
    this.setMode(false);
    if (w < 0.01 || h < 0.01) return;
    this.roi = { x: x0, y: y0, width: w, height: h, enabled: true };
    this.draw();
    this.onSave?.(this.roi);
  }

  draw() {
    const { ctx, c } = this;
    ctx.clearRect(0, 0, c.width, c.height);
    const drawRect = (x, y, w, h, color, dash) => {
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.setLineDash(dash || []);
      ctx.strokeRect(x * c.width, y * c.height, w * c.width, h * c.height);
      ctx.setLineDash([]);
    };
    if (this.roi.enabled && (this.roi.width < 1 || this.roi.height < 1)) {
      drawRect(this.roi.x, this.roi.y, this.roi.width, this.roi.height, '#5ad1a0', [6, 4]);
    }
    if (this.start && this.end) {
      const x0 = Math.min(this.start.x, this.end.x);
      const y0 = Math.min(this.start.y, this.end.y);
      const w = Math.abs(this.end.x - this.start.x);
      const h = Math.abs(this.end.y - this.start.y);
      drawRect(x0, y0, w, h, '#f5b642', [4, 4]);
    }
  }
}

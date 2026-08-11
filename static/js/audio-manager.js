class AudioManager {
    constructor() {
        this.audioCtx = null;
        this.alertInterval = null;
        this.isMotionAlertActive = false;
        this.enabled = true;
        this.alertIntervalMs = 3000;
        this.beepFrequency = 880;
        this.beepDuration = 0.15;
        this.beepVolume = 0.3;
        this.initialized = false;
    }

    init() {
        if (this.initialized && this.audioCtx) {
            return this.audioCtx;
        }

        try {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.initialized = true;
            
            if (this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }
            
            console.log('🔊 AudioContext initialized, state:', this.audioCtx.state);
            return this.audioCtx;
        } catch (e) {
            console.error('Audio init error:', e);
            return null;
        }
    }

    playBeep(frequency = this.beepFrequency, duration = this.beepDuration, volume = this.beepVolume) {
        if (!this.enabled) return;
        
        const ctx = this.init();
        if (!ctx || ctx.state !== 'running') {
            console.warn('AudioContext not ready, state:', ctx?.state);
            return;
        }
        
        try {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(frequency, ctx.currentTime);
            
            // Volume envelope
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + 0.01);
            gain.gain.linearRampToValueAtTime(0, ctx.currentTime + duration);
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + duration + 0.01);
            
            // Cleanup
            setTimeout(() => {
                try {
                    osc.disconnect();
                    gain.disconnect();
                } catch (e) {
                    // Ignore cleanup errors
                }
            }, (duration * 1000) + 100);
            
        } catch (e) {
            console.warn('Beep error:', e);
        }
    }

    playAlert() {
        this.playBeep(this.beepFrequency, 0.1, 0.3);
        setTimeout(() => {
            this.playBeep(this.beepFrequency * 1.2, 0.12, 0.25);
        }, 200);
    }

    testSound() {
        this.playBeep(660, 0.1, 0.2);
        setTimeout(() => {
            this.playBeep(880, 0.1, 0.2);
        }, 150);
        setTimeout(() => {
            this.playBeep(1100, 0.12, 0.2);
        }, 300);
    }

    startMotionAlert() {
        if (this.isMotionAlertActive) return;
        
        this.isMotionAlertActive = true;
        console.log(`🔊 Starting motion alert (every ${this.alertIntervalMs / 1000} seconds)`);
        
        // Play immediately
        this.playAlert();
        
        // Then every interval
        this.alertInterval = setInterval(() => {
            if (this.isMotionAlertActive && this.enabled) {
                this.playAlert();
            } else {
                this.stopMotionAlert();
            }
        }, this.alertIntervalMs);
    }

    stopMotionAlert() {
        if (this.alertInterval) {
            clearInterval(this.alertInterval);
            this.alertInterval = null;
        }
        this.isMotionAlertActive = false;
        console.log('🔇 Motion alert stopped');
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        if (!enabled) {
            this.stopMotionAlert();
            if (this.audioCtx && this.audioCtx.state === 'running') {
                this.audioCtx.suspend();
            }
        } else {
            this.init();
            if (this.audioCtx && this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }
        }
    }
    
    cleanup() {
        this.stopMotionAlert();
        if (this.audioCtx) {
            try {
                this.audioCtx.close();
            } catch (e) {
                // Ignore
            }
            this.audioCtx = null;
            this.initialized = false;
        }
    }
}

// Create singleton instance
window.audioManager = new AudioManager();

// Initialize audio on first interaction
document.addEventListener('click', () => window.audioManager.init(), { once: true });
document.addEventListener('touchstart', () => window.audioManager.init(), { once: true });
document.addEventListener('keydown', () => window.audioManager.init(), { once: true });
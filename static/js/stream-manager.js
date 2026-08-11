// Stream Manager Module
class StreamManager {
    constructor(streamId, thresholdId, minAreaId) {
        this.stream = document.getElementById(streamId);
        this.threshold = document.getElementById(thresholdId);
        this.minArea = document.getElementById(minAreaId);
        this.thresholdDisplay = document.getElementById('t_val');
        this.minAreaDisplay = document.getElementById('m_val');
        
        this.currentParams = {
            threshold: parseInt(this.threshold.value),
            minArea: parseInt(this.minArea.value)
        };
    }

    update() {
        const threshold = parseInt(this.threshold.value);
        const minArea = parseInt(this.minArea.value);
        
        this.currentParams = { threshold, minArea };
        
        // Update displays
        if (this.thresholdDisplay) {
            this.thresholdDisplay.textContent = threshold;
        }
        if (this.minAreaDisplay) {
            this.minAreaDisplay.textContent = minArea;
        }
        
        // Update stream URL
        this.stream.src = `/stream.mjpg?threshold=${threshold}&min_area=${minArea}`;
    }

    setCamera(cameraUrl, options = {}) {
        // Maintain current params
        const params = new URLSearchParams({
            threshold: this.currentParams.threshold,
            min_area: this.currentParams.minArea,
            ...options
        });
        
        // If camera URL already has params, handle accordingly
        // if (cameraUrl.includes('?')) {
        //     const [baseUrl, existingParams] = cameraUrl.split('?');
        //     const existing = new URLSearchParams(existingParams);
        //     // Merge with existing params, but our params take precedence
        //     for (const [key, value] of params) {
        //         existing.set(key, value);
        //     }
        //     this.stream.src = `${baseUrl}?${existing.toString()}`;
        // } else {
        //     this.stream.src = `${cameraUrl}?${params.toString()}`;
        // }
        this.stream.src = `/stream.mjpg?time=${Date.now()}`;
    }

    getParams() {
        return this.currentParams;
    }

    onStreamLoad(callback) {
        this.stream.addEventListener('load', callback);
    }
}

// Export for use
window.StreamManager = StreamManager;
// ROI Manager Module
class ROIManager {
    constructor(canvasId, cameraName = '') {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.cameraName = cameraName;
        
        // ROI state
        this.roiData = {
            x: 0,
            y: 0,
            width: 1.0,
            height: 1.0,
            enabled: false
        };
        
        // Drawing state
        this.isDrawingMode = false;
        this.isDrawing = false;
        this.drawStart = null;
        this.drawEnd = null;
        
        // Event listeners
        this.onROIChange = null;
        this.onStatusUpdate = null;
        
        // Touch support
        this.isMobile = /Android|iPhone|iPad|iPod|BlackBerry|Opera Mini|IEMobile/i.test(navigator.userAgent);
    }

    setCameraName(name) {
        this.cameraName = name;
    }

    loadROI(cameraName) {
        this.cameraName = cameraName || this.cameraName;
        return fetch(`/roi/${encodeURIComponent(this.cameraName)}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    this.roiData = data.roi;
                    this.drawROI();
                    this.updateStatus();
                    return this.roiData;
                }
                throw new Error('Failed to load ROI');
            })
            .catch(err => {
                console.error('Error loading ROI:', err);
                return null;
            });
    }

    saveROI() {
        return fetch('/roi/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_name: this.cameraName,
                roi: this.roiData
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                this.drawROI();
                this.updateStatus();
                return data;
            }
            throw new Error(data.message || 'Failed to save ROI');
        });
    }

    resetROI() {
        return fetch(`/roi/reset/${encodeURIComponent(this.cameraName)}`, {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                this.roiData = { x: 0, y: 0, width: 1.0, height: 1.0, enabled: false };
                this.drawROI();
                this.updateStatus();
                return data;
            }
            throw new Error(data.message || 'Failed to reset ROI');
        });
    }

    toggleROI() {
        this.roiData.enabled = !this.roiData.enabled;
        return this.saveROI();
    }

    enableDrawing() {
        this.isDrawingMode = true;
        this.canvas.classList.add('drawing');
        this.canvas.style.cursor = 'crosshair';
        this.showHelp('🔴 Drawing mode active. Click and drag on video to select ROI.', 'info');
    }

    disableDrawing() {
        this.isDrawingMode = false;
        this.isDrawing = false;
        this.canvas.classList.remove('drawing');
        this.canvas.style.cursor = 'default';
        this.drawStart = null;
        this.drawEnd = null;
        roiDraw.textContent = '✏️ Draw ROI';
        roiDraw.className = 'btn btn-roi';        
        this.showHelp('', '');
        this.drawROI();
    }

    // Drawing methods
    startDraw(x, y) {
        if (!this.isDrawingMode) return;
        this.drawStart = { x, y };
        this.isDrawing = true;
    }

    moveDraw(x, y) {
        if (!this.isDrawing || !this.drawStart) return;
        this.drawEnd = { x, y };
        this.drawROI();
    }

    endDraw() {
        if (!this.isDrawing || !this.drawStart) {
            this.disableDrawing();
            return;
        }

        if (!this.drawEnd) {
            this.drawEnd = this.drawStart;
        }

        const x = Math.min(this.drawStart.x, this.drawEnd.x);
        const y = Math.min(this.drawStart.y, this.drawEnd.y);
        const width = Math.abs(this.drawEnd.x - this.drawStart.x);
        const height = Math.abs(this.drawEnd.y - this.drawStart.y);

        if (width > 0.01 && height > 0.01) {
            this.roiData = { x, y, width, height, enabled: true };
            this.saveROI()
                .then(() => {
                    this.showHelp('✅ ROI saved successfully!', 'success');
                    setTimeout(() => this.showHelp('', ''), 2000);
                })
                .catch(err => {
                    this.showHelp('❌ Error saving ROI: ' + err.message, 'error');
                });
        } else {
            this.showHelp('⚠️ ROI area too small. Please draw a larger rectangle.', 'warning');
        }

        this.disableDrawing();
    }

    cancelDraw() {
        if (this.isDrawing) {
            this.disableDrawing();
            this.drawROI();
        }
    }

    drawROI() {
        const canvas = this.canvas;
        const ctx = this.ctx;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw existing ROI
        if (this.roiData.enabled && this.roiData.width < 1.0 && this.roiData.height < 1.0) {
            const x = this.roiData.x * canvas.width;
            const y = this.roiData.y * canvas.height;
            const w = this.roiData.width * canvas.width;
            const h = this.roiData.height * canvas.height;

            ctx.strokeStyle = '#00ff88';
            ctx.lineWidth = 3;
            ctx.setLineDash([8, 4]);
            ctx.strokeRect(x, y, w, h);

            ctx.fillStyle = 'rgba(0, 255, 136, 0.1)';
            ctx.fillRect(x, y, w, h);
            ctx.setLineDash([]);

            ctx.fillStyle = '#00ff88';
            ctx.font = '14px system-ui';
            ctx.fillText('ROI', x + 8, y + 22);
        }

        // Draw current rectangle being drawn
        if (this.drawStart && this.drawEnd) {
            const x = Math.min(this.drawStart.x, this.drawEnd.x);
            const y = Math.min(this.drawStart.y, this.drawEnd.y);
            const w = Math.abs(this.drawEnd.x - this.drawStart.x);
            const h = Math.abs(this.drawEnd.y - this.drawStart.y);

            ctx.strokeStyle = '#FFD700';
            ctx.lineWidth = 3;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(x, y, w, h);

            ctx.fillStyle = 'rgba(255, 215, 0, 0.15)';
            ctx.fillRect(x, y, w, h);
            ctx.setLineDash([]);
        }
    }

    updateStatus() {
        const status = this.roiData.enabled && this.roiData.width < 1.0 && this.roiData.height < 1.0;
        const roiStatus = document.getElementById('roiStatus');
        const roiState = document.getElementById('roiState');
        const roiToggle = document.getElementById('roiToggle');
        const roiCoords = document.getElementById('roiCoords');

        if (status) {
            const xPercent = (this.roiData.x * 100).toFixed(1);
            const yPercent = (this.roiData.y * 100).toFixed(1);
            const wPercent = (this.roiData.width * 100).toFixed(1);
            const hPercent = (this.roiData.height * 100).toFixed(1);

            roiStatus.textContent = `📐 ROI: Active (${xPercent}%, ${yPercent}%) → (${(parseFloat(xPercent) + parseFloat(wPercent)).toFixed(1)}%, ${(parseFloat(yPercent) + parseFloat(hPercent)).toFixed(1)}%)`;
            roiStatus.className = 'roi-status active';
            roiState.textContent = 'Active';
            roiToggle.textContent = '🎯 ROI ON';
            roiToggle.className = 'btn btn-roi active';
            roiCoords.textContent = `ROI: X:${xPercent}% Y:${yPercent}% W:${wPercent}% H:${hPercent}%`;
        } else {
            roiStatus.textContent = '📐 ROI: Disabled (Full Frame)';
            roiStatus.className = 'roi-status inactive';
            roiState.textContent = 'Disabled';
            roiToggle.textContent = '🎯 Enable ROI';
            roiToggle.className = 'btn btn-roi';
            roiCoords.textContent = 'ROI Position: Full Frame';
        }

        if (this.onStatusUpdate) {
            this.onStatusUpdate(this.roiData);
        }
    }

    showHelp(message, type = 'info') {
        const helpText = document.getElementById('helpText');
        if (message) {
            helpText.textContent = message;
            helpText.className = 'help-text visible';
            helpText.style.border = `2px solid ${type === 'success' ? '#4CAF50' : type === 'warning' ? '#FF9800' : type === 'error' ? '#f44336' : '#2196F3'}`;
        } else {
            helpText.className = 'help-text';
        }
    }

    resizeCanvas() {
        const stream = document.getElementById('stream');
        const rect = stream.getBoundingClientRect();
        const videoWidth = rect.width / 2;
        
        this.canvas.width = videoWidth;
        this.canvas.height = rect.height;
        this.canvas.style.width = videoWidth + 'px';
        this.canvas.style.height = rect.height + 'px';
        
        this.drawROI();
    }
}

// Export for use
window.ROIManager = ROIManager;
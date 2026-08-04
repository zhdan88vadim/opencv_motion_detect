HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Motion Detection with ROI</title>
    <style>
        body { background: #121212; color: #e0e0e0; font-family: system-ui, sans-serif; text-align: center; margin: 0; padding: 10px; }
        .container { max-width: 1200px; margin: auto; }
        .video-container { 
            position: relative; 
            display: inline-block; 
            width: 100%; 
            max-width: 100%;
            background: #000;
            border-radius: 8px;
            border: 2px solid #333;
            overflow: hidden;
        }
        .video-container img { 
            width: 100%; 
            max-width: 100%; 
            height: auto; 
            display: block;
        }
        .video-container canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 50%;  /* Только левая половина */
            height: 100%;
            pointer-events: none;
            cursor: default;
        }
        .video-container canvas.drawing {
            pointer-events: auto;
            cursor: crosshair;
        }
        .controls { background: #1e1e1e; padding: 15px; border-radius: 8px; margin-top: 15px; display: flex; flex-wrap: wrap; justify-content: space-around; gap: 10px; }
        .control-group { display: flex; flex-direction: column; align-items: center; min-width: 150px; }
        label { font-size: 14px; margin-bottom: 5px; color: #aaa; }
        input[type=range] { width: 100%; cursor: pointer; }
        span { font-weight: bold; color: #00ff88; margin-top: 5px; }
        
        .roi-controls { background: #1e1e1e; padding: 15px; border-radius: 8px; margin-top: 10px; display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
        .btn { padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; transition: 0.3s; margin: 2px; }
        .btn-roi { background: #9C27B0; color: white; }
        .btn-roi.active { background: #4CAF50; }
        .btn-roi.drawing { background: #FF5722; animation: pulse 0.5s; }
        .btn-roi.reset { background: #f44336; color: white; }
        .btn-audio { background: #4CAF50; color: white; }
        .btn-audio.off { background: #f44336; }
        .btn:hover { transform: scale(1.05); opacity: 0.9; }
        
        .roi-status { padding: 8px; margin-top: 5px; border-radius: 4px; font-size: 14px; background: #1e1e1e; }
        .roi-status.active { background: #4CAF50; color: white; }
        .roi-status.inactive { background: #666; color: #ccc; }
        
        .motion-status { padding: 10px; margin-top: 10px; border-radius: 6px; font-weight: bold; background: #1e1e1e; }
        .motion-status.motion { background: #ff4444; color: white; animation: pulse 0.5s; }
        .motion-status.recording { background: #ff4444; color: white; animation: pulse 0.3s; }
        @keyframes pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.02)} }
        
        audio { width: 100%; margin-top: 10px; }

        .btn-record { background: #2196F3; color: white; }
        .btn-record.off { background: #666; }
        .btn-record.recording { background: #f44336; animation: pulse 0.5s; }
        
        .btn-detection { background: #FF5722; color: white; }
        .btn-detection.off { background: #666; }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-indicator.online { background: #4CAF50; }
        .status-indicator.offline { background: #f44336; }
        
        .audio-indicator {
            font-size: 12px;
            color: #888;
            margin-top: 4px;
        }
        .audio-indicator.enabled { color: #4CAF50; }
        .audio-indicator.disabled { color: #888; }
        
        .roi-coords {
            font-size: 12px;
            color: #aaa;
            margin-top: 5px;
            font-family: monospace;
        }
        
        .info-panel {
            background: #1e1e1e;
            padding: 10px;
            border-radius: 6px;
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 20px;
        }
        .info-item {
            font-size: 13px;
            color: #aaa;
        }
        .info-item .value {
            color: #00ff88;
            font-weight: bold;
        }
        
        .help-text {
            color: #FF9800;
            font-size: 13px;
            margin-top: 5px;
            padding: 8px;
            background: #2a2a2a;
            border-radius: 4px;
            display: none;
        }
        .help-text.visible {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Live Security Feed 
            <span class="status-indicator online" id="statusIndicator"></span>
            <span id="connectionStatus" style="font-size: 14px; color: #4CAF50;">Connected</span>
        </h2>
        <div class="video-container" id="videoContainer">
            <img id="stream" src="/stream.mjpg?threshold=200&min_area=5">
            <canvas id="roiCanvas"></canvas>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>Camera</label>
                <select id="cameraSelect" style="width: 100%; padding: 8px; background: #2a2a2a; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; cursor: pointer;">
                    __CAMERA_OPTIONS__
                </select>
                <span id="audioIndicator" class="audio-indicator enabled">🔊 Audio available</span>
            </div>        
            <div class="control-group">
                <label>Motion Threshold</label>
                <input type="range" id="threshold" min="10" max="2000" step="10" value="200">
                <span id="t_val">200</span>
            </div>
            <div class="control-group">
                <label>Minimum Area</label>
                <input type="range" id="min_area" min="5" max="1000" step="5" value="5">
                <span id="m_val">5</span>
            </div>
        </div>
        
        <div class="roi-controls">
            <button id="roiToggle" class="btn btn-roi">🎯 Enable ROI</button>
            <button id="roiDraw" class="btn btn-roi">✏️ Draw ROI</button>
            <button id="roiReset" class="btn btn-roi reset">🔄 Reset ROI</button>
            <button id="audioToggle" class="btn btn-audio">🔊 Audio ON</button>
            <button id="recordToggle" class="btn btn-record">📹 Recording ON</button>
            <button id="detectionToggle" class="btn btn-detection">🎯 Detection ON</button>
        </div>
        
        <div id="helpText" class="help-text">
            💡 Click and drag on the video to draw ROI rectangle. Release to save.
        </div>
        
        <div id="roiStatus" class="roi-status inactive">📐 ROI: Disabled (Full Frame)</div>
        <div id="roiCoords" class="roi-coords">ROI Position: —</div>
        
        <div id="motionStatus" class="motion-status">⚫ NO MOTION</div>
        
        <div class="info-panel">
            <span class="info-item">📷 Camera: <span class="value" id="currentCamera">Loading...</span></span>
            <span class="info-item">🎯 ROI: <span class="value" id="roiState">Disabled</span></span>
            <span class="info-item">📹 Recording: <span class="value" id="recordingState">OFF</span></span>
        </div>
        
        <audio id="audioPlayer" controls autoplay preload="none">
            <source src="/audio.wav" type="audio/wav">
        </audio>
    </div>
    
       <script>
        const stream = document.getElementById('stream');
        const canvas = document.getElementById('roiCanvas');
        const ctx = canvas.getContext('2d');
        const videoContainer = document.getElementById('videoContainer');
        
        const threshold = document.getElementById('threshold');
        const min_area = document.getElementById('min_area');
        const audioToggle = document.getElementById('audioToggle');
        const motionStatus = document.getElementById('motionStatus');
        const audioPlayer = document.getElementById('audioPlayer');
        const recordToggle = document.getElementById('recordToggle');
        const detectionToggle = document.getElementById('detectionToggle');
        const statusIndicator = document.getElementById('statusIndicator');
        const connectionStatus = document.getElementById('connectionStatus');
        const audioIndicator = document.getElementById('audioIndicator');
        const currentCamera = document.getElementById('currentCamera');
        const roiState = document.getElementById('roiState');
        const recordingState = document.getElementById('recordingState');
        const roiStatus = document.getElementById('roiStatus');
        const roiCoords = document.getElementById('roiCoords');
        const roiToggle = document.getElementById('roiToggle');
        const roiDraw = document.getElementById('roiDraw');
        const roiReset = document.getElementById('roiReset');
        const helpText = document.getElementById('helpText');
        const cameraSelect = document.getElementById('cameraSelect');
        
        let audioEnabled = true;
        let recordingEnabled = true;
        let detectionEnabled = true;
        let lastMotionState = false;
        let eventSource = null;
        let currentCameraName = '';
        let roiEnabled = false;
        let isDrawing = false;
        let isDrawingMode = false;
        let drawStart = null;
        let drawEnd = null;
        let roiData = { x: 0, y: 0, width: 1.0, height: 1.0, enabled: false };
        
        // Определяем мобильное устройство
        const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|Opera Mini|IEMobile/i.test(navigator.userAgent);
        
        // ===== CANVAS RESIZE =====
        function resizeCanvas() {
            const rect = stream.getBoundingClientRect();
            const videoWidth = rect.width / 2;
            
            canvas.width = videoWidth;
            canvas.height = rect.height;
            canvas.style.width = videoWidth + 'px';
            canvas.style.height = rect.height + 'px';
            
            drawExistingROI();
        }
        
        // ===== POSITION CALCULATION =====
        function getCanvasPos(e) {
            if (!e) {
                console.warn('getCanvasPos: no event');
                return null;
            }
            
            try {
                const rect = canvas.getBoundingClientRect();
                let clientX, clientY;
                
                if (e.touches && e.touches.length > 0) {
                    clientX = e.touches[0].clientX;
                    clientY = e.touches[0].clientY;
                    if (e.preventDefault) e.preventDefault();
                } else if (e.changedTouches && e.changedTouches.length > 0) {
                    clientX = e.changedTouches[0].clientX;
                    clientY = e.changedTouches[0].clientY;
                    if (e.preventDefault) e.preventDefault();
                } else if (e.clientX !== undefined && e.clientX !== null) {
                    clientX = e.clientX;
                    clientY = e.clientY;
                } else {
                    console.warn('getCanvasPos: no position data');
                    return null;
                }
                
                const x = clientX - rect.left;
                const y = clientY - rect.top;
                
                const normalizedX = Math.max(0, Math.min(1, x / canvas.width));
                const normalizedY = Math.max(0, Math.min(1, y / canvas.height));
                
                return { 
                    x: normalizedX, 
                    y: normalizedY,
                    px: x,
                    py: y
                };
            } catch(err) {
                console.warn('getCanvasPos error:', err);
                return null;
            }
        }
        
        // ===== DRAWING FUNCTIONS =====
        function drawExistingROI() {
            try {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                if (roiData.enabled && roiData.width < 1.0 && roiData.height < 1.0) {
                    const x = roiData.x * canvas.width;
                    const y = roiData.y * canvas.height;
                    const w = roiData.width * canvas.width;
                    const h = roiData.height * canvas.height;
                    
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
                    
                    const xPercent = (roiData.x * 100).toFixed(1);
                    const yPercent = (roiData.y * 100).toFixed(1);
                    const wPercent = (roiData.width * 100).toFixed(1);
                    const hPercent = (roiData.height * 100).toFixed(1);
                    roiCoords.textContent = `ROI: X:${xPercent}% Y:${yPercent}% W:${wPercent}% H:${hPercent}%`;
                } else {
                    roiCoords.textContent = 'ROI Position: Full Frame';
                }
            } catch(err) {
                console.warn('drawExistingROI error:', err);
            }
        }
        
        function drawROI() {
            try {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                if (roiData.enabled && roiData.width < 1.0 && roiData.height < 1.0) {
                    const x = roiData.x * canvas.width;
                    const y = roiData.y * canvas.height;
                    const w = roiData.width * canvas.width;
                    const h = roiData.height * canvas.height;
                    
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
                
                if (drawStart && drawEnd) {
                    const x = Math.min(drawStart.px, drawEnd.px);
                    const y = Math.min(drawStart.py, drawEnd.py);
                    const w = Math.abs(drawEnd.px - drawStart.px);
                    const h = Math.abs(drawEnd.py - drawStart.py);
                    
                    ctx.strokeStyle = '#FFD700';
                    ctx.lineWidth = 3;
                    ctx.setLineDash([6, 4]);
                    ctx.strokeRect(x, y, w, h);
                    
                    ctx.fillStyle = 'rgba(255, 215, 0, 0.15)';
                    ctx.fillRect(x, y, w, h);
                    
                    ctx.setLineDash([]);
                    
                    const xPercent = (x / canvas.width * 100).toFixed(1);
                    const yPercent = (y / canvas.height * 100).toFixed(1);
                    const wPercent = (w / canvas.width * 100).toFixed(1);
                    const hPercent = (h / canvas.height * 100).toFixed(1);
                    ctx.fillStyle = '#FFD700';
                    ctx.font = '12px system-ui';
                    ctx.fillText(`X:${xPercent}% Y:${yPercent}% W:${wPercent}% H:${hPercent}%`, x + 5, y - 8);
                    
                    roiCoords.textContent = `Drawing: (${xPercent}%, ${yPercent}%) → (${((x+w)/canvas.width*100).toFixed(1)}%, ${((y+h)/canvas.height*100).toFixed(1)}%)`;
                }
            } catch(err) {
                console.warn('drawROI error:', err);
            }
        }
        
        // ===== MOUSE EVENTS =====
        function startDraw(e) {
            if (!isDrawingMode) return;
            e.preventDefault();
            const pos = getCanvasPos(e);
            if (!pos) return;
            drawStart = pos;
            drawEnd = pos;
            isDrawing = true;
            canvas.style.cursor = 'crosshair';
            helpText.textContent = '🔴 Drawing... Release mouse to save ROI';
            helpText.className = 'help-text visible';
        }
        
        function moveDraw(e) {
            if (!isDrawing || !drawStart) return;
            e.preventDefault();
            const pos = getCanvasPos(e);
            if (!pos) return;
            drawEnd = pos;
            drawROI();
        }
        
        function endDraw(e) {
            if (!isDrawing || !drawStart) {
                isDrawingMode = false;
                return;
            }
            e.preventDefault();
            
            const pos = getCanvasPos(e);
            if (!pos) {
                resetDrawingState();
                return;
            }
            drawEnd = pos;
            
            const x = Math.min(drawStart.x, drawEnd.x);
            const y = Math.min(drawStart.y, drawEnd.y);
            const width = Math.abs(drawEnd.x - drawStart.x);
            const height = Math.abs(drawEnd.y - drawStart.y);
            
            if (width > 0.01 && height > 0.01) {
                roiData = { x, y, width, height, enabled: true };
                saveROI();
                drawExistingROI();
            } else {
                alert('ROI area too small. Please draw a larger rectangle.');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawExistingROI();
            }
            
            resetDrawingState();
        }
        
        function cancelDraw(e) {
            if (isDrawing) {
                resetDrawingState();
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawExistingROI();
            }
        }
        
        // ===== TOUCH EVENTS (Mobile) =====
        let touchTimer = null;
        let touchStartTime = 0;
        
        function touchStartDraw(e) {
            if (!isDrawingMode) return;
            e.preventDefault();
            
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
            
            const pos = getCanvasPos(e);
            if (!pos) return;
            
            drawStart = pos;
            drawEnd = pos;
            isDrawing = true;
            touchStartTime = Date.now();
            
            helpText.textContent = '👆 Drawing... Release to save ROI';
            helpText.className = 'help-text visible';
            canvas.style.border = '3px solid #FFD700';
            
            if (navigator.vibrate) {
                navigator.vibrate(10);
            }
        }
        
        function touchMoveDraw(e) {
            if (!isDrawing || !drawStart) {
                return;
            }
            e.preventDefault();
            
            const pos = getCanvasPos(e);
            if (!pos) return;
            
            drawEnd = pos;
            drawROI();
        }
        
        function touchEndDraw(e) {
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
            
            if (!isDrawingMode || !drawStart) {
                resetDrawingState();
                return;
            }
            
            e.preventDefault();
            
            let pos = drawEnd;
            
            if (e && e.changedTouches && e.changedTouches.length > 0) {
                const touchPos = getCanvasPos(e);
                if (touchPos) {
                    pos = touchPos;
                }
            }
            
            if (!pos || (pos.px === undefined && pos.py === undefined)) {
                pos = drawEnd || drawStart;
            }
            
            drawEnd = pos;
            
            const x = Math.min(drawStart.x, drawEnd.x);
            const y = Math.min(drawStart.y, drawEnd.y);
            const width = Math.abs(drawEnd.x - drawStart.x);
            const height = Math.abs(drawEnd.y - drawStart.y);
            
            const touchDuration = Date.now() - touchStartTime;
            
            if (width > 0.02 && height > 0.02 && touchDuration > 200) {
                roiData = { x, y, width, height, enabled: true };
                saveROI();
                drawExistingROI();
                showNotification('✅ ROI saved!');
                
                if (navigator.vibrate) {
                    navigator.vibrate([10, 50, 10]);
                }
            } else if (width > 0 || height > 0) {
                if (touchDuration > 200) {
                    alert('ROI area too small. Please draw a larger rectangle.');
                } else {
                    showNotification('👆 Tap and drag to draw ROI');
                }
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawExistingROI();
            } else {
                showNotification('👆 Tap and drag to draw ROI');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawExistingROI();
            }
            
            resetDrawingState();
        }
        
        // Глобальный обработчик для touchend (если палец ушел за пределы canvas)
        function documentTouchEnd(e) {
            if (!isDrawing && !isDrawingMode) return;
            
            const touch = e.changedTouches ? e.changedTouches[0] : null;
            if (!touch) return;
            
            try {
                const target = document.elementFromPoint(touch.clientX, touch.clientY);
                
                if (!canvas.contains(target)) {
                    console.log('Touch ended outside canvas, forcing complete');
                    
                    const rect = canvas.getBoundingClientRect();
                    const x = touch.clientX - rect.left;
                    const y = touch.clientY - rect.top;
                    
                    if (x >= 0 && x <= canvas.width && y >= 0 && y <= canvas.height) {
                        const normalizedX = Math.max(0, Math.min(1, x / canvas.width));
                        const normalizedY = Math.max(0, Math.min(1, y / canvas.height));
                        drawEnd = { x: normalizedX, y: normalizedY, px: x, py: y };
                        
                        const xMin = Math.min(drawStart.x, drawEnd.x);
                        const yMin = Math.min(drawStart.y, drawEnd.y);
                        const width = Math.abs(drawEnd.x - drawStart.x);
                        const height = Math.abs(drawEnd.y - drawStart.y);
                        
                        if (width > 0.02 && height > 0.02) {
                            roiData = { x: xMin, y: yMin, width, height, enabled: true };
                            saveROI();
                            drawExistingROI();
                            showNotification('✅ ROI saved!');
                        } else {
                            ctx.clearRect(0, 0, canvas.width, canvas.height);
                            drawExistingROI();
                        }
                    }
                    
                    resetDrawingState();
                }
            } catch(err) {
                console.warn('documentTouchEnd error:', err);
                resetDrawingState();
            }
        }
        
        function forceCompleteDraw() {
            if (isDrawing && drawStart) {
                console.log('Force completing drawing');
                const pos = drawEnd || drawStart;
                drawEnd = pos;
                
                const x = Math.min(drawStart.x, drawEnd.x);
                const y = Math.min(drawStart.y, drawEnd.y);
                const width = Math.abs(drawEnd.x - drawStart.x);
                const height = Math.abs(drawEnd.y - drawStart.y);
                
                if (width > 0.02 && height > 0.02) {
                    roiData = { x, y, width, height, enabled: true };
                    saveROI();
                    drawExistingROI();
                    showNotification('✅ ROI saved!');
                } else {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    drawExistingROI();
                }
                
                resetDrawingState();
            }
        }
        
        function resetDrawingState() {
            drawStart = null;
            drawEnd = null;
            isDrawing = false;
            isDrawingMode = false;
            canvas.style.cursor = 'default';
            canvas.className = '';
            canvas.style.border = 'none';
            roiDraw.textContent = '✏️ Draw ROI';
            roiDraw.className = 'btn btn-roi';
            helpText.className = 'help-text';
            
            if (touchTimer) {
                clearTimeout(touchTimer);
                touchTimer = null;
            }
            
            setTimeout(() => {
                drawExistingROI();
            }, 50);
        }
        
        function touchCancelDraw(e) {
            if (isDrawing || isDrawingMode) {
                resetDrawingState();
                showNotification('❌ Drawing cancelled');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawExistingROI();
            }
        }
        
        // ===== SETUP EVENTS =====
        function setupROIDrawing() {
            canvas.addEventListener('mousedown', startDraw);
            canvas.addEventListener('mousemove', moveDraw);
            canvas.addEventListener('mouseup', endDraw);
            canvas.addEventListener('mouseleave', cancelDraw);
            
            canvas.addEventListener('touchstart', touchStartDraw, { passive: false });
            canvas.addEventListener('touchmove', touchMoveDraw, { passive: false });
            canvas.addEventListener('touchend', touchEndDraw, { passive: false });
            canvas.addEventListener('touchcancel', touchCancelDraw, { passive: false });
            
            document.addEventListener('touchend', documentTouchEnd, { passive: false });
            
            window.addEventListener('resize', resizeCanvas);
            window.addEventListener('load', resizeCanvas);
            stream.addEventListener('load', resizeCanvas);
            
            document.addEventListener('visibilitychange', function() {
                if (document.hidden && (isDrawing || isDrawingMode)) {
                    forceCompleteDraw();
                }
            });
            
            setInterval(function() {
                if (isDrawing && Date.now() - touchStartTime > 10000) {
                    console.log('Drawing stuck, forcing complete');
                    forceCompleteDraw();
                }
            }, 5000);
        }
        
        // ===== ROI FUNCTIONS =====
        async function saveROI() {
            try {
                const res = await fetch('/roi/set', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        camera_name: currentCameraName,
                        roi: roiData
                    })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    console.log('ROI saved:', roiData);
                    updateROIStatus(roiData);
                    showNotification('✅ ROI saved!');
                    helpText.textContent = '✅ ROI saved successfully!';
                    helpText.className = 'help-text visible';
                    setTimeout(() => {
                        helpText.className = 'help-text';
                    }, 3000);
                } else {
                    alert('Error saving ROI: ' + data.message);
                }
            } catch(e) {
                console.error('Error saving ROI:', e);
                alert('Error saving ROI: ' + e.message);
            }
        }
        
        function updateROIStatus(roi) {
            if (roi.enabled && roi.width < 1.0 && roi.height < 1.0) {
                roiEnabled = true;
                const xPercent = (roi.x * 100).toFixed(1);
                const yPercent = (roi.y * 100).toFixed(1);
                const wPercent = (roi.width * 100).toFixed(1);
                const hPercent = (roi.height * 100).toFixed(1);
                
                roiStatus.textContent = `📐 ROI: Active (${xPercent}%, ${yPercent}%) → (${(parseFloat(xPercent) + parseFloat(wPercent)).toFixed(1)}%, ${(parseFloat(yPercent) + parseFloat(hPercent)).toFixed(1)}%)`;
                roiStatus.className = 'roi-status active';
                roiState.textContent = 'Active';
                roiToggle.textContent = '🎯 ROI ON';
                roiToggle.className = 'btn btn-roi active';
                roiCoords.textContent = `ROI: X:${xPercent}% Y:${yPercent}% W:${wPercent}% H:${hPercent}%`;
            } else {
                roiEnabled = false;
                roiStatus.textContent = '📐 ROI: Disabled (Full Frame)';
                roiStatus.className = 'roi-status inactive';
                roiState.textContent = 'Disabled';
                roiToggle.textContent = '🎯 Enable ROI';
                roiToggle.className = 'btn btn-roi';
                roiCoords.textContent = 'ROI Position: Full Frame';
            }
            drawExistingROI();
        }
        
        async function toggleROI() {
            roiData.enabled = !roiData.enabled;
            await saveROI();
        }
        
        async function resetROI() {
            if (!confirm('Reset ROI to full frame?')) return;
            try {
                const res = await fetch(`/roi/reset/${encodeURIComponent(currentCameraName)}`, {
                    method: 'POST'
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    roiData = { x: 0, y: 0, width: 1.0, height: 1.0, enabled: false };
                    updateROIStatus(roiData);
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    showNotification('🔄 ROI reset to full frame');
                } else {
                    alert('Error resetting ROI: ' + data.message);
                }
            } catch(e) {
                console.error('Error resetting ROI:', e);
                alert('Error resetting ROI: ' + e.message);
            }
        }
        
        function toggleDraw() {
            isDrawingMode = !isDrawingMode;
            if (isDrawingMode) {
                roiDraw.textContent = '✏️ Drawing... Tap on video';
                roiDraw.className = 'btn btn-roi drawing';
                canvas.className = 'drawing';
                canvas.style.cursor = 'crosshair';
                if (isMobile) {
                    helpText.textContent = '👆 Tap and drag on the video to draw ROI. Release to save.';
                } else {
                    helpText.textContent = '💡 Click and drag on the video to draw ROI rectangle. Release to save.';
                }
                helpText.className = 'help-text visible';
                showNotification('📐 Click and drag on the video to draw ROI');
            } else {
                roiDraw.textContent = '✏️ Draw ROI';
                roiDraw.className = 'btn btn-roi';
                canvas.className = '';
                canvas.style.cursor = 'default';
                drawStart = null;
                drawEnd = null;
                isDrawing = false;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawExistingROI();
                helpText.className = 'help-text';
                roiCoords.textContent = 'ROI Position: —';
            }
        }

        // ===== CAMERA FUNCTIONS =====
        async function switchCamera() {
            const selectedOption = cameraSelect.options[cameraSelect.selectedIndex];
            const url = cameraSelect.value;
            const name = selectedOption.text;
            const hasAudio = selectedOption.dataset.hasAudio === 'true';
            const cameraName = selectedOption.dataset.cameraName;
            
            currentCameraName = cameraName;
            currentCamera.textContent = name;
            
            if (hasAudio) {
                audioIndicator.textContent = '🔊 Audio available';
                audioIndicator.className = 'audio-indicator enabled';
            } else {
                audioIndicator.textContent = '🔇 No audio';
                audioIndicator.className = 'audio-indicator disabled';
            }
            
            try {
                const res = await fetch('/switch_camera', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, name: name, has_audio: hasAudio })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    console.log('📷 Switched to camera:', name, 'Audio:', hasAudio);
                    await loadROI(cameraName);
                    updateStream();
                    showNotification('Switched to: ' + name + (hasAudio ? ' 🔊' : ' 🔇'));
                }
            } catch(e) {
                console.error('Error switching camera:', e);
            }
        }
        
        async function loadROI(cameraName) {
            try {
                const res = await fetch(`/roi/${encodeURIComponent(cameraName)}`);
                const data = await res.json();
                if (data.status === 'ok') {
                    roiData = data.roi;
                    updateROIStatus(roiData);
                }
            } catch(e) {
                console.error('Error loading ROI:', e);
            }
        }

        // ===== NOTIFICATION =====
        function showNotification(message) {
            const status = document.getElementById('motionStatus');
            const originalText = status.innerHTML;
            status.innerHTML = '📷 ' + message;
            status.style.background = '#2196F3';
            setTimeout(() => {
                status.innerHTML = originalText;
                status.style.background = '';
            }, 2000);
        }

        // ===== SSE CONNECTION =====
        function connectSSE() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            
            try {
                eventSource = new EventSource('/events');
                
                eventSource.onopen = function(e) {
                    console.log('📡 SSE connection established');
                    statusIndicator.className = 'status-indicator online';
                    connectionStatus.textContent = 'Connected';
                    connectionStatus.style.color = '#4CAF50';
                };
                
                eventSource.onmessage = function(e) {
                    try {
                        const data = JSON.parse(e.data);
                        handleStatusUpdate(data);
                    } catch (err) {
                        console.error('Error parsing SSE data:', err);
                    }
                };
                
                eventSource.onerror = function(e) {
                    console.error('SSE connection error, reconnecting...');
                    statusIndicator.className = 'status-indicator offline';
                    connectionStatus.textContent = 'Disconnected - Reconnecting...';
                    connectionStatus.style.color = '#f44336';
                    
                    if (eventSource) {
                        eventSource.close();
                        eventSource = null;
                    }
                    
                    setTimeout(connectSSE, 3000);
                };
                
            } catch (err) {
                console.error('SSE initialization error:', err);
                setTimeout(connectSSE, 5000);
            }
        }

        function handleStatusUpdate(data) {
            if (data.recording_enabled !== undefined) {
                recordingEnabled = data.recording_enabled;
                recordToggle.textContent = recordingEnabled ? '📹 Recording ON' : '📹 Recording OFF';
                recordToggle.className = recordingEnabled ? 'btn btn-record' : 'btn btn-record off';
                recordingState.textContent = recordingEnabled ? 'ON' : 'OFF';
            }
            
            if (data.detection_enabled !== undefined) {
                detectionEnabled = data.detection_enabled;
                detectionToggle.textContent = detectionEnabled ? '🎯 Detection ON' : '🎯 Detection OFF';
                detectionToggle.className = detectionEnabled ? 'btn btn-detection' : 'btn btn-detection off';
            }
            
            if (data.motion_detected !== undefined) {
                let statusText = '';
                if (data.motion_detected) {
                    statusText = '🔴 MOTION DETECTED! Area: ' + data.motion_area;
                    if (data.recording) {
                        statusText += ' 📹 RECORDING';
                        motionStatus.className = 'motion-status recording';
                    } else {
                        motionStatus.className = 'motion-status motion';
                    }
                    
                    if (!lastMotionState) {
                        playAlert();
                    }
                    lastMotionState = true;
                } else {
                    statusText = '⚫ NO MOTION';
                    if (data.recording) {
                        statusText += ' 📹 RECORDING';
                        motionStatus.className = 'motion-status recording';
                    } else {
                        motionStatus.className = 'motion-status';
                    }
                    lastMotionState = false;
                }
                motionStatus.innerHTML = statusText;
            }
            
            if (data.last_recording) {
                console.log('📹 Last recording saved: ' + data.last_recording);
            }
            
            if (data.has_audio !== undefined) {
                if (data.has_audio) {
                    audioIndicator.textContent = '🔊 Audio available';
                    audioIndicator.className = 'audio-indicator enabled';
                } else {
                    audioIndicator.textContent = '🔇 No audio';
                    audioIndicator.className = 'audio-indicator disabled';
                }
            }
            
            if (data.camera_name) {
                currentCameraName = data.camera_name;
                currentCamera.textContent = data.camera_name;
            }
            
            if (data.roi) {
                roiData = data.roi;
                updateROIStatus(roiData);
            }
            
            statusIndicator.className = 'status-indicator online';
            connectionStatus.textContent = 'Connected';
            connectionStatus.style.color = '#4CAF50';
        }

        // ===== CONTROL FUNCTIONS =====
        async function toggleRecording() {
            recordingEnabled = !recordingEnabled;
            recordToggle.textContent = recordingEnabled ? '📹 Recording ON' : '📹 Recording OFF';
            recordToggle.className = recordingEnabled ? 'btn btn-record' : 'btn btn-record off';
            recordingState.textContent = recordingEnabled ? 'ON' : 'OFF';
            
            try {
                const res = await fetch('/toggle_recording', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: recordingEnabled })
                });
                console.log(await res.text());
            } catch(e) {
                console.log('Error toggling recording:', e);
            }
        }

        async function toggleDetection() {
            detectionEnabled = !detectionEnabled;
            detectionToggle.textContent = detectionEnabled ? '🎯 Detection ON' : '🎯 Detection OFF';
            detectionToggle.className = detectionEnabled ? 'btn btn-detection' : 'btn btn-detection off';
            
            try {
                const res = await fetch('/toggle_detection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: detectionEnabled })
                });
                console.log(await res.text());
            } catch(e) {
                console.log('Error toggling detection:', e);
            }
        }

        function playAlert() {
            if (audioEnabled) {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.value = 880;
                    gain.gain.setValueAtTime(0.3, ctx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime);
                    osc.stop(ctx.currentTime + 0.15);
                } catch(e) { console.log('Beep error:', e); }
            }
        }
        
        function toggleAudio() {
            audioEnabled = !audioEnabled;
            audioToggle.textContent = audioEnabled ? '🔊 Audio ON' : '🔇 Audio OFF';
            audioToggle.className = audioEnabled ? 'btn btn-audio' : 'btn btn-audio off';
            if (audioEnabled) {
                audioPlayer.play().catch(() => {});
            } else {
                audioPlayer.pause();
            }
        }
        
        function updateStream() {
            document.getElementById('t_val').innerText = threshold.value;
            document.getElementById('m_val').innerText = min_area.value;
            stream.src = `/stream.mjpg?threshold=${threshold.value}&min_area=${min_area.value}`;
        }
        
        // ===== EVENT LISTENERS =====
        threshold.oninput = updateStream;
        min_area.oninput = updateStream;
        audioToggle.onclick = toggleAudio;
        recordToggle.onclick = toggleRecording;
        detectionToggle.onclick = toggleDetection;
        roiToggle.onclick = toggleROI;
        roiDraw.onclick = toggleDraw;
        roiReset.onclick = resetROI;
        cameraSelect.onchange = switchCamera;
        
        // ===== INITIALIZATION =====
        window.addEventListener('load', function() {
            const selectedOption = cameraSelect.options[cameraSelect.selectedIndex];
            if (selectedOption) {
                currentCameraName = selectedOption.dataset.cameraName || selectedOption.text;
                currentCamera.textContent = currentCameraName;
                loadROI(currentCameraName);
            }
            setupROIDrawing();
            resizeCanvas();
            
            if (isMobile) {
                helpText.textContent = '👆 Tap "Draw ROI", then drag on video to select area';
                helpText.className = 'help-text visible';
                setTimeout(() => {
                    helpText.className = 'help-text';
                }, 5000);
            }
        });
        
        stream.addEventListener('load', resizeCanvas);
        connectSSE();
        
        console.log('🎥 Motion Detection with ROI');
        console.log('📡 Using Server-Sent Events for real-time updates');
        console.log('📐 ROI drawing: Click "Draw ROI" then click and drag on the video');
        console.log('📱 Mobile support:', isMobile ? 'Enabled' : 'Not detected');
    </script>
</body>
</html>
"""
// Main Application
document.addEventListener('DOMContentLoaded', function() {
    // Initialize managers
    const streamManager = new StreamManager('stream', 'threshold', 'min_area');
    const roiManager = new ROIManager('roiCanvas');
    const sseClient = new SSEClient('/events');

    // DOM References
    const cameraSelect = document.getElementById('cameraSelect');
    const currentCamera = document.getElementById('currentCamera');
    const audioIndicator = document.getElementById('audioIndicator');
    const audioToggle = document.getElementById('audioToggle');
    const recordToggle = document.getElementById('recordToggle');
    const detectionToggle = document.getElementById('detectionToggle');
    const roiToggle = document.getElementById('roiToggle');
    const roiDraw = document.getElementById('roiDraw');
    const roiReset = document.getElementById('roiReset');
    const motionStatus = document.getElementById('motionStatus');
    const audioPlayer = document.getElementById('audioPlayer');

    // State
    let audioEnabled = true;
    let recordingEnabled = true;
    let detectionEnabled = true;
    let lastMotionState = false;
    let currentCameraName = '';

    // ===== Camera Functions =====
    function loadCameras() {
        fetch('/api/cameras')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    populateCameraSelect(data.cameras);
                    // Set default selected camera
                    const defaultCamera = data.selected || Object.keys(data.cameras)[0];
                    if (defaultCamera) {
                        selectCamera(defaultCamera, false);
                    }
                } else {
                    console.error('Failed to load cameras:', data.message);
                }
            })
            .catch(err => {
                console.error('Error loading cameras:', err);
            });
    }

    function populateCameraSelect(cameras) {
        cameraSelect.innerHTML = '';
        
        for (const [name, config] of Object.entries(cameras)) {
            const option = document.createElement('option');
            option.value = config.url;
            option.textContent = name;
            option.dataset.hasAudio = config.has_audio !== false;
            option.dataset.cameraName = name;            
            cameraSelect.appendChild(option);
        }
    }

    function selectCamera(cameraName, isNeedDispatchEvent) {
        // Find and select the option with matching camera name
        for (const option of cameraSelect.options) {
            if (option.dataset.cameraName === cameraName) {
                cameraSelect.value = option.value;
                if (isNeedDispatchEvent) {
                    cameraSelect.dispatchEvent(new Event('change'));
                }
                break;
            }
        }
    }

    async function switchCamera() {
        const selectedOption = cameraSelect.options[cameraSelect.selectedIndex];
        const url = cameraSelect.value;
        const name = selectedOption.text;
        const hasAudio = selectedOption.dataset.hasAudio === 'true';
        const cameraName = selectedOption.dataset.cameraName;

        currentCameraName = cameraName;
        currentCamera.textContent = name;

        // Update audio indicator
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
                body: JSON.stringify({ url, name, has_audio: hasAudio })
            });
            
            const data = await res.json();
            if (data.status === 'ok') {
                console.log('📷 Switched to camera:', name, 'Audio:', hasAudio);
                
                // Update stream with new camera
                streamManager.setCamera(url);
                
                // Update ROI manager
                roiManager.setCameraName(cameraName);
                await roiManager.loadROI(cameraName);
                
                showNotification('Switched to: ' + name + (hasAudio ? ' 🔊' : ' 🔇'));
            } else {
                console.error('Switch camera failed:', data.message);
                showNotification('❌ Failed to switch camera: ' + data.message);
            }
        } catch (e) {
            console.error('Error switching camera:', e);
            showNotification('❌ Error switching camera');
        }
    }

    // ===== SSE Event Handlers =====
    function handleStatusUpdate(data) {
        // Recording state
        if (data.recording_enabled !== undefined) {
            recordingEnabled = data.recording_enabled;
            recordToggle.textContent = recordingEnabled ? '📹 Recording ON' : '📹 Recording OFF';
            recordToggle.className = recordingEnabled ? 'btn btn-record' : 'btn btn-record off';
            document.getElementById('recordingState').textContent = recordingEnabled ? 'ON' : 'OFF';
        }

        // Detection state
        if (data.detection_enabled !== undefined) {
            detectionEnabled = data.detection_enabled;
            detectionToggle.textContent = detectionEnabled ? '🎯 Detection ON' : '🎯 Detection OFF';
            detectionToggle.className = detectionEnabled ? 'btn btn-detection' : 'btn btn-detection off';
        }

        // Motion status
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

        // Last recording
        if (data.last_recording) {
            console.log('📹 Last recording saved: ' + data.last_recording);
        }

        // Audio availability
        if (data.has_audio !== undefined) {
            if (data.has_audio) {
                audioIndicator.textContent = '🔊 Audio available';
                audioIndicator.className = 'audio-indicator enabled';
            } else {
                audioIndicator.textContent = '🔇 No audio';
                audioIndicator.className = 'audio-indicator disabled';
            }
        }

        // Camera name
        if (data.camera_name) {
            currentCameraName = data.camera_name;
            currentCamera.textContent = data.camera_name;
            // Update the select dropdown to match
            for (const option of cameraSelect.options) {
                if (option.dataset.cameraName === data.camera_name) {
                    cameraSelect.value = option.value;
                    break;
                }
            }
        }

        // ROI data
        if (data.roi) {
            roiManager.roiData = data.roi;
            roiManager.drawROI();
            roiManager.updateStatus();
        }

        // Update connection status
        document.getElementById('statusIndicator').className = 'status-indicator online';
        document.getElementById('connectionStatus').textContent = 'Connected';
        document.getElementById('connectionStatus').style.color = '#4CAF50';
    }

    // ===== Control Functions =====
    async function toggleRecording() {
        recordingEnabled = !recordingEnabled;
        recordToggle.textContent = recordingEnabled ? '📹 Recording ON' : '📹 Recording OFF';
        recordToggle.className = recordingEnabled ? 'btn btn-record' : 'btn btn-record off';
        document.getElementById('recordingState').textContent = recordingEnabled ? 'ON' : 'OFF';

        try {
            const res = await fetch('/toggle_recording', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: recordingEnabled })
            });
            const data = await res.json();
            if (data.status !== 'ok') {
                console.error('Toggle recording failed:', data.message);
            }
        } catch (e) {
            console.error('Error toggling recording:', e);
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
            const data = await res.json();
            if (data.status !== 'ok') {
                console.error('Toggle detection failed:', data.message);
            }
        } catch (e) {
            console.error('Error toggling detection:', e);
        }
    }

    function toggleAudio() {
        audioEnabled = !audioEnabled;
        audioToggle.textContent = audioEnabled ? '🔊 Audio ON' : '🔇 Audio OFF';
        audioToggle.className = audioEnabled ? 'btn btn-audio' : 'btn btn-audio off';

        if (audioEnabled) {
            playAlert();
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
            } catch (e) {
                console.log('Beep error:', e);
            }
        }
    }

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

    // ===== Canvas Event Setup =====
    function setupCanvasEvents() {
        const canvas = document.getElementById('roiCanvas');

        // Mouse events
        canvas.addEventListener('mousedown', function(e) {
            if (!roiManager.isDrawingMode) return;
            const pos = getCanvasPosition(e);
            if (pos) {
                roiManager.startDraw(pos.x, pos.y);
            }
        });

        canvas.addEventListener('mousemove', function(e) {
            if (!roiManager.isDrawing) return;
            const pos = getCanvasPosition(e);
            if (pos) {
                roiManager.moveDraw(pos.x, pos.y);
            }
        });

        canvas.addEventListener('mouseup', function(e) {
            if (!roiManager.isDrawing) return;
            const pos = getCanvasPosition(e);
            if (pos) {
                roiManager.drawEnd = pos;
            }
            roiManager.endDraw();
        });

        canvas.addEventListener('mouseleave', function() {
            if (roiManager.isDrawing) {
                roiManager.cancelDraw();
            }
        });

        // Touch events
        canvas.addEventListener('touchstart', function(e) {
            if (!roiManager.isDrawingMode) return;
            e.preventDefault();
            const touch = e.touches[0];
            const pos = getTouchPosition(touch);
            if (pos) {
                roiManager.startDraw(pos.x, pos.y);
            }
        }, { passive: false });

        canvas.addEventListener('touchmove', function(e) {
            if (!roiManager.isDrawing) return;
            e.preventDefault();
            const touch = e.touches[0];
            const pos = getTouchPosition(touch);
            if (pos) {
                roiManager.moveDraw(pos.x, pos.y);
            }
        }, { passive: false });

        canvas.addEventListener('touchend', function(e) {
            if (!roiManager.isDrawing) return;
            e.preventDefault();
            const touch = e.changedTouches[0];
            const pos = getTouchPosition(touch);
            if (pos) {
                roiManager.drawEnd = pos;
            }
            roiManager.endDraw();
        }, { passive: false });

        canvas.addEventListener('touchcancel', function() {
            if (roiManager.isDrawing) {
                roiManager.cancelDraw();
            }
        });
    }

    function getCanvasPosition(e) {
        const canvas = document.getElementById('roiCanvas');
        const rect = canvas.getBoundingClientRect();
        return {
            x: Math.max(0, Math.min(1, (e.clientX - rect.left) / canvas.width)),
            y: Math.max(0, Math.min(1, (e.clientY - rect.top) / canvas.height))
        };
    }

    function getTouchPosition(touch) {
        const canvas = document.getElementById('roiCanvas');
        const rect = canvas.getBoundingClientRect();
        return {
            x: Math.max(0, Math.min(1, (touch.clientX - rect.left) / canvas.width)),
            y: Math.max(0, Math.min(1, (touch.clientY - rect.top) / canvas.height))
        };
    }

    // ===== Event Listeners =====
    // Camera
    cameraSelect.addEventListener('change', switchCamera);

    // Stream controls
    document.getElementById('threshold').addEventListener('input', function() {
        streamManager.update();
    });
    document.getElementById('min_area').addEventListener('input', function() {
        streamManager.update();
    });

    // Buttons
    audioToggle.addEventListener('click', toggleAudio);
    recordToggle.addEventListener('click', toggleRecording);
    detectionToggle.addEventListener('click', toggleDetection);
    
    roiToggle.addEventListener('click', function() {
        roiManager.toggleROI()
            .then(() => {
                showNotification(roiManager.roiData.enabled ? '✅ ROI enabled' : '✅ ROI disabled');
            })
            .catch(err => {
                showNotification('❌ Error toggling ROI: ' + err.message);
            });
    });
    
    roiDraw.addEventListener('click', function() {
        if (roiManager.isDrawingMode) {
            roiManager.disableDrawing();
            roiDraw.textContent = '✏️ Draw ROI';
            roiDraw.className = 'btn btn-roi';
        } else {
            roiManager.enableDrawing();
            roiDraw.textContent = '✏️ Drawing... Click to cancel';
            roiDraw.className = 'btn btn-roi drawing';
            if (roiManager.isMobile) {
                roiManager.showHelp('👆 Tap and drag on the video to draw ROI. Release to save.', 'info');
            } else {
                roiManager.showHelp('💡 Click and drag on the video to draw ROI rectangle. Release to save.', 'info');
            }
        }
    });
    
    roiReset.addEventListener('click', function() {
        if (!confirm('Reset ROI to full frame?')) return;
        roiManager.resetROI()
            .then(() => {
                showNotification('🔄 ROI reset to full frame');
            })
            .catch(err => {
                showNotification('❌ Error resetting ROI: ' + err.message);
            });
    });

    // SSE Events
    sseClient.on('connected', function() {
        document.getElementById('statusIndicator').className = 'status-indicator online';
        document.getElementById('connectionStatus').textContent = 'Connected';
        document.getElementById('connectionStatus').style.color = '#4CAF50';
    });

    sseClient.on('disconnected', function() {
        document.getElementById('statusIndicator').className = 'status-indicator offline';
        document.getElementById('connectionStatus').textContent = 'Disconnected - Reconnecting...';
        document.getElementById('connectionStatus').style.color = '#f44336';
    });

    sseClient.on('message', handleStatusUpdate);

    // ROI Manager callbacks
    roiManager.onStatusUpdate = function(roiData) {
        // Update ROI state in UI
        document.getElementById('roiState').textContent = roiData.enabled ? 'Active' : 'Disabled';
    };

    // ===== Initialization =====
    function initialize() {
        // Load cameras
        loadCameras();
        
        // Setup canvas
        setupCanvasEvents();
        
        // Resize canvas on load
        window.addEventListener('load', function() {
            roiManager.resizeCanvas();
            
            // Set initial camera
            const selectedOption = cameraSelect.options[cameraSelect.selectedIndex];
            if (selectedOption) {
                currentCameraName = selectedOption.dataset.cameraName || selectedOption.text;
                currentCamera.textContent = currentCameraName;
                roiManager.setCameraName(currentCameraName);
                roiManager.loadROI(currentCameraName);
            }
            
            // Show mobile help
            if (roiManager.isMobile) {
                roiManager.showHelp('👆 Tap "Draw ROI", then drag on video to select area', 'info');
                setTimeout(() => roiManager.showHelp('', ''), 5000);
            }
        });
        
        // Resize on stream load
        document.getElementById('stream').addEventListener('load', function() {
            roiManager.resizeCanvas();
        });
        
        // Resize on window resize
        let resizeTimeout;
        window.addEventListener('resize', function() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                roiManager.resizeCanvas();
            }, 100);
        });

        // Connect SSE
        sseClient.connect();
        
        console.log('🎥 Motion Detection with ROI initialized');
        console.log('📡 SSE connected:', sseClient.isConnected);
        console.log('📱 Mobile support:', roiManager.isMobile ? 'Enabled' : 'Not detected');
    }

    // Start the application
    initialize();
});
/**
 * Highway Road Safety System - Clean, Simple Frontend Controller
 * With Vercel Deployment Support & Configurable Backend Endpoint
 */

let BACKEND_URL = localStorage.getItem('IOT_BACKEND_URL') || '';
let isMaskView = false;
let currentSource = '1';

function apiUrl(path) {
    if (!BACKEND_URL) return path;
    const base = BACKEND_URL.replace(/\/+$/, '');
    return base + (path.startsWith('/') ? path : '/' + path);
}

function updateBackendLabel() {
    const label = document.getElementById('backendLabel');
    if (!label) return;
    if (BACKEND_URL) {
        try {
            const u = new URL(BACKEND_URL);
            label.textContent = `Backend: ${u.hostname}`;
        } catch {
            label.textContent = 'Backend: Remote';
        }
    } else {
        label.textContent = 'Backend: Local';
    }
}

// ================= STARTUP =================
window.addEventListener('DOMContentLoaded', () => {
    updateBackendLabel();
    
    // Load initial on-demand snapshot (No continuous stream running)
    grabSnapshotNow();

    fetchDifferencingStatus();
    fetchSystemStatus();
    fetchLogs();
    fetchCameraStatus();
    fetchDbStatus();

    // Fast, event-driven polling (Low bandwidth, JSON only)
    setInterval(fetchDifferencingStatus, 1000);
    setInterval(fetchSystemStatus, 2000);
    setInterval(fetchLogs, 3500);
    setInterval(fetchDbStatus, 6000);
});

// ================= BACKEND URL MODAL (VERCEL HOSTING) =================
function openBackendModal() {
    const input = document.getElementById('backendUrlInput');
    if (input) input.value = BACKEND_URL;
    document.getElementById('backendModal').style.display = 'flex';
}

function closeBackendModal() {
    document.getElementById('backendModal').style.display = 'none';
}

function saveBackendUrl() {
    const input = document.getElementById('backendUrlInput');
    let val = input ? input.value.trim() : '';
    if (val && !val.startsWith('http://') && !val.startsWith('https://')) {
        val = 'http://' + val;
    }
    BACKEND_URL = val;
    localStorage.setItem('IOT_BACKEND_URL', val);
    updateBackendLabel();
    closeBackendModal();

    // Refresh telemetry and captured snapshot
    grabSnapshotNow();
    fetchDifferencingStatus();
    fetchSystemStatus();
    fetchLogs();
    fetchDbStatus();
    fetchCameraStatus();
}

// ================= FRAME DIFFERENCING & CAPTURED EVIDENCE =================

// 1. Fetch Real-Time Differencing Telemetry (Variance & Constant Change Timer)
async function fetchDifferencingStatus() {
    try {
        const res = await fetch(apiUrl('/api/differencing/status'));
        if (!res.ok) return;
        const data = await res.json();

        // Update Differencing Variance Meter
        const diffText = document.getElementById('diffPctText');
        const diffBar = document.getElementById('diffBarFill');
        if (diffText) diffText.textContent = `${data.diff_pct.toFixed(1)}%`;
        if (diffBar) {
            diffBar.style.width = `${Math.min(100, data.diff_pct * 3.5)}%`;
        }

        // Update Constant Change Persistence Timer
        const constText = document.getElementById('constDurText');
        const constBar = document.getElementById('constBarFill');
        if (constText) constText.textContent = `${data.constant_duration.toFixed(1)}s / ${data.threshold_seconds.toFixed(1)}s`;
        if (constBar) {
            const pct = Math.min(100, (data.constant_duration / data.threshold_seconds) * 100);
            constBar.style.width = `${pct}%`;
            if (data.constant_triggered) {
                constBar.className = 'diff-bar-fill trip';
            } else if (data.diff_pct > 1.5) {
                constBar.className = 'diff-bar-fill caution';
            } else {
                constBar.className = 'diff-bar-fill';
            }
        }

        // If constant change triggered an obstruction event, update captured evidence photo
        if (data.latest_captured_incident && data.latest_captured_incident.photo_url) {
            const photoUrl = data.latest_captured_incident.photo_url;
            if (photoUrl !== lastCapturedPhotoUrl && !liveStreamActive) {
                lastCapturedPhotoUrl = photoUrl;
                const img = document.getElementById('incidentPhotoDisplay');
                if (img) {
                    img.src = apiUrl(photoUrl);
                }
            }
        }

        // Differencing Dot Indicator
        const dot = document.getElementById('differencingDot');
        if (dot) {
            dot.style.background = data.constant_triggered ? '#ef4444' : (data.diff_pct > 1.5 ? '#f59e0b' : '#10b981');
        }
    } catch (e) {}
}

// 2. Grab Single On-Demand Snapshot (Zero Streaming Overhead)
function grabSnapshotNow() {
    const img = document.getElementById('incidentPhotoDisplay');
    if (img && !liveStreamActive) {
        img.src = apiUrl(`/api/camera/snapshot?view=${isMaskView ? 'mask' : 'live'}&_=${Date.now()}`);
    }
}

// 3. Optional Live Stream Toggle (User must explicitly activate)
function toggleLiveStream() {
    const img = document.getElementById('incidentPhotoDisplay');
    const btn = document.getElementById('streamToggleBtn');
    liveStreamActive = !liveStreamActive;

    if (liveStreamActive) {
        img.src = apiUrl(`/api/camera/stream?view=${isMaskView ? 'mask' : 'live'}&_=${Date.now()}`);
        if (btn) {
            btn.textContent = '⏹️ Stop Stream';
            btn.style.background = '#fee2e2';
            btn.style.color = '#b91c1c';
        }
    } else {
        grabSnapshotNow();
        if (btn) {
            btn.textContent = '▶️ Live Stream';
            btn.style.background = 'var(--bg-white)';
            btn.style.color = 'var(--text-primary)';
        }
    }
}

// 4. One-Click Road Baseline Calibration
async function calibrateRoadBackground() {
    const badge = document.getElementById('calibBadge');
    if (badge) badge.textContent = '⏳ Calibrating...';

    try {
        const res = await fetch(apiUrl('/api/camera/calibrate'), { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            if (badge) {
                badge.textContent = '● Baseline Locked';
                badge.style.background = '#ecfdf5';
                badge.style.color = '#047857';
            }
            grabSnapshotNow();
            alert('🎯 Clean road baseline calibrated successfully!\nFrame differencing will now compute deltas against this reference.');
        } else {
            alert('Calibration notice: ' + data.message);
        }
    } catch (e) {
        alert('Could not calibrate: server unreachable at ' + (BACKEND_URL || 'localhost'));
    }
}

// 5. Toggle Edge Differential Mask View
function toggleEdgeMask() {
    const btn = document.getElementById('maskToggleBtn');
    isMaskView = !isMaskView;

    if (isMaskView) {
        if (btn) btn.textContent = '🎥 View Normal Photo';
    } else {
        if (btn) btn.textContent = '⚡ View Edge Mask';
    }

    if (liveStreamActive) {
        const img = document.getElementById('incidentPhotoDisplay');
        if (img) img.src = apiUrl(`/api/camera/stream?view=${isMaskView ? 'mask' : 'live'}&_=${Date.now()}`);
    } else {
        grabSnapshotNow();
    }
}

// 6. Change Camera Source (Local Cam, ESP32-CAM, Demo Video)
async function changeCameraSource(newSource) {
    try {
        const res = await fetch(apiUrl('/api/camera/source'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: newSource })
        });
        currentSource = newSource;
        setTimeout(grabSnapshotNow, 500);
    } catch (e) {
        alert('Failed to switch camera source');
    }
}

async function fetchCameraStatus() {
    try {
        const res = await fetch(apiUrl('/api/camera/calibration'));
        const data = await res.json();
        const badge = document.getElementById('calibBadge');
        if (badge) {
            badge.textContent = data.calibrated ? '● Background Calibrated' : '○ Auto-Learning Background';
        }
        const select = document.getElementById('cameraSourceSelect');
        if (select && data.active_source) {
            select.value = data.active_source;
        }
    } catch (e) {}
}

// ================= SYSTEM STATUS & HAZARD MONITORING =================
async function fetchSystemStatus() {
    try {
        const res = await fetch(apiUrl('/api/stats'));
        const data = await res.json();

        const pill = document.getElementById('systemStatusPill');
        const pillText = document.getElementById('systemStatusText');
        const card = document.getElementById('hazardCard');
        const title = document.getElementById('hazardTitle');
        const desc = document.getElementById('hazardDesc');
        const banner = document.getElementById('videoOverlayBanner');

        if (data.active_hazard && data.active_hazard.status === 'DANGER') {
            const h = data.active_hazard;
            
            // Red Danger State
            if (pill) pill.className = 'status-pill status-pill-danger';
            if (pillText) pillText.textContent = `! OBSTRUCTION: ${h.type} !`;

            if (card) card.style.borderLeftColor = 'var(--status-danger)';
            if (title) {
                title.textContent = `🚨 OBSTRUCTION: ${h.type}`;
                title.style.color = '#b91c1c';
            }
            if (desc) {
                desc.textContent = `Stationary hazard detected in Lane 1 (Duration: ${h.duration}s). LoRa warning packet dispatched to in-cabin driver units in < 1ms.`;
            }
            if (banner) {
                banner.className = 'video-overlay-banner banner-danger';
                banner.textContent = `! DANGER: ${h.type} (${h.duration}s) !`;
            }
        } else {
            // Green Clear State
            if (pill) pill.className = 'status-pill status-pill-clear';
            if (pillText) pillText.textContent = 'LANE CLEAR';

            if (card) card.style.borderLeftColor = 'var(--status-online)';
            if (title) {
                title.textContent = 'ALL LANES CLEAR';
                title.style.color = '#047857';
            }
            if (desc) {
                desc.textContent = 'No obstructions detected. Monitoring vehicle corridor at 25 FPS.';
            }
            if (banner) {
                banner.className = 'video-overlay-banner banner-clear';
                banner.textContent = '● ROADWAY CLEAR';
            }
        }
    } catch (e) {}
}

// ================= TEST IN-CABIN DRIVER ALARM =================
async function testDriverAlarm() {
    try {
        const res = await fetch(apiUrl('/api/devices/ESP32-RX-01/test-alarm'), { method: 'POST' });
        const data = await res.json();
        alert(`🔊 In-Cabin Warning Test:\n${data.message}`);
    } catch (e) {
        alert('Could not trigger in-cabin test alarm');
    }
}

// ================= RECENT INCIDENT LOGS & EVIDENCE =================
async function fetchLogs() {
    try {
        const res = await fetch(apiUrl('/api/logs'));
        const logs = await res.json();
        renderLogsTable(logs);
    } catch (e) {}
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('logsTbody');
    if (!tbody) return;

    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">No obstructions recorded yet. System is clear.</td></tr>';
        return;
    }

    tbody.innerHTML = logs.slice(0, 10).map(l => `
        <tr>
            <td style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600;">${l.timestamp}</td>
            <td><span style="font-family: var(--font-mono); font-size: 0.78rem; background: var(--bg-subtle); padding: 2px 6px; border-radius: 4px;">${l.device_id}</span></td>
            <td style="font-weight: 600;">${l.event}</td>
            <td>
                <span class="status-dot ${l.severity === 'Critical' ? 'badge-alert' : 'badge-online'}" style="font-size: 0.72rem; padding: 2px 8px;">
                    ${l.severity}
                </span>
            </td>
            <td>${l.duration}</td>
            <td>
                ${l.has_photo ? `
                    <img src="${l.photo_url.startsWith('data:') ? l.photo_url : apiUrl(l.photo_url)}" class="photo-thumb" alt="Evidence" onclick="openPhotoModal('${l.photo_url.startsWith('data:') ? l.photo_url : apiUrl(l.photo_url)}', '${l.timestamp}', '${l.event}')" title="Click to enlarge">
                ` : `<span style="color: var(--text-muted); font-size: 0.75rem;">No photo</span>`}
            </td>
        </tr>
    `).join('');
}

// ================= PHOTO LIGHTBOX =================
function openPhotoModal(url, timestamp, title) {
    const modal = document.getElementById('photoModal');
    const img = document.getElementById('photoModalImg');
    const caption = document.getElementById('photoModalCaption');

    img.src = url;
    caption.textContent = `Incident: ${title} | Recorded at: ${timestamp}`;
    modal.style.display = 'flex';
}

function closePhotoModal() {
    document.getElementById('photoModal').style.display = 'none';
}

// ================= DOKPLOY POSTGRESQL MODAL =================
function openDbModal() {
    document.getElementById('dbModal').style.display = 'flex';
}

function closeDbModal() {
    document.getElementById('dbModal').style.display = 'none';
}

async function fetchDbStatus() {
    try {
        const res = await fetch(apiUrl('/api/database/status'));
        const db = await res.json();
        const label = document.getElementById('dbStatusLabel');
        const input = document.getElementById('dbUriInput');
        const statusNote = document.getElementById('dbModalStatus');

        if (db.connected) {
            if (label) label.textContent = 'Database: Dokploy';
            if (statusNote) {
                statusNote.style.color = '#047857';
                statusNote.textContent = '● Connected to Dokploy PostgreSQL';
            }
            if (input && !input.value && db.url_masked) {
                input.placeholder = db.url_masked;
            }
        } else {
            if (label) label.textContent = 'Database: SQLite (Local)';
            if (statusNote) {
                statusNote.style.color = '#b45309';
                statusNote.textContent = '● Running SQLite fallback. Enter Dokploy URI to connect.';
            }
        }
    } catch (e) {}
}

async function connectDokployDatabase() {
    const uri = document.getElementById('dbUriInput').value.trim();
    if (!uri) {
        alert('Please enter your Dokploy PostgreSQL URI');
        return;
    }

    const statusNote = document.getElementById('dbModalStatus');
    if (statusNote) statusNote.textContent = 'Connecting to Dokploy...';

    try {
        const res = await fetch(apiUrl('/api/database/connect'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ database_url: uri })
        });
        const data = await res.json();
        if (data.success) {
            alert('🎉 Connected to Dokploy PostgreSQL!\nSchema created and synced.');
            closeDbModal();
            fetchDbStatus();
            fetchLogs();
        } else {
            alert('❌ Connection failed: ' + data.message);
            if (statusNote) {
                statusNote.style.color = '#dc2626';
                statusNote.textContent = 'Error: ' + data.message;
            }
        }
    } catch (e) {
        alert('Failed to send connection request');
    }
}

/**
 * Highway Road Safety System - Clean, Simple Frontend Controller
 * Effortless, intuitive, zero-clutter operation.
 */

let isMaskView = false;
let currentSource = '1';

// ================= STARTUP =================
window.addEventListener('DOMContentLoaded', () => {
    fetchSystemStatus();
    fetchLogs();
    fetchCameraStatus();
    fetchDbStatus();

    // Fast, lightweight polling
    setInterval(fetchSystemStatus, 1500);
    setInterval(fetchLogs, 3000);
    setInterval(fetchDbStatus, 6000);
});

// ================= LIVE CAMERA CONTROLS =================

// 1. One-Click Road Background Calibration
async function calibrateRoadBackground() {
    const badge = document.getElementById('calibBadge');
    if (badge) badge.textContent = '⏳ Calibrating...';

    try {
        const res = await fetch('/api/camera/calibrate', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            if (badge) {
                badge.textContent = '● Background Calibrated';
                badge.style.background = '#ecfdf5';
                badge.style.color = '#047857';
            }
            alert('🎯 Clean road background calibrated successfully!\nThe edge detector is now locked to this baseline.');
        } else {
            alert('Calibration notice: ' + data.message);
        }
    } catch (e) {
        alert('Could not calibrate background: server unreachable');
    }
}

// 2. Toggle Edge Differential Mask
function toggleEdgeMask() {
    const img = document.getElementById('liveVideoFeed');
    const btn = document.getElementById('maskToggleBtn');
    isMaskView = !isMaskView;

    if (isMaskView) {
        img.src = `/api/camera/stream?view=mask&_=${Date.now()}`;
        btn.textContent = '🎥 View Normal Camera';
    } else {
        img.src = `/api/camera/stream?view=live&_=${Date.now()}`;
        btn.textContent = '⚡ View Edge Mask';
    }
}

// 3. Change Camera Source (Local Cam, ESP32-CAM, Demo Video)
async function changeCameraSource(newSource) {
    try {
        const res = await fetch('/api/camera/source', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: newSource })
        });
        const data = await res.json();
        currentSource = newSource;
        
        // Reload video feed after source switch
        setTimeout(() => {
            const img = document.getElementById('liveVideoFeed');
            if (img) {
                img.src = `/api/camera/stream?view=${isMaskView ? 'mask' : 'live'}&_=${Date.now()}`;
            }
        }, 500);
    } catch (e) {
        alert('Failed to switch camera source');
    }
}

async function fetchCameraStatus() {
    try {
        const res = await fetch('/api/camera/calibration');
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
        const res = await fetch('/api/stats');
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
        const res = await fetch('/api/devices/ESP32-RX-01/test-alarm', { method: 'POST' });
        const data = await res.json();
        alert(`🔊 In-Cabin Warning Test:\n${data.message}`);
    } catch (e) {
        alert('Could not trigger in-cabin test alarm');
    }
}

// ================= RECENT INCIDENT LOGS & EVIDENCE =================
async function fetchLogs() {
    try {
        const res = await fetch('/api/logs');
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
                    <img src="${l.photo_url}" class="photo-thumb" alt="Evidence" onclick="openPhotoModal('${l.photo_url}', '${l.timestamp}', '${l.event}')" title="Click to enlarge">
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
        const res = await fetch('/api/database/status');
        const db = await res.json();
        const label = document.getElementById('dbStatusLabel');
        const input = document.getElementById('dbUriInput');
        const statusNote = document.getElementById('dbModalStatus');

        if (db.connected) {
            if (label) label.textContent = 'Database: PostgreSQL (Dokploy)';
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
        const res = await fetch('/api/database/connect', {
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

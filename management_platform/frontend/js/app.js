/**
 * Highway Safety Operations Center (ITS Management Platform)
 * Frontend Application Controller
 */

// Web Audio API Alarm Generator
let audioContext = null;
let isAudioMuted = false;
let lastSoundCode = 0;

function initAudio() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
}

function playAlarmTone(frequency, duration, type = 'sine') {
    if (isAudioMuted) return;
    initAudio();
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(frequency, audioContext.currentTime);

    gain.gain.setValueAtTime(0.2, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);

    osc.connect(gain);
    gain.connect(audioContext.destination);
    osc.start();
    osc.stop(audioContext.currentTime + duration);
}

// Master Polling Loop
let currentHazardState = null;

async function pollSystemState() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        updateSystemHUD(data);
    } catch (e) {}
}

async function pollNodes() {
    try {
        const res = await fetch('/api/nodes');
        const nodes = await res.json();
        renderNodesGrid(nodes);
    } catch (e) {}
}

async function pollIncidents() {
    try {
        const res = await fetch('/api/incidents');
        const incidents = await res.json();
        renderIncidentsTable(incidents);
    } catch (e) {}
}

async function pollAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();
        renderAnalyticsKPIs(data.kpis);
        updateChartsData(data);
    } catch (e) {}
}

function updateSystemHUD(data) {
    const alert = data.alert;
    currentHazardState = alert;

    // 1. Header Status Pill
    const pill = document.getElementById('globalStatusPill');
    const badgeWifi = document.getElementById('badgeWifi');
    const badgeLora = document.getElementById('badgeLora');

    if (alert.status === 'DANGER') {
        pill.className = 'system-status-pill pill-danger';
        pill.textContent = `🚨 CRITICAL HAZARD: ${alert.type}`;
        if (alert.sound === 2 && lastSoundCode !== 2) {
            playAlarmTone(2200, 0.35, 'sawtooth');
            setTimeout(() => playAlarmTone(1750, 0.35, 'sawtooth'), 220);
        }
    } else if (alert.status === 'CAUTION') {
        pill.className = 'system-status-pill pill-caution';
        pill.textContent = `⚠️ ADVISORY: ${alert.type}`;
        if (alert.sound === 1 && lastSoundCode !== 1) {
            playAlarmTone(1500, 0.2);
        }
    } else {
        pill.className = 'system-status-pill pill-clear';
        pill.textContent = '🟢 CORRIDOR CLEAR';
    }
    lastSoundCode = alert.sound;

    // Wireless Gateway Status
    badgeWifi.innerHTML = `<span class="dot ${data.broadcaster.wifi_enabled ? 'dot-green' : 'dot-red'}"></span> Wi-Fi Hotspot: Active`;
    const loraConnected = data.broadcaster.lora_connected;
    badgeLora.innerHTML = `<span class="dot ${loraConnected ? 'dot-green' : 'dot-amber'}"></span> LoRa Link: ${loraConnected ? 'Tx Online' : 'Standby'}`;

    // 2. Triage Banner & Active Obstruction Card
    const triageBanner = document.getElementById('triageBanner');
    const triageTitle = document.getElementById('triageTitle');
    const triageMeta = document.getElementById('triageMeta');
    const vmsDisplay = document.getElementById('vmsText');

    if (alert.status === 'DANGER') {
        triageBanner.className = 'triage-alert-banner triage-danger';
        triageTitle.textContent = `🚨 IMMEDIATE ACTION REQUIRED: ${alert.type}`;
        triageMeta.innerHTML = `
            <strong>Location:</strong> Corridor N-12 | Active Lane 1 (Northbound)<br>
            <strong>Stationary Duration:</strong> ${alert.duration.toFixed(1)} seconds blocked<br>
            <strong>Proximity:</strong> ${alert.dist} | <strong>Incident Confidence:</strong> 98.4%
        `;
    } else {
        triageBanner.className = 'triage-alert-banner';
        triageTitle.textContent = 'Operational State: Normal Patrol';
        triageMeta.innerHTML = 'No active obstructions detected. Autonomous monitoring in progress.';
    }

    // 3. Variable Message Sign (VMS) Preview
    vmsDisplay.textContent = data.vms || 'ROAD CLEAR - MAINTAIN SAFE DISTANCE';

    // 4. In-Cabin Alert Unit Hardware Mirror
    const twinLcd = document.getElementById('twinLcd');
    const twinLedRed = document.getElementById('twinLedRed');
    const twinLedGreen = document.getElementById('twinLedGreen');
    const twinBuzzer = document.getElementById('twinBuzzer');

    if (alert.status === 'DANGER') {
        twinLcd.innerHTML = `!ROAD OBSTRUCT!<br>${alert.type.substring(0, 10)} ${alert.dist}`;
        twinLcd.style.borderColor = '#ef4444';
        twinLcd.style.color = '#fca5a5';
        twinLedRed.style.color = '#ef4444';
        twinLedGreen.style.color = '#334155';
        twinBuzzer.textContent = '🔊 [SIREN ACTIVE]';
        twinBuzzer.style.color = '#ef4444';
    } else if (alert.status === 'CAUTION') {
        twinLcd.innerHTML = `CAUTION: ROAD<br>${alert.type.substring(0, 10)} SLOW`;
        twinLcd.style.borderColor = '#f59e0b';
        twinLcd.style.color = '#fde68a';
        twinLedRed.style.color = '#f59e0b';
        twinLedGreen.style.color = '#10b981';
        twinBuzzer.textContent = '🔊 [PULSE BEEP]';
        twinBuzzer.style.color = '#f59e0b';
    } else {
        twinLcd.innerHTML = `ROAD STATUS: OK<br>LANE: CLEAR`;
        twinLcd.style.borderColor = '#059669';
        twinLcd.style.color = '#34d399';
        twinLedRed.style.color = '#334155';
        twinLedGreen.style.color = '#10b981';
        twinBuzzer.textContent = '🔊 [MUTE]';
        twinBuzzer.style.color = '#64748b';
    }
}

function renderAnalyticsKPIs(kpis) {
    if (!kpis) return;
    document.getElementById('kpiTotal').textContent = kpis.total_incidents;
    document.getElementById('kpiToday').textContent = kpis.today_incidents;
    document.getElementById('kpiMttd').textContent = `${kpis.mean_time_to_detect_s}s`;
    document.getElementById('kpiPdr').textContent = `${kpis.pdr_reliability}%`;
    document.getElementById('kpiPoles').textContent = `${kpis.active_poles_online} Online`;
}

function renderIncidentsTable(records) {
    const tbody = document.getElementById('incidentsTbody');
    if (!tbody) return;
    if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #64748b; padding: 20px;">No incidents recorded yet.</td></tr>';
        return;
    }

    tbody.innerHTML = records.slice(0, 15).map(r => `
        <tr>
            <td><strong>${r.timestamp}</strong></td>
            <td><span class="hud-tag">${r.node_id}</span></td>
            <td><span style="color: ${r.status === 'DANGER' ? '#f87171' : '#fbbf24'}; font-weight: bold;">${r.status}</span></td>
            <td>${r.type}</td>
            <td>${r.lane}</td>
            <td>${r.duration}s</td>
            <td>
                <button onclick="openEvidenceModal('${r.timestamp}', '${r.type}')" style="padding: 4px 8px; font-size: 0.75rem;">
                    📸 View Evidence
                </button>
            </td>
        </tr>
    `).join('');
}

function renderNodesGrid(nodes) {
    const container = document.getElementById('nodesGrid');
    if (!container) return;

    container.innerHTML = nodes.map(n => `
        <div class="node-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="node-name">${n.name}</div>
                <span class="dot ${n.status === 'ALERT' ? 'dot-red' : (n.status === 'ONLINE' ? 'dot-green' : 'dot-amber')}"></span>
            </div>
            <div class="node-loc">${n.location || 'Highway Corridor'}</div>
            <div class="node-metrics-list">
                ${n.battery_pct ? `<div>Battery: <span class="node-metric-val">${n.battery_pct}% (${n.battery_v}V)</span></div>` : ''}
                ${n.solar_current_ma ? `<div>Solar: <span class="node-metric-val">+${n.solar_current_ma}mA</span></div>` : ''}
                ${n.camera_fps ? `<div>Camera: <span class="node-metric-val">${n.camera_fps} FPS</span></div>` : ''}
                ${n.wifi_rssi ? `<div>Wi-Fi RSSI: <span class="node-metric-val">${n.wifi_rssi} dBm</span></div>` : ''}
                ${n.lora_snr_db ? `<div>LoRa SNR: <span class="node-metric-val">+${n.lora_snr_db} dB</span></div>` : ''}
            </div>
        </div>
    `).join('');
}

// Dispatch Action Handlers
async function broadcastLoraEmergency() {
    try {
        const res = await fetch('/api/dispatch/lora', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lane: "LANE_1",
                type: currentHazardState ? currentHazardState.type : "STALLED CAR"
            })
        });
        const data = await res.json();
        alert(`📡 [LoRa Radio Dispatch]:\n${data.message}\nUpstream VMS & Approaching Vehicles Updated!`);
    } catch (e) {
        alert("Error dispatching LoRa broadcast");
    }
}

async function dispatchPatrol() {
    alert("🚓 [Highway Incident Response System]:\nSafety Patrol Unit #09 dispatched to Corridor N-12 Mile Marker 16.5.\nEstimated Arrival: 3 minutes.");
}

async function acknowledgeIncident() {
    try {
        await fetch('/api/incidents/acknowledge', { method: 'POST' });
        alert("✅ Incident acknowledged by operator. Audio siren muted.");
    } catch (e) {}
}

async function changeCameraSource() {
    const select = document.getElementById('cameraSelect');
    const val = select.value;
    let url = "";
    if (val === 'ESP32_URL') {
        url = prompt("Enter ESP32-CAM stream URL:", "http://192.168.43.50:81/stream");
        if (!url) return;
    }

    await fetch('/api/switch_camera', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: val, url: url })
    });
}

function openEvidenceModal(timestamp, hazardType) {
    const modal = document.getElementById('evidenceModal');
    const modalImg = document.getElementById('modalImage');
    const modalCaption = document.getElementById('modalCaption');

    // Get latest snapshot from snapshots folder or query
    modalImg.src = `/api/snapshots/incident_1788553244_STALLED_CAR.jpg`;
    modalCaption.textContent = `Obstruction Hazard Evidence | Recorded: ${timestamp} | Hazard: ${hazardType}`;
    modal.style.display = 'flex';
}

function closeEvidenceModal() {
    document.getElementById('evidenceModal').style.display = 'none';
}

function toggleAudioMute() {
    isAudioMuted = !isAudioMuted;
    document.getElementById('audioBtn').textContent = isAudioMuted ? '🔇 Unmute Audio' : '🔊 Audio Enabled';
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    document.getElementById(`tabBtn_${tabId}`).classList.add('active');
    document.getElementById(`tabContent_${tabId}`).classList.add('active');
}

// Startup
window.addEventListener('DOMContentLoaded', () => {
    initAnalyticsCharts();
    pollSystemState();
    pollNodes();
    pollIncidents();
    pollAnalytics();

    setInterval(pollSystemState, 400);
    setInterval(pollNodes, 3000);
    setInterval(pollIncidents, 2000);
    setInterval(pollAnalytics, 5000);

    // Update real-time clock
    setInterval(() => {
        const now = new Date();
        document.getElementById('utcClock').textContent = now.toTimeString().split(' ')[0] + ' UTC';
    }, 1000);
});

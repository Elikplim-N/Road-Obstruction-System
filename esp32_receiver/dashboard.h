#ifndef RECEIVER_DASHBOARD_H
#define RECEIVER_DASHBOARD_H

#include <Arduino.h>

const char RECEIVER_DASHBOARD_HTML[] PROGMEM = R"=====(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>In-Cabin Driver HUD — Road Obstruction Alert</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800;900&family=JetBrains+Mono:wght@600;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(22, 30, 46, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-red: #ef4444;
      --primary: #3b82f6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 16px;
      overflow-x: hidden;
      transition: background 0.3s ease;
    }
    body.hazard-active {
      background: #20070b;
    }
    .hud-container {
      width: 100%;
      max-width: 480px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 18px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      backdrop-filter: blur(12px);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 800;
      font-size: 0.95rem;
      letter-spacing: -0.01em;
    }
    .brand-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--accent-green);
      box-shadow: 0 0 10px var(--accent-green);
    }
    .badge-comm {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      padding: 4px 10px;
      border-radius: 20px;
      background: rgba(59, 130, 246, 0.15);
      border: 1px solid rgba(59, 130, 246, 0.3);
      color: #93c5fd;
      font-weight: 700;
    }
    .alert-card {
      background: var(--card-bg);
      border: 2px solid var(--border);
      border-radius: 24px;
      padding: 28px 20px;
      text-align: center;
      backdrop-filter: blur(16px);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    body.hazard-active .alert-card {
      border-color: var(--accent-red);
      box-shadow: 0 0 40px rgba(239, 68, 68, 0.35);
      animation: alertPulse 1.2s infinite alternate;
    }
    @keyframes alertPulse {
      from { transform: scale(1); }
      to { transform: scale(1.015); }
    }
    .status-icon {
      font-size: 3.5rem;
      margin-bottom: 12px;
      line-height: 1;
    }
    .status-title {
      font-size: 1.6rem;
      font-weight: 900;
      letter-spacing: -0.02em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .status-desc {
      font-size: 0.9rem;
      color: var(--text-muted);
      font-weight: 600;
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 20px;
    }
    .metric-tile {
      background: rgba(11, 15, 25, 0.6);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      text-align: left;
    }
    .metric-label {
      font-size: 0.72rem;
      text-transform: uppercase;
      color: var(--text-muted);
      font-weight: 700;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }
    .metric-val {
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.25rem;
      font-weight: 800;
      color: var(--text-main);
    }
    .hardware-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px 20px;
      backdrop-filter: blur(12px);
    }
    .hw-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .hw-title {
      font-size: 0.82rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    .hw-item {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      font-size: 0.85rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .hw-item:last-child { border-bottom: none; }
    .hw-label { color: var(--text-muted); }
    .hw-val { font-family: 'JetBrains Mono', monospace; font-weight: 700; }
    .controls {
      display: flex;
      gap: 10px;
    }
    .btn {
      flex: 1;
      padding: 14px;
      border-radius: 14px;
      font-size: 0.88rem;
      font-weight: 800;
      cursor: pointer;
      border: 1px solid var(--border);
      transition: all 0.15s ease;
      text-align: center;
    }
    .btn:active { transform: scale(0.97); }
    .btn-test {
      background: rgba(59, 130, 246, 0.12);
      border-color: rgba(59, 130, 246, 0.3);
      color: #93c5fd;
    }
    .btn-mute {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-main);
    }
  </style>
</head>
<body>
  <div class="hud-container">
    <header>
      <div class="brand">
        <div class="brand-dot" id="brand-dot"></div>
        <span>ESP32 HUD RECEIVER</span>
      </div>
      <div class="badge-comm" id="comm-badge">DUAL LINK</div>
    </header>

    <div class="alert-card" id="alert-card">
      <div class="status-icon" id="status-icon">🛡️</div>
      <div class="status-title" id="status-title" style="color: var(--accent-green);">ROAD CLEAR</div>
      <div class="status-desc" id="status-desc">No stationary road obstacles detected</div>

      <div class="metrics-grid">
        <div class="metric-tile">
          <div class="metric-label">Hazard Type</div>
          <div class="metric-val" id="metric-type">NONE</div>
        </div>
        <div class="metric-tile">
          <div class="metric-label">Proximity</div>
          <div class="metric-val" id="metric-dist">SAFE</div>
        </div>
        <div class="metric-tile">
          <div class="metric-label">Corridor Lane</div>
          <div class="metric-val" id="metric-lane">LANE 1</div>
        </div>
        <div class="metric-tile">
          <div class="metric-label">Packet Count</div>
          <div class="metric-val" id="metric-pkts">0</div>
        </div>
      </div>
    </div>

    <div class="hardware-card">
      <div class="hw-header">
        <span class="hw-title">Receiver Telemetry</span>
        <span style="font-size:0.75rem; color:var(--text-muted);" id="last-seen">Scanning...</span>
      </div>
      <div class="hw-item">
        <span class="hw-label">Active Channel</span>
        <span class="hw-val" id="hw-channel" style="color:#60a5fa;">Wi-Fi UDP + LoRa</span>
      </div>
      <div class="hw-item">
        <span class="hw-label">LCD Display</span>
        <span class="hw-val" id="hw-lcd" style="color:var(--accent-green);">16x2 I2C OK</span>
      </div>
      <div class="hw-item">
        <span class="hw-label">Audio Buzzer Pin</span>
        <span class="hw-val">GPIO 25 (PWM)</span>
      </div>
      <div class="hw-item">
        <span class="hw-label">Firmware Version</span>
        <span class="hw-val">v2.2 Production</span>
      </div>
    </div>

    <div class="controls">
      <button class="btn btn-test" onclick="triggerTestAlarm()">⚡ Sound Test</button>
      <button class="btn btn-mute" id="mute-btn" onclick="toggleMute()">🔔 Buzzer: ON</button>
    </div>
  </div>

  <script>
    let isMuted = false;
    let packetCount = 0;

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        renderStatus(data);
      } catch (err) {
        document.getElementById('last-seen').textContent = "Offline / Reconnecting";
      }
    }

    function renderStatus(data) {
      const isDanger = data.status === "DANGER";
      const isCaution = data.status === "CAUTION";
      document.body.classList.toggle('hazard-active', isDanger || isCaution);

      const title = document.getElementById('status-title');
      const icon = document.getElementById('status-icon');
      const desc = document.getElementById('status-desc');
      const dot = document.getElementById('brand-dot');

      if (isDanger) {
        title.textContent = "! OBSTRUCTION DETECTED !";
        title.style.color = "var(--accent-red)";
        icon.textContent = "🚨";
        desc.textContent = "Immediate danger ahead: Slow down & change lanes";
        dot.style.background = "var(--accent-red)";
        dot.style.boxShadow = "0 0 10px var(--accent-red)";
      } else if (isCaution) {
        title.textContent = "CAUTION: SLOW TRAFFIC";
        title.style.color = "var(--accent-amber)";
        icon.textContent = "⚠️";
        desc.textContent = "Potential hazard flagged upstream";
        dot.style.background = "var(--accent-amber)";
        dot.style.boxShadow = "0 0 10px var(--accent-amber)";
      } else {
        title.textContent = "ROAD CLEAR";
        title.style.color = "var(--accent-green)";
        icon.textContent = "🛡️";
        desc.textContent = "Highway corridor free of stationary blockages";
        dot.style.background = "var(--accent-green)";
        dot.style.boxShadow = "0 0 10px var(--accent-green)";
      }

      document.getElementById('metric-type').textContent = data.type || "NONE";
      document.getElementById('metric-dist').textContent = data.dist || "SAFE";
      document.getElementById('metric-lane').textContent = data.lane || "LANE 1";
      document.getElementById('metric-pkts').textContent = data.packets || ++packetCount;
      document.getElementById('comm-badge').textContent = (data.channel || "DUAL").toUpperCase();
      document.getElementById('last-seen').textContent = "Live sync (<50ms)";
    }

    async function triggerTestAlarm() {
      try {
        await fetch('/api/test-alarm', { method: 'POST' });
      } catch(e) {}
    }

    async function toggleMute() {
      isMuted = !isMuted;
      try {
        await fetch('/api/mute?val=' + (isMuted ? '1' : '0'), { method: 'POST' });
        document.getElementById('mute-btn').textContent = isMuted ? '🔕 Buzzer: MUTED' : '🔔 Buzzer: ON';
      } catch(e) {}
    }

    setInterval(fetchStatus, 500);
    fetchStatus();
  </script>
</body>
</html>
)=====";

#endif

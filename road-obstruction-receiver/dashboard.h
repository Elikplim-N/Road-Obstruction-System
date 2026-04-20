#ifndef DASHBOARD_H
#define DASHBOARD_H

#include <Arduino.h>

const char PWA_DASHBOARD[] PROGMEM = R"=====(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RoadHUD — Precision Alert System</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
  <style>
    :root { --bg: #030712; --card: rgba(15, 23, 42, 0.75); --primary: #38bdf8; --danger: #f43f5e; --text: #f8fafc; --sub: #94a3b8; }
    body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 20px; overflow-x: hidden; min-height: 100vh; display: flex; flex-direction: column; }
    .radar-bg { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100vw; height: 100vw; z-index: -1; opacity: 0.1; pointer-events: none; }
    .pulse { position: absolute; border: 1px solid var(--primary); border-radius: 50%; top: 50%; left: 50%; transform: translate(-50%, -50%); animation: pulse-anim 4s infinite linear; opacity: 0; }
    @keyframes pulse-anim { 0% { width: 0; height: 0; opacity: 1; } 100% { width: 100%; height: 100%; opacity: 0; } }
    .hud { max-width: 500px; width: 100%; margin: auto; z-index: 10; }
    .panel { background: var(--card); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.08); border-radius: 32px; padding: 32px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.8); margin-bottom: 24px; text-align: center; }
    h1 { font-size: 11px; text-transform: uppercase; letter-spacing: 4px; color: var(--sub); margin: 0 0 32px 0; font-weight: 700; opacity: 0.8; }
    .rssi-ring { width: 180px; height: 180px; margin: 0 auto 24px auto; position: relative; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid rgba(56,189,248,0.1); box-shadow: inset 0 0 40px rgba(56,189,248,0.05); }
    .rssi-ring::after { content: ''; position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid var(--primary); clip-path: inset(0 0 50% 0); animation: spin 3s infinite linear; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .rssi-val { font-size: 48px; font-weight: 900; color: var(--text); letter-spacing: -2px; }
    .rssi-unit { font-size: 11px; color: var(--sub); display: block; margin-top: -8px; font-weight: 700; }
    .dist-label { font-size: 11px; color: var(--sub); margin-bottom: 4px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .dist-val { color: var(--primary); font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
    .status-pill { display: inline-flex; align-items: center; gap: 8px; padding: 6px 16px; border-radius: 100px; background: rgba(56,189,248,0.1); border: 1px solid var(--primary); color: var(--primary); font-size: 12px; font-weight: 700; margin-top: 32px; transition: 0.3s; }
    .indicator-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--primary); box-shadow: 0 0 8px var(--primary); animation: blink 1s infinite alternate; }
    @keyframes blink { from { opacity: 1; scale: 1.2; } to { opacity: 0.3; scale: 0.8; } }
    .alert-banner { display: none; position: fixed; top: 0; left: 0; right: 0; background: var(--danger); color: white; padding: 18px; text-align: center; font-weight: 900; z-index: 100; font-size: 14px; letter-spacing: 1px; box-shadow: 0 10px 30px rgba(244,63,94,0.4); }
    .alert-active .panel { border-color: var(--danger); box-shadow: 0 0 50px rgba(244,63,94,0.25); }
    .alert-active .status-pill { border-color: var(--danger); background: rgba(244,63,94,0.1); color: var(--danger); }
    .alert-active .indicator-dot { background: var(--danger); box-shadow: 0 0 12px var(--danger); }
    .alert-active .dist-val { color: var(--danger); }
    .logs { background: var(--card); border-radius: 28px; padding: 24px; backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.05); }
    .log-header { font-size: 12px; font-weight: 700; color: var(--sub); display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px; }
    .log-row { display: grid; grid-template-columns: 1fr 1fr 1fr; padding: 14px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 13px; font-weight: 500; }
    .log-row:last-child { border: none; }
    .log-time { color: var(--sub); font-family: monospace; }
  </style>
</head>
<body id="root">
  <div class="radar-bg"><div class="pulse" style="animation-delay: 0s"></div><div class="pulse" style="animation-delay: 1.5s"></div></div>
  <div class="alert-banner" id="alert-banner">⚠️ CAUTION: OBSTRUCTION DETECTED — REDUCE SPEED ⚠️</div>
  <div class="hud">
    <div class="panel">
      <h1>Tactical Road Scan</h1>
      <div class="rssi-ring"><div><span class="rssi-val" id="rssi">-</span><span class="rssi-unit">SIGNAL (dBm)</span></div></div>
      <div>
        <div class="dist-label">Proximity Confidence</div>
        <div class="dist-val" id="dist">---</div>
      </div>
      <div class="status-pill" id="status"><div class="indicator-dot"></div><span id="status-text">SYSTEM STANDBY</span></div>
    </div>
    <div class="logs">
      <div class="log-header"><span>Incident Registry</span><button onclick="clearLogs()" style="color:var(--danger); background:transparent; border:none; padding:4px; font-size:10px; font-weight:700; cursor:pointer; opacity:0.6">WIPE DATA</button></div>
      <div id="log-list"></div>
    </div>
  </div>
  <script>
    let lastId = 0;
    function loadLogs() {
      const logs = JSON.parse(localStorage.getItem('roadAlerts') || '[]');
      document.getElementById('log-list').innerHTML = logs.reverse().slice(0, 5).map(l => `
        <div class="log-row">
          <span class="log-time">${new Date(l.time).toLocaleTimeString()}</span>
          <span style="color:var(--danger); text-align:center">DANGER</span>
          <span style="font-family:monospace; text-align:right">${l.rssi} dBm</span>
        </div>`).join('') || '<div style="color:var(--sub); font-size:12px; text-align:center; padding:10px">No logs in buffer.</div>';
    }
    function updateHUD(data) {
      document.getElementById('rssi').textContent = data.rssi || '-';
      document.getElementById('status-text').textContent = data.alerting ? 'DANGER DETECTED' : 'SYSTEM SCANNING';
      document.getElementById('alert-banner').style.display = data.alerting ? 'block' : 'none';
      document.body.classList.toggle('alert-active', data.alerting);
      if(data.rssi < 0) {
        let dist = Math.pow(10, ((-20 - data.rssi) / 20));
        document.getElementById('dist').textContent = dist < 25 ? 'IMMEDIATE AREA' : `${Math.round(dist)}m ESTIMATED`;
      }
      if(data.id > lastId && lastId !== 0) {
        const logs = JSON.parse(localStorage.getItem('roadAlerts') || '[]');
        logs.push({ time: Date.now(), rssi: data.rssi });
        localStorage.setItem('roadAlerts', JSON.stringify(logs));
        loadLogs();
      }
      lastId = data.id;
    }
    async function sync() { try { const res = await fetch('/api/status'); updateHUD(await res.json()); } catch(e) {} }
    function clearLogs() { if(confirm('Wipe history?')) { localStorage.removeItem('roadAlerts'); loadLogs(); } }
    setInterval(sync, 1000);
    loadLogs();
  </script>
</body>
</html>
)=====";

#endif

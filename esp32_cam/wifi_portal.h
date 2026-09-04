#ifndef WIFI_PORTAL_H
#define WIFI_PORTAL_H

#include <Arduino.h>

const char WIFI_PORTAL_HTML_HEAD[] PROGMEM = R"=====(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>ESP32-CAM Wi-Fi Setup</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 28px 24px;
      max-width: 420px;
      width: 100%;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    }
    .header {
      text-align: center;
      margin-bottom: 24px;
    }
    .icon {
      font-size: 2.8rem;
      margin-bottom: 10px;
    }
    h1 {
      font-size: 1.35rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }
    p {
      font-size: 0.85rem;
      color: var(--muted);
      line-height: 1.4;
    }
    .form-group {
      margin-bottom: 18px;
    }
    label {
      display: block;
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      margin-bottom: 6px;
    }
    select, input[type="text"], input[type="password"] {
      width: 100%;
      background: #0b1120;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 12px 14px;
      border-radius: 10px;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.15s;
    }
    select:focus, input:focus {
      border-color: var(--primary);
    }
    .toggle-pass {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.8rem;
      color: var(--muted);
      margin-top: 6px;
      cursor: pointer;
    }
    .btn {
      width: 100%;
      background: var(--primary);
      color: white;
      border: none;
      padding: 14px;
      border-radius: 12px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
      margin-top: 8px;
    }
    .btn:hover {
      background: var(--primary-hover);
    }
    .btn:active {
      transform: scale(0.98);
    }
    .badge {
      display: inline-block;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      padding: 2px 8px;
      border-radius: 6px;
      background: rgba(59, 130, 246, 0.15);
      color: #93c5fd;
      border: 1px solid rgba(59, 130, 246, 0.3);
      margin-top: 8px;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="icon">📹</div>
      <h1>ESP32-CAM Wi-Fi Setup</h1>
      <p>Select your Wi-Fi hotspot or in-vehicle router to connect the optical detection station.</p>
      <div class="badge">AP IP: 192.168.4.1</div>
    </div>

    <form action="/save" method="POST">
      <div class="form-group">
        <label for="ssid">Available Hotspots</label>
        <select id="ssid" name="ssid" onchange="onSsidChange(this)">
)=====";

const char WIFI_PORTAL_HTML_FOOT[] PROGMEM = R"=====(
        </select>
      </div>

      <div class="form-group" id="manualGroup" style="display: none;">
        <label for="manual_ssid">Custom / Hidden SSID</label>
        <input type="text" id="manual_ssid" name="manual_ssid" placeholder="Enter network name">
      </div>

      <div class="form-group">
        <label for="password">Hotspot Password</label>
        <input type="password" id="password" name="password" placeholder="Enter Wi-Fi password">
        <label class="toggle-pass">
          <input type="checkbox" onclick="togglePassword()"> Show password
        </label>
      </div>

      <button type="submit" class="btn">⚡ Save & Connect Hotspot</button>
    </form>
  </div>

  <script>
    function togglePassword() {
      const p = document.getElementById("password");
      p.type = (p.type === "password") ? "text" : "password";
    }
    function onSsidChange(sel) {
      const manual = document.getElementById("manualGroup");
      if (sel.value === "__MANUAL__") {
        manual.style.display = "block";
      } else {
        manual.style.display = "none";
      }
    }
  </script>
</body>
</html>
)=====";

const char WIFI_SAVED_PAGE[] PROGMEM = R"=====(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Credentials Saved</title>
  <style>
    body {
      background: #0f172a;
      color: #f8fafc;
      font-family: -apple-system, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      text-align: center;
      padding: 20px;
    }
    .box {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 20px;
      padding: 32px;
      max-width: 400px;
    }
    h2 { color: #10b981; margin-bottom: 12px; }
    p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
    .loader {
      width: 40px;
      height: 40px;
      border: 3px solid #334155;
      border-top-color: #3b82f6;
      border-radius: 50%;
      margin: 20px auto;
      animation: spin 1s infinite linear;
    }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="box">
    <div style="font-size: 3rem; margin-bottom: 12px;">✅</div>
    <h2>Credentials Saved!</h2>
    <p>Connecting to <strong>%SSID%</strong>...</p>
    <div class="loader"></div>
    <p style="font-size: 0.8rem; color: #64748b;">The ESP32-CAM is rebooting into Station mode. Once connected, open its assigned IP on port 81.</p>
  </div>
</body>
</html>
)=====";

#endif

"""
Parts Washer v2.0 - Async Web Server
REST API and web interface for remote control
"""

import uasyncio as asyncio
import json
import gc


class WebServer:
    """Lightweight async web server with REST API."""

    def __init__(self, washer, wifi, settings, port=80):
        self.washer = washer
        self.wifi = wifi
        self.settings = settings
        self.port = port
        self.server = None
        self.running = False

    async def start(self):
        """Start the web server."""
        self.server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self.port
        )
        self.running = True
        print(f"Web server started on port {self.port}")

    async def stop(self):
        """Stop the web server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.running = False

    async def _handle_client(self, reader, writer):
        """Handle incoming HTTP request."""
        gc.collect()
        try:
            # Read request line
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=5
            )
            if not request_line:
                return

            request_line = request_line.decode().strip()
            parts = request_line.split(" ")
            if len(parts) < 2:
                return

            method = parts[0]
            path = parts[1]

            # Read headers
            content_length = 0
            while True:
                line = await reader.readline()
                if line == b"\r\n" or line == b"":
                    break
                if line.lower().startswith(b"content-length:"):
                    content_length = int(line.decode().split(":")[1].strip())

            # Read body if present
            body = None
            if content_length > 0:
                body = await reader.read(content_length)
                body = body.decode()

            # Route request
            response = await self._route(method, path, body)

            # Send response
            writer.write(response.encode() if isinstance(response, str) else response)
            await writer.drain()

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"Request error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _route(self, method, path, body):
        """Route request to appropriate handler."""
        # Remove query string for routing
        path_only = path.split("?")[0]

        # API endpoints
        if path_only == "/api/status":
            return self._json_response(self._get_status())

        elif path_only == "/api/settings" and method == "GET":
            return self._json_response(self.settings.get_all())

        elif path_only == "/api/settings" and method == "POST":
            return self._handle_settings(body)

        elif path_only == "/api/control" and method == "POST":
            return await self._handle_control(body)

        elif path_only == "/api/wifi/scan":
            networks = self.wifi.scan_networks()
            return self._json_response({"networks": networks})

        elif path_only == "/api/wifi/connect" and method == "POST":
            return self._handle_wifi_connect(body)

        elif path_only == "/api/wifi/status":
            return self._json_response(self.wifi.get_status())

        elif path_only == "/api/wifi/static" and method == "POST":
            return self._handle_static_ip(body)

        elif path_only == "/" or path_only == "/index.html":
            return self._serve_html()

        elif path_only == "/style.css":
            return self._serve_css()

        else:
            return self._response(404, "Not Found")

    def _get_status(self):
        """Get current washer status."""
        return {
            "mode": self.washer.current_mode,
            "mode_name": self.washer.get_mode_name(),
            "station": self.washer.current_station,
            "station_name": self.washer.get_station_name(),
            "running": self.washer.is_running,
            "homed": self.washer.is_homed,
            "heater": not self.washer.heater.value(),
            "z_position": self.washer.z_motor.get_position_mm() if hasattr(self.washer, 'z_motor') else 0,
            "limits": {
                "z_top": not self.washer.z_top.value(),
                "z_bottom": not self.washer.z_bottom.value(),
                "rot_home": not self.washer.rot_home.value()
            },
            "wifi": self.wifi.get_status()
        }

    def _handle_settings(self, body):
        """Handle settings update."""
        try:
            data = json.loads(body)
            self.settings.set_multiple(data)
            self.settings.save()
            return self._json_response({"success": True})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    async def _handle_control(self, body):
        """Handle control commands."""
        try:
            data = json.loads(body)
            action = data.get("action")

            if action == "start":
                self.washer.start_cycle()
                return self._json_response({"success": True, "action": "started"})

            elif action == "stop":
                self.washer.stop_cycle()
                return self._json_response({"success": True, "action": "stopped"})

            elif action == "home":
                asyncio.create_task(self.washer.home_all())
                return self._json_response({"success": True, "action": "homing"})

            elif action == "mode":
                mode = data.get("mode", 0)
                self.washer.set_mode(mode)
                return self._json_response({"success": True, "mode": mode})

            elif action == "station":
                station = data.get("station", 0)
                self.washer.move_to_station(station)
                return self._json_response({"success": True, "station": station})

            elif action == "z_up":
                self.washer.jog_z(10)
                return self._json_response({"success": True, "action": "z_up"})

            elif action == "z_down":
                self.washer.jog_z(-10)
                return self._json_response({"success": True, "action": "z_down"})

            elif action == "heater":
                state = data.get("state", False)
                self.washer.set_heater(state)
                return self._json_response({"success": True, "heater": state})

            elif action == "beep":
                self.washer.beep(1)
                return self._json_response({"success": True, "action": "beep"})

            else:
                return self._json_response({"success": False, "error": "Unknown action"}, 400)

        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _handle_wifi_connect(self, body):
        """Handle WiFi connection request."""
        try:
            data = json.loads(body)
            ssid = data.get("ssid")
            password = data.get("password", "")

            if self.wifi.connect(ssid, password, timeout=20):
                return self._json_response({
                    "success": True,
                    "ip": self.wifi.ip_address
                })
            else:
                return self._json_response({
                    "success": False,
                    "error": "Connection failed"
                }, 400)
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _handle_static_ip(self, body):
        """Handle static IP configuration."""
        try:
            data = json.loads(body)
            static_ip = data.get("static_ip")

            if static_ip:
                subnet = data.get("subnet", "255.255.255.0")
                gateway = data.get("gateway")
                dns = data.get("dns", "8.8.8.8")
                self.wifi.set_static_ip(static_ip, subnet, gateway, dns)
                return self._json_response({
                    "success": True,
                    "message": f"Static IP {static_ip} configured. Reboot to apply."
                })
            else:
                self.wifi.clear_static_ip()
                return self._json_response({
                    "success": True,
                    "message": "Static IP cleared. Will use DHCP on next connect."
                })
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _json_response(self, data, status=200):
        """Create JSON HTTP response."""
        body = json.dumps(data)
        return (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )

    def _response(self, status, message):
        """Create simple HTTP response."""
        return (
            f"HTTP/1.1 {status} {message}\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{message}"
        )

    def _serve_html(self):
        """Serve the main HTML page."""
        html = self._get_html()
        return (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/html\r\n"
            f"Content-Length: {len(html)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{html}"
        )

    def _serve_css(self):
        """Serve CSS stylesheet."""
        css = self._get_css()
        return (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/css\r\n"
            f"Content-Length: {len(css)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{css}"
        )

    def _get_html(self):
        """Return embedded HTML."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parts Washer Control</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Parts Washer</h1>
            <div id="status-indicator" class="status-dot"></div>
        </header>

        <section class="status-panel">
            <div class="status-item">
                <label>Mode:</label>
                <span id="current-mode">--</span>
            </div>
            <div class="status-item">
                <label>Station:</label>
                <span id="current-station">--</span>
            </div>
            <div class="status-item">
                <label>Status:</label>
                <span id="running-status">--</span>
            </div>
            <div class="status-item">
                <label>Heater:</label>
                <span id="heater-status">--</span>
            </div>
        </section>

        <section class="control-panel">
            <h2>Controls</h2>
            <div class="button-grid">
                <button onclick="sendControl('start')" class="btn btn-green">START</button>
                <button onclick="sendControl('stop')" class="btn btn-red">STOP</button>
                <button onclick="sendControl('home')" class="btn btn-blue">HOME</button>
                <button onclick="toggleHeater()" id="heater-btn" class="btn">HEATER</button>
            </div>
        </section>

        <section class="mode-panel">
            <h2>Mode Select</h2>
            <div class="button-grid">
                <button onclick="setMode(0)" class="btn btn-small">JITTER</button>
                <button onclick="setMode(1)" class="btn btn-small">CLEAN</button>
                <button onclick="setMode(2)" class="btn btn-small">SPIN</button>
                <button onclick="setMode(3)" class="btn btn-small">HEAT</button>
                <button onclick="setMode(4)" class="btn btn-small btn-primary">AUTO</button>
            </div>
        </section>

        <section class="station-panel">
            <h2>Station Select</h2>
            <div class="button-grid">
                <button onclick="setStation(0)" class="btn btn-small">WASH</button>
                <button onclick="setStation(1)" class="btn btn-small">RINSE 1</button>
                <button onclick="setStation(2)" class="btn btn-small">RINSE 2</button>
                <button onclick="setStation(3)" class="btn btn-small">HEATER</button>
            </div>
        </section>

        <section class="jog-panel">
            <h2>Z-Axis Jog</h2>
            <div class="jog-buttons">
                <button onclick="sendControl('z_up')" class="btn btn-jog">UP</button>
                <button onclick="sendControl('z_down')" class="btn btn-jog">DOWN</button>
            </div>
        </section>

        <section class="settings-panel">
            <h2>Settings</h2>
            <details>
                <summary>Timing Settings</summary>
                <div class="settings-grid">
                    <label>Wash Duration (s):</label>
                    <input type="number" id="wash_duration" min="0" max="600">
                    <label>Rinse 1 Duration (s):</label>
                    <input type="number" id="rinse1_duration" min="0" max="600">
                    <label>Rinse 2 Duration (s):</label>
                    <input type="number" id="rinse2_duration" min="0" max="600">
                    <label>Spin Duration (s):</label>
                    <input type="number" id="spin_duration" min="0" max="600">
                    <label>Heat Duration (s):</label>
                    <input type="number" id="heat_duration" min="0" max="3600">
                </div>
            </details>
            <details>
                <summary>Motor Settings</summary>
                <div class="settings-grid">
                    <label>Clean RPM:</label>
                    <input type="number" id="clean_rpm" min="100" max="1200">
                    <label>Spin RPM:</label>
                    <input type="number" id="spin_rpm" min="100" max="1200">
                    <label>Heat RPM:</label>
                    <input type="number" id="heat_rpm" min="50" max="500">
                    <label>Jitter Osc/sec:</label>
                    <input type="number" id="jitter_osc" min="1" max="20" step="0.5">
                </div>
            </details>
            <button onclick="saveSettings()" class="btn btn-blue">Save Settings</button>
        </section>

        <section class="wifi-panel">
            <h2>WiFi</h2>
            <div id="wifi-status"></div>
            <details>
                <summary>Configure WiFi</summary>
                <div class="settings-grid">
                    <label>SSID:</label>
                    <select id="wifi-ssid"></select>
                    <button onclick="scanWifi()" class="btn btn-small">Scan</button>
                    <label>Password:</label>
                    <input type="password" id="wifi-password">
                </div>
                <button onclick="connectWifi()" class="btn btn-blue">Connect</button>
            </details>
            <details>
                <summary>Static IP Configuration</summary>
                <div class="settings-grid">
                    <label>Static IP:</label>
                    <input type="text" id="static-ip" placeholder="e.g. 192.168.71.154">
                    <label>Subnet:</label>
                    <input type="text" id="static-subnet" value="255.255.255.0">
                    <label>Gateway:</label>
                    <input type="text" id="static-gateway" placeholder="e.g. 192.168.71.1">
                    <label>DNS:</label>
                    <input type="text" id="static-dns" value="8.8.8.8">
                </div>
                <button onclick="setStaticIP()" class="btn btn-blue">Set Static IP</button>
                <button onclick="clearStaticIP()" class="btn btn-small">Use DHCP</button>
            </details>
        </section>
    </div>

    <script>
        let heaterState = false;

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                updateUI(data);
            } catch (e) {
                document.getElementById('status-indicator').className = 'status-dot offline';
            }
        }

        function updateUI(data) {
            document.getElementById('status-indicator').className = 'status-dot online';
            document.getElementById('current-mode').textContent = data.mode_name;
            document.getElementById('current-station').textContent = data.station_name;
            document.getElementById('running-status').textContent = data.running ? 'RUNNING' : 'IDLE';
            document.getElementById('heater-status').textContent = data.heater ? 'ON' : 'OFF';
            heaterState = data.heater;
            document.getElementById('heater-btn').className = data.heater ? 'btn btn-orange' : 'btn';
        }

        async function sendControl(action, extra = {}) {
            try {
                await fetch('/api/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action, ...extra})
                });
                setTimeout(fetchStatus, 200);
            } catch (e) {
                alert('Control failed: ' + e);
            }
        }

        function setMode(mode) { sendControl('mode', {mode}); }
        function setStation(station) { sendControl('station', {station}); }
        function toggleHeater() { sendControl('heater', {state: !heaterState}); }

        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                for (const [key, value] of Object.entries(data)) {
                    const el = document.getElementById(key);
                    if (el) el.value = value;
                }
            } catch (e) {}
        }

        async function saveSettings() {
            const settings = {};
            const inputs = document.querySelectorAll('.settings-grid input');
            inputs.forEach(input => {
                if (input.id) settings[input.id] = input.value;
            });
            try {
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings)
                });
                alert('Settings saved!');
            } catch (e) {
                alert('Save failed: ' + e);
            }
        }

        async function scanWifi() {
            const select = document.getElementById('wifi-ssid');
            select.innerHTML = '<option>Scanning...</option>';
            try {
                const res = await fetch('/api/wifi/scan');
                const data = await res.json();
                select.innerHTML = data.networks.map(n =>
                    `<option value="${n.ssid}">${n.ssid} (${n.rssi}dBm)</option>`
                ).join('');
            } catch (e) {
                select.innerHTML = '<option>Scan failed</option>';
            }
        }

        async function connectWifi() {
            const ssid = document.getElementById('wifi-ssid').value;
            const password = document.getElementById('wifi-password').value;
            try {
                const res = await fetch('/api/wifi/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ssid, password})
                });
                const data = await res.json();
                if (data.success) {
                    alert('Connected! New IP: ' + data.ip);
                } else {
                    alert('Connection failed: ' + data.error);
                }
            } catch (e) {
                alert('Connection failed: ' + e);
            }
        }

        async function setStaticIP() {
            const static_ip = document.getElementById('static-ip').value;
            const subnet = document.getElementById('static-subnet').value;
            const gateway = document.getElementById('static-gateway').value;
            const dns = document.getElementById('static-dns').value;
            if (!static_ip) {
                alert('Please enter a static IP address');
                return;
            }
            try {
                const res = await fetch('/api/wifi/static', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({static_ip, subnet, gateway, dns})
                });
                const data = await res.json();
                alert(data.message || (data.success ? 'Static IP set!' : 'Failed'));
            } catch (e) {
                alert('Failed: ' + e);
            }
        }

        async function clearStaticIP() {
            try {
                const res = await fetch('/api/wifi/static', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                });
                const data = await res.json();
                alert(data.message || 'DHCP mode set');
                document.getElementById('static-ip').value = '';
            } catch (e) {
                alert('Failed: ' + e);
            }
        }

        async function loadStaticIPConfig() {
            try {
                const res = await fetch('/api/wifi/status');
                const data = await res.json();
                if (data.static_ip) {
                    document.getElementById('static-ip').value = data.static_ip;
                    document.getElementById('static-subnet').value = data.subnet || '255.255.255.0';
                    document.getElementById('static-gateway').value = data.gateway || '';
                    document.getElementById('static-dns').value = data.dns || '8.8.8.8';
                }
            } catch (e) {}
        }

        // Initialize
        fetchStatus();
        loadSettings();
        loadStaticIPConfig();
        setInterval(fetchStatus, 2000);
    </script>
</body>
</html>'''

    def _get_css(self):
        """Return embedded CSS."""
        return '''* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
.container { max-width: 600px; margin: 0 auto; padding: 15px; }
header { display: flex; justify-content: space-between; align-items: center; padding: 15px 0; border-bottom: 1px solid #333; }
h1 { font-size: 1.5em; }
h2 { font-size: 1.1em; margin-bottom: 10px; color: #888; }
.status-dot { width: 12px; height: 12px; border-radius: 50%; background: #666; }
.status-dot.online { background: #4caf50; box-shadow: 0 0 10px #4caf50; }
.status-dot.offline { background: #f44336; }
section { background: #16213e; border-radius: 10px; padding: 15px; margin: 15px 0; }
.status-panel { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.status-item { display: flex; justify-content: space-between; padding: 8px; background: #1a1a2e; border-radius: 5px; }
.status-item label { color: #888; }
.button-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.btn { padding: 15px; border: none; border-radius: 8px; font-size: 1em; font-weight: bold; cursor: pointer; background: #333; color: #fff; transition: all 0.2s; }
.btn:active { transform: scale(0.95); }
.btn-green { background: #4caf50; }
.btn-red { background: #f44336; }
.btn-blue { background: #2196f3; }
.btn-orange { background: #ff9800; }
.btn-primary { background: #9c27b0; }
.btn-small { padding: 10px; font-size: 0.9em; }
.btn-jog { padding: 20px 40px; }
.jog-buttons { display: flex; justify-content: center; gap: 20px; }
details { margin: 10px 0; }
summary { cursor: pointer; padding: 10px; background: #1a1a2e; border-radius: 5px; }
.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 15px 0; align-items: center; }
.settings-grid label { color: #888; }
.settings-grid input, .settings-grid select { padding: 8px; border: 1px solid #333; border-radius: 5px; background: #1a1a2e; color: #fff; }
#wifi-status { padding: 10px; background: #1a1a2e; border-radius: 5px; margin-bottom: 10px; }'''

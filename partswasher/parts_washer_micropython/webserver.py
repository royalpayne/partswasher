"""
Parts Washer v2.0 - Async Web Server
REST API and web interface for remote control
"""

import uasyncio as asyncio
import json
import gc
import os
import time
import machine


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

            # Send response - handle tuples (header, body) for large responses
            if isinstance(response, tuple):
                header, body_content = response
                writer.write(header.encode())
                await writer.drain()
                # Write body in chunks to avoid large allocations
                chunk_size = 1024
                for i in range(0, len(body_content), chunk_size):
                    writer.write(body_content[i:i+chunk_size].encode())
                    await writer.drain()
            else:
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

        elif path_only == "/api/ota/files":
            return self._handle_ota_files()

        elif path_only == "/api/ota/upload" and method == "POST":
            return self._handle_ota_upload(body)

        elif path_only == "/api/ota/reboot" and method == "POST":
            return await self._handle_ota_reboot()

        elif path_only == "/" or path_only == "/index.html":
            return self._serve_html()

        elif path_only == "/style.css":
            return self._serve_css()

        else:
            return self._response(404, "Not Found")

    def _get_status(self):
        """Get current washer status."""
        elapsed = 0
        duration = 0
        if self.washer.is_running and self.washer.mode_start_time:
            elapsed = time.ticks_ms() - self.washer.mode_start_time
            duration = self.washer.get_mode_duration_ms()
        return {
            "mode": self.washer.current_mode,
            "mode_name": self.washer.get_mode_name(),
            "station": self.washer.current_station,
            "station_name": self.washer.get_station_name(),
            "running": self.washer.is_running,
            "homed": self.washer.is_homed,
            "heater": bool(self.washer.heater.value()),
            "z_pos": self.washer.z_motor.get_position_mm() if hasattr(self.washer, 'z_motor') else 0,
            "z_target": self.washer.z_motor.get_target_mm() if hasattr(self.washer, 'z_motor') else 0,
            "z_top": bool(self.washer.z_top.value()),
            "z_bottom": bool(self.washer.z_bottom.value()),
            "rot_home": bool(self.washer.rot_home.value()),
            "elapsed_ms": elapsed,
            "duration_ms": duration,
            "auto_step": self.washer.auto_step,
            "auto_total": 21,
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

            elif action == "z_move_to":
                pos = float(data.get("position", 0))
                self.washer.move_z_to(pos)
                return self._json_response({"success": True, "action": "z_move_to", "position": pos})

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

    # ============== OTA UPDATE METHODS ==============

    def _handle_ota_files(self):
        """List files on flash with sizes."""
        try:
            files = []
            for name in os.listdir("/"):
                stat = os.stat("/" + name)
                files.append({"name": name, "size": stat[6]})
            files.sort(key=lambda f: f["name"])
            return self._json_response({"files": files})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _handle_ota_upload(self, body):
        """Handle file upload for OTA update."""
        try:
            data = json.loads(body)
            filename = data.get("filename", "")
            content = data.get("content", "")

            # Security: reject path traversal and subdirectories
            if not filename or ".." in filename or "/" in filename:
                return self._json_response(
                    {"success": False, "error": "Invalid filename"}, 400
                )

            # Protect config files from accidental overwrite
            protected = ("settings.json", "wifi_config.json")
            if filename in protected:
                return self._json_response(
                    {"success": False, "error": f"{filename} is protected"}, 400
                )

            # Write file to flash
            with open("/" + filename, "w") as f:
                written = f.write(content)

            print(f"OTA: wrote {filename} ({written} bytes)")
            return self._json_response({
                "success": True,
                "filename": filename,
                "bytes": written
            })
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    async def _handle_ota_reboot(self):
        """Handle reboot request - stops hardware then resets."""
        self.washer.stop_all()
        print("OTA: rebooting...")
        # Schedule reset after response is sent
        async def _delayed_reset():
            await asyncio.sleep_ms(500)
            machine.soft_reset()
        asyncio.create_task(_delayed_reset())
        return self._json_response({"success": True, "message": "Rebooting..."})

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
        """Serve the main HTML page (streamed as tuple)."""
        gc.collect()
        html = self._get_html()
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/html\r\n"
            f"Content-Length: {len(html)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        return (header, html)

    def _serve_css(self):
        """Serve CSS stylesheet (streamed as tuple)."""
        gc.collect()
        css = self._get_css()
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/css\r\n"
            f"Content-Length: {len(css)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        return (header, css)

    def _get_html(self):
        """Return embedded HTML."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parts Washer Control</title>
    <style>''' + self._get_css() + '''</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Parts Washer</h1>
            <div class="hdr-right">
                <span id="conn-text" class="conn-text">--</span>
                <div id="status-indicator" class="status-dot"></div>
            </div>
        </header>

        <!-- Dashboard -->
        <section class="dashboard">
            <div class="dash-top">
                <div class="dash-mode">
                    <div class="dash-label">MODE</div>
                    <div id="dash-mode" class="dash-val">--</div>
                </div>
                <div class="dash-status">
                    <div id="dash-state" class="state-badge idle">IDLE</div>
                </div>
            </div>

            <canvas id="viz" width="300" height="260" style="display:block;margin:4px auto 8px"></canvas>

            <!-- Station Carousel -->
            <div class="carousel">
                <div id="stn-c-0" class="carousel-item active"><div class="carousel-dot"></div><span>WASH</span></div>
                <div class="carousel-arrow">&rarr;</div>
                <div id="stn-c-1" class="carousel-item"><div class="carousel-dot"></div><span>RINSE 1</span></div>
                <div class="carousel-arrow">&rarr;</div>
                <div id="stn-c-2" class="carousel-item"><div class="carousel-dot"></div><span>RINSE 2</span></div>
                <div class="carousel-arrow">&rarr;</div>
                <div id="stn-c-3" class="carousel-item"><div class="carousel-dot"></div><span>HEATER</span></div>
            </div>

            <!-- Timer + Progress -->
            <div class="dash-timer-row">
                <div class="timer-block">
                    <span id="dash-timer" class="timer-val">00:00</span>
                    <span id="dash-duration" class="timer-total"></span>
                </div>
                <div class="progress-wrap">
                    <div id="dash-progress" class="progress-bar" style="width:0%"></div>
                </div>
            </div>

            <!-- Info Row -->
            <div class="dash-info">
                <div class="info-item"><span class="info-lbl">Z</span><span id="dash-z" class="info-val">0.0 mm</span></div>
                <div class="info-item"><span class="info-lbl">HEATER</span><span id="dash-heater" class="info-val off">OFF</span></div>
                <div id="dash-auto-wrap" class="info-item" style="display:none"><span class="info-lbl">AUTO</span><span id="dash-auto" class="info-val">0/21</span></div>
                <div class="info-item"><span class="info-lbl">HOME</span><span id="dash-homed" class="info-val off">NO</span></div>
            </div>
        </section>

        <!-- Controls -->
        <section>
            <h2>Controls</h2>
            <div class="button-grid">
                <button onclick="sendControl('start')" class="btn btn-green">START</button>
                <button onclick="sendControl('stop')" class="btn btn-red">STOP</button>
                <button onclick="sendControl('home')" class="btn btn-blue">HOME</button>
                <button onclick="toggleHeater()" id="heater-btn" class="btn">HEATER</button>
            </div>
        </section>

        <!-- Mode Select -->
        <section>
            <h2>Mode Select</h2>
            <div class="button-grid mode-grid">
                <button id="mode-0" onclick="setMode(0)" class="btn btn-small">JITTER</button>
                <button id="mode-1" onclick="setMode(1)" class="btn btn-small">CLEAN</button>
                <button id="mode-2" onclick="setMode(2)" class="btn btn-small">SPIN</button>
                <button id="mode-3" onclick="setMode(3)" class="btn btn-small">HEAT</button>
                <button id="mode-4" onclick="setMode(4)" class="btn btn-small">AUTO</button>
            </div>
        </section>

        <!-- Station Select -->
        <section>
            <h2>Station Select</h2>
            <div class="button-grid">
                <button id="stn-0" onclick="setStation(0)" class="btn btn-small">WASH</button>
                <button id="stn-1" onclick="setStation(1)" class="btn btn-small">RINSE 1</button>
                <button id="stn-2" onclick="setStation(2)" class="btn btn-small">RINSE 2</button>
                <button id="stn-3" onclick="setStation(3)" class="btn btn-small">HEATER</button>
            </div>
        </section>

        <!-- Z-Axis -->
        <section>
            <h2>Z-Axis</h2>
            <div class="z-slider-container">
                <div class="z-slider-labels">
                    <span class="z-end-label">HOME</span>
                    <span id="jog-z" class="jog-pos">0.0 cm</span>
                    <span class="z-end-label">WASH</span>
                </div>
                <input type="range" id="z-slider" class="z-slider" min="0" max="20.6" step="0.1" value="0">
                <div class="z-ticks">
                    <span>0</span><span>5</span><span>10</span><span>15</span><span>20.6</span>
                </div>
            </div>
        </section>

        <!-- Settings -->
        <section>
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
            <details>
                <summary>Z Positions (mm)</summary>
                <div class="settings-grid">
                    <label>Home (Top):</label>
                    <div><input type="number" id="z_pos_home" step="0.1" min="0" max="155" style="width:80px"> <button onclick="setZCurrent('z_pos_home')" class="btn btn-small">Set Current</button></div>
                    <label>Spin Dry (Mid):</label>
                    <div><input type="number" id="z_pos_spin" step="0.1" min="0" max="155" style="width:80px"> <button onclick="setZCurrent('z_pos_spin')" class="btn btn-small">Set Current</button></div>
                    <label>Wash (Bottom):</label>
                    <div><input type="number" id="z_pos_wash" step="0.1" min="0" max="155" style="width:80px"> <button onclick="setZCurrent('z_pos_wash')" class="btn btn-small">Set Current</button></div>
                </div>
            </details>
            <button onclick="saveSettings()" class="btn btn-blue">Save Settings</button>
        </section>

        <!-- WiFi -->
        <section>
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
                <summary>Static IP</summary>
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

        <!-- OTA -->
        <section>
            <h2>OTA Update</h2>
            <div style="margin-bottom:10px">
                <input type="file" id="ota-files" multiple accept=".py" style="color:#888">
                <button onclick="uploadFiles()" class="btn btn-blue" style="margin-top:10px">Upload Files</button>
            </div>
            <div id="ota-status" style="padding:10px;background:#1a1a2e;border-radius:5px;margin:10px 0;font-family:monospace;font-size:0.85em;white-space:pre-wrap"></div>
            <details>
                <summary>Files on Device</summary>
                <div id="ota-file-list" style="padding:10px"></div>
                <button onclick="loadDeviceFiles()" class="btn btn-small">Refresh</button>
            </details>
            <button onclick="rebootDevice()" class="btn btn-red" style="margin-top:10px">Reboot Device</button>
        </section>
    </div>

    <script>
        let heaterState = false;
        var zSliderActive = false;
        var zDebounce = null;

        (function() {
            var sl = document.getElementById('z-slider');
            sl.addEventListener('input', function() {
                zSliderActive = true;
                document.getElementById('jog-z').textContent = parseFloat(this.value).toFixed(1) + ' cm';
                clearTimeout(zDebounce);
                zDebounce = setTimeout(function() {
                    var cm = parseFloat(sl.value);
                    sendControl('z_move_to', {position: cm * 10});
                }, 200);
            });
            sl.addEventListener('change', function() {
                var cm = parseFloat(this.value);
                sendControl('z_move_to', {position: cm * 10});
                setTimeout(function() { zSliderActive = false; }, 500);
            });
        })();

        var vizData={};
        (function vL(){drawViz(vizData);requestAnimationFrame(vL);})();

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                updateUI(data);
            } catch (e) {
                document.getElementById('status-indicator').className = 'status-dot offline';
                document.getElementById('conn-text').textContent = 'OFFLINE';
            }
        }

        function fmtTime(ms) {
            var s = Math.floor(ms / 1000);
            var m = Math.floor(s / 60);
            s = s % 60;
            return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
        }

        function updateUI(data) {
            // Connection
            document.getElementById('status-indicator').className = 'status-dot online';
            document.getElementById('conn-text').textContent = 'ONLINE';

            // Dashboard mode
            document.getElementById('dash-mode').textContent = data.mode_name || '--';
            document.getElementById('dash-mode').className = data.running ? 'dash-val running' : 'dash-val';

            // State badge
            var sb = document.getElementById('dash-state');
            if (!data.homed) { sb.textContent = 'NOT HOMED'; sb.className = 'state-badge warn'; }
            else if (data.running) { sb.textContent = 'RUNNING'; sb.className = 'state-badge running'; }
            else { sb.textContent = 'READY'; sb.className = 'state-badge ready'; }

            // Station carousel
            for (var i = 0; i < 4; i++) {
                var el = document.getElementById('stn-c-' + i);
                if (el) el.className = i === data.station ? 'carousel-item active' : 'carousel-item';
            }

            // Timer + progress
            var timer = document.getElementById('dash-timer');
            var dur = document.getElementById('dash-duration');
            var prog = document.getElementById('dash-progress');
            if (data.running && data.duration_ms > 0) {
                timer.textContent = fmtTime(data.elapsed_ms);
                dur.textContent = '/ ' + fmtTime(data.duration_ms);
                var pct = Math.min(100, (data.elapsed_ms / data.duration_ms) * 100);
                prog.style.width = pct + '%';
            } else if (data.running) {
                timer.textContent = fmtTime(data.elapsed_ms);
                dur.textContent = '';
                prog.style.width = '0%';
            } else {
                timer.textContent = '00:00';
                dur.textContent = '';
                prog.style.width = '0%';
            }

            // Info row
            var zp_mm = parseFloat(data.z_pos || 0);
            var zp_cm = (zp_mm / 10).toFixed(1);
            var zt_mm = parseFloat(data.z_target || 0);
            var zt_cm = (zt_mm / 10).toFixed(1);
            document.getElementById('dash-z').textContent = zp_cm + ' cm';
            if (!zSliderActive) {
                document.getElementById('jog-z').textContent = zp_cm + ' cm';
                document.getElementById('z-slider').value = zt_cm;
            }

            var hEl = document.getElementById('dash-heater');
            hEl.textContent = data.heater ? 'ON' : 'OFF';
            hEl.className = data.heater ? 'info-val on' : 'info-val off';

            var hmEl = document.getElementById('dash-homed');
            hmEl.textContent = data.homed ? 'YES' : 'NO';
            hmEl.className = data.homed ? 'info-val on' : 'info-val off';

            // Auto cycle
            var aw = document.getElementById('dash-auto-wrap');
            if (data.mode === 4 && data.running) {
                aw.style.display = '';
                document.getElementById('dash-auto').textContent = data.auto_step + '/' + data.auto_total;
            } else {
                aw.style.display = 'none';
            }

            // Mode buttons
            var mode = typeof data.mode === 'string' ? parseInt(data.mode) : data.mode;
            for (var m = 0; m < 5; m++) { var mb = document.getElementById('mode-' + m); if (mb) mb.className = m === mode ? 'btn btn-small btn-primary' : 'btn btn-small'; }

            // Station buttons
            var stn = typeof data.station === 'string' ? parseInt(data.station) : data.station;
            for (var s = 0; s < 4; s++) { var sb2 = document.getElementById('stn-' + s); if (sb2) sb2.className = s === stn ? 'btn btn-small btn-primary' : 'btn btn-small'; }

            // Heater button
            heaterState = data.heater;
            document.getElementById('heater-btn').className = data.heater ? 'btn btn-orange' : 'btn';

            vizData = data;
        }

        function drawViz(d){
            var c=document.getElementById("viz");if(!c)return;
            var g=c.getContext("2d"),W=c.width,H=c.height;
            g.clearRect(0,0,W,H);
            var sc=W/320,cx=W/2,cy=H*0.78,t=Date.now();
            function iso(x,y,z){return[cx+(x-y)*0.82*sc,cy-z*0.95*sc+(x+y)*0.47*sc];}
            function iE(ox,oy,z,r,f,st,lw){var p=iso(ox,oy,z),rx=r*1.16*sc,ry=r*0.66*sc;
                g.beginPath();g.ellipse(p[0],p[1],rx,ry,0,0,6.283);
                if(f){g.fillStyle=f;g.fill();}if(st){g.strokeStyle=st;g.lineWidth=lw||1;g.stroke();}}
            var zF=Math.min(1,(d.z_pos||0)/206),stn=d.station||0,run=d.running,heat=d.heater;
            var sn=["W","R1","R2","H"],R=52,jr=17;
            // Smooth carousel rotation (jars rotate to basket, NOT arm to jar)
            if(drawViz.cr===undefined)drawViz.cr=0;
            var tgt=stn*1.5708,df=tgt-drawViz.cr;
            while(df>3.14)df-=6.283;while(df<-3.14)df+=6.283;
            drawViz.cr+=df*0.12;
            // Jar positions: carousel rotates so active jar is at front-center
            var BA=0.7854; // basket angle = pi/4 (front-center in iso view)
            var J=[];
            for(var i=0;i<4;i++){
                var a=BA+i*1.5708-drawViz.cr;
                var jx=R*Math.cos(a),jy=R*Math.sin(a);
                J.push({i:i,x:jx,y:jy,sy:iso(jx,jy,45)[1],act:i===stn});
            }
            J.sort(function(a,b){return a.sy-b.sy;}); // back-to-front
            // Fixed basket position (arm always extends to same spot)
            var bkx=R*Math.cos(BA),bky=R*Math.sin(BA);
            var hz=168-zF*125,hp=iso(0,0,hz),bp=iso(bkx*0.82,bky*0.82,hz);
            var ctrSy=iso(0,0,45)[1];
            // --- Jar renderer ---
            function jar(j){
                var bt=iso(j.x,j.y,3),tp=iso(j.x,j.y,88);
                var w=jr*2.32*sc,hw=w/2,h=bt[1]-tp[1],ac=j.act,hi=j.i===3&&heat;
                // Body
                g.fillStyle=ac?"rgba(187,134,252,0.13)":(hi?"rgba(255,130,0,0.15)":"rgba(28,28,52,0.55)");
                g.fillRect(tp[0]-hw,tp[1],w,h);
                g.strokeStyle=ac?"#bb86fc":"#2a2a50";g.lineWidth=ac?2:1;
                g.strokeRect(tp[0]-hw,tp[1],w,h);
                // Top ellipse (jar opening)
                iE(j.x,j.y,88,jr,"rgba(18,18,38,0.8)",ac?"#bb86fc":"#2a2a50",ac?2:1);
                // Liquid with slosh
                if(j.i<3){var lz=30+(run&&ac?Math.sin(t/250)*4:0),lt=iso(j.x,j.y,lz);
                    g.fillStyle=j.i===0?"rgba(80,120,255,0.13)":"rgba(80,180,255,0.09)";
                    g.fillRect(lt[0]-hw+1,lt[1],w-2,bt[1]-lt[1]-1);
                    iE(j.x,j.y,lz,jr-1,j.i===0?"rgba(80,120,255,0.2)":"rgba(80,180,255,0.14)",null,0);}
                // Heater glow
                if(hi){var hc=iso(j.x,j.y,25),gr=g.createRadialGradient(hc[0],hc[1],2,hc[0],hc[1],hw*2);
                    gr.addColorStop(0,"rgba(255,100,0,"+(0.3+Math.sin(t/400)*0.15)+")");gr.addColorStop(1,"rgba(255,50,0,0)");
                    g.fillStyle=gr;g.beginPath();g.arc(hc[0],hc[1],hw*2,0,6.283);g.fill();}
                if(ac){g.save();g.shadowColor="#bb86fc";g.shadowBlur=12;g.strokeStyle="rgba(187,134,252,0.4)";g.lineWidth=2;g.strokeRect(tp[0]-hw,tp[1],w,h);g.restore();}
                g.fillStyle=ac?"#bb86fc":"#444";g.font="bold "+(8*sc)+"px sans-serif";g.textAlign="center";g.fillText(sn[j.i],bt[0],bt[1]+10*sc);
            }
            // === DRAW (back to front) ===
            // Base platform
            iE(0,0,0,70,"#0e0e20","#2a2a45",1.5);
            iE(0,0,2,66,null,"#1e1e40",0.5);
            // Back jars
            for(var i=0;i<J.length;i++)if(J[i].sy<ctrSy)jar(J[i]);
            // Center tube with gradient
            var tb=iso(0,0,0),tt=iso(0,0,185),tw=8*sc;
            var tg=g.createLinearGradient(tt[0]-tw/2,0,tt[0]+tw/2,0);
            tg.addColorStop(0,"#181835");tg.addColorStop(0.5,"#282850");tg.addColorStop(1,"#181835");
            g.fillStyle=tg;g.fillRect(tt[0]-tw/2,tt[1],tw,tb[1]-tt[1]);
            g.strokeStyle="#333355";g.lineWidth=1;g.strokeRect(tt[0]-tw/2,tt[1],tw,tb[1]-tt[1]);
            iE(0,0,185,4,"#282850","#333355",1);
            // Motor mount + spool
            var mt=iso(0,0,195);
            g.fillStyle="#1a1a38";g.fillRect(mt[0]-12*sc,mt[1]-8*sc,24*sc,16*sc);
            g.strokeStyle="#333355";g.strokeRect(mt[0]-12*sc,mt[1]-8*sc,24*sc,16*sc);
            g.fillStyle="#c88a0a";g.beginPath();g.arc(mt[0],mt[1],3*sc,0,6.283);g.fill();
            g.strokeStyle="#a07008";g.lineWidth=1;g.stroke();
            // Cable from spool to head
            g.beginPath();g.moveTo(mt[0],mt[1]+3*sc);g.lineTo(hp[0],hp[1]-9*sc);
            g.strokeStyle="#555";g.lineWidth=1;g.setLineDash([3,2]);g.stroke();g.setLineDash([]);
            // Head clamp (rides center tube, vertical only)
            var cw=14*sc,ch=18*sc;
            g.fillStyle="#5a4520";g.fillRect(hp[0]-cw/2,hp[1]-ch/2,cw,ch);
            g.strokeStyle="#7a6530";g.lineWidth=1.5;g.strokeRect(hp[0]-cw/2,hp[1]-ch/2,cw,ch);
            g.fillStyle="#7a6530";g.fillRect(hp[0]-cw/2+2,hp[1]-1.5,cw-4,3);
            // Arm to FIXED basket position
            g.beginPath();g.moveTo(hp[0],hp[1]);g.lineTo(bp[0],bp[1]);
            g.strokeStyle="#8a7540";g.lineWidth=3*sc;g.stroke();
            g.strokeStyle="#6a5520";g.lineWidth=1.2*sc;g.stroke();
            // Basket at fixed position
            var bR=8*sc,wb=run?Math.sin(t/80)*2.5*sc:0;
            g.beginPath();g.arc(bp[0]+wb,bp[1],bR,0,6.283);
            g.fillStyle=run?"rgba(76,175,80,0.2)":"rgba(50,50,80,0.25)";g.fill();
            g.strokeStyle=run?"#4caf50":"#555";g.lineWidth=1.5;g.stroke();
            // Basket mesh
            g.save();g.globalAlpha=run?0.35:0.2;g.strokeStyle=run?"#4caf50":"#666";g.lineWidth=0.5;
            for(var mi=-1;mi<=1;mi++){g.beginPath();g.moveTo(bp[0]+wb-bR+2,bp[1]+mi*3.5*sc);g.lineTo(bp[0]+wb+bR-2,bp[1]+mi*3.5*sc);g.stroke();}
            g.restore();
            // Motion lines
            if(run){g.save();g.globalAlpha=0.3+Math.sin(t/150)*0.15;g.strokeStyle="#4caf50";g.lineWidth=1;
                for(var ml=-1;ml<=1;ml++){
                    g.beginPath();g.moveTo(bp[0]+wb-bR-3*sc,bp[1]+ml*4*sc);g.lineTo(bp[0]+wb-bR-9*sc,bp[1]+ml*4*sc);g.stroke();
                    g.beginPath();g.moveTo(bp[0]+wb+bR+3*sc,bp[1]+ml*4*sc);g.lineTo(bp[0]+wb+bR+9*sc,bp[1]+ml*4*sc);g.stroke();}
                g.restore();}
            // Front jars (drawn on top)
            for(var i=0;i<J.length;i++)if(J[i].sy>=ctrSy)jar(J[i]);
        }

        async function sendControl(action, extra = {}) {
            try {
                await fetch('/api/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action, ...extra})
                });
                setTimeout(fetchStatus, 200);
            } catch (e) { alert('Control failed: ' + e); }
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

        async function setZCurrent(fieldId) {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById(fieldId).value = parseFloat(data.z_pos || 0).toFixed(1);
                await saveSettings();
            } catch (e) { alert('Failed: ' + e); }
        }

        async function saveSettings() {
            const settings = {};
            document.querySelectorAll('.settings-grid input').forEach(input => { if (input.id) settings[input.id] = input.value; });
            try {
                await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(settings) });
                alert('Settings saved!');
            } catch (e) { alert('Save failed: ' + e); }
        }

        async function scanWifi() {
            const sel = document.getElementById('wifi-ssid');
            sel.innerHTML = '<option>Scanning...</option>';
            try {
                const res = await fetch('/api/wifi/scan');
                const data = await res.json();
                sel.innerHTML = data.networks.map(n => '<option value="' + n.ssid + '">' + n.ssid + ' (' + n.rssi + 'dBm)</option>').join('');
            } catch (e) { sel.innerHTML = '<option>Scan failed</option>'; }
        }

        async function connectWifi() {
            try {
                const res = await fetch('/api/wifi/connect', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ssid: document.getElementById('wifi-ssid').value, password: document.getElementById('wifi-password').value}) });
                const data = await res.json();
                alert(data.success ? 'Connected! IP: ' + data.ip : 'Failed: ' + data.error);
            } catch (e) { alert('Failed: ' + e); }
        }

        async function setStaticIP() {
            var ip = document.getElementById('static-ip').value;
            if (!ip) { alert('Enter an IP'); return; }
            try {
                const res = await fetch('/api/wifi/static', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({static_ip: ip, subnet: document.getElementById('static-subnet').value, gateway: document.getElementById('static-gateway').value, dns: document.getElementById('static-dns').value}) });
                const data = await res.json();
                alert(data.message || 'Done');
            } catch (e) { alert('Failed: ' + e); }
        }

        async function clearStaticIP() {
            try {
                await fetch('/api/wifi/static', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({}) });
                alert('DHCP mode set');
                document.getElementById('static-ip').value = '';
            } catch (e) { alert('Failed: ' + e); }
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

        async function uploadFiles() {
            const input = document.getElementById('ota-files');
            const st = document.getElementById('ota-status');
            if (!input.files.length) { st.textContent = 'No files selected'; return; }
            st.textContent = '';
            for (const file of input.files) {
                st.textContent += 'Uploading ' + file.name + '...\\n';
                try {
                    const content = await file.text();
                    const res = await fetch('/api/ota/upload', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({filename: file.name, content}) });
                    const data = await res.json();
                    st.textContent += data.success ? '  OK (' + data.bytes + ' bytes)\\n' : '  FAILED: ' + data.error + '\\n';
                } catch (e) { st.textContent += '  ERROR: ' + e + '\\n'; }
            }
            st.textContent += 'Done.\\n';
            input.value = '';
        }

        async function loadDeviceFiles() {
            const list = document.getElementById('ota-file-list');
            list.innerHTML = 'Loading...';
            try {
                const res = await fetch('/api/ota/files');
                const data = await res.json();
                list.innerHTML = data.files.map(f => '<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #333"><span>' + f.name + '</span><span style="color:#888">' + f.size + ' B</span></div>').join('');
            } catch (e) { list.innerHTML = 'Failed'; }
        }

        async function rebootDevice() {
            if (!confirm('Reboot? Running cycle will stop.')) return;
            try { await fetch('/api/ota/reboot', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}' }); } catch (e) {}
            document.getElementById('ota-status').textContent = 'Rebooting...';
            setTimeout(() => location.reload(), 10000);
        }

        fetchStatus();
        loadSettings();
        loadStaticIPConfig();
        setInterval(fetchStatus, 1000);
    </script>
</body>
</html>'''

    def _get_css(self):
        """Return embedded CSS."""
        return '''* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a1a; color: #e0e0e0; min-height: 100vh; }
.container { max-width: 600px; margin: 0 auto; padding: 10px; }
header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: linear-gradient(135deg, #1a1a3e, #16213e); border-radius: 12px; margin-bottom: 12px; border: 1px solid #2a2a4e; animation: slide-up 0.3s ease-out; }
h1 { font-size: 1.4em; background: linear-gradient(90deg, #bb86fc, #6c63ff, #bb86fc, #6c63ff); background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 1px; animation: title-gradient 4s ease infinite; }
h2 { font-size: 0.95em; margin-bottom: 10px; color: #7a7aaa; text-transform: uppercase; letter-spacing: 1px; }
.hdr-right { display: flex; align-items: center; gap: 8px; }
.conn-text { font-size: 0.7em; color: #666; text-transform: uppercase; letter-spacing: 1px; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: #444; transition: all 0.3s; }
.status-dot.online { background: #4caf50; box-shadow: 0 0 8px #4caf50, 0 0 20px rgba(76,175,80,0.3); animation: dot-ping 3s ease-in-out infinite; }
.status-dot.offline { background: #f44336; box-shadow: 0 0 8px #f44336; }
section { background: linear-gradient(180deg, #141428, #111122); border-radius: 12px; padding: 16px; margin: 10px 0; border: 1px solid #1e1e3a; animation: slide-up 0.4s ease-out both; transition: border-color 0.3s, box-shadow 0.3s; }
section:hover { border-color: #2a2a5a; box-shadow: 0 4px 20px rgba(108,99,255,0.08); }
section:nth-child(2) { animation-delay: 0.05s; }
section:nth-child(3) { animation-delay: 0.1s; }
section:nth-child(4) { animation-delay: 0.15s; }
section:nth-child(5) { animation-delay: 0.2s; }
section:nth-child(6) { animation-delay: 0.25s; }
section:nth-child(7) { animation-delay: 0.3s; }
section:nth-child(8) { animation-delay: 0.35s; }
section:nth-child(9) { animation-delay: 0.4s; }
.dashboard { background: linear-gradient(180deg, #161630, #111126); border: 1px solid #2a2a50; padding: 16px; }
.dash-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.dash-mode { }
.dash-label { font-size: 0.7em; color: #6a6a9a; text-transform: uppercase; letter-spacing: 2px; }
.dash-val { font-size: 1.8em; font-weight: 700; color: #bb86fc; letter-spacing: 1px; }
.dash-val.running { color: #4caf50; text-shadow: 0 0 12px rgba(76,175,80,0.5); }
.state-badge { padding: 6px 16px; border-radius: 20px; font-size: 0.8em; font-weight: 700; letter-spacing: 1px; }
.state-badge.idle { background: #2a2a3a; color: #888; }
.state-badge.ready { background: rgba(76,175,80,0.15); color: #4caf50; border: 1px solid rgba(76,175,80,0.3); }
.state-badge.running { background: rgba(76,175,80,0.15); color: #4caf50; border: 1px solid rgba(76,175,80,0.3); animation: pulse 2s infinite; }
.state-badge.warn { background: rgba(255,152,0,0.15); color: #ff9800; border: 1px solid rgba(255,152,0,0.3); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }
@keyframes glow-pulse { 0%,100% { box-shadow: 0 0 8px rgba(187,134,252,0.4); } 50% { box-shadow: 0 0 20px rgba(187,134,252,0.8), 0 0 40px rgba(108,99,255,0.3); } }
@keyframes shimmer { 0% { background-position: -200% center; } 100% { background-position: 200% center; } }
@keyframes slide-up { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
@keyframes progress-glow { 0%,100% { box-shadow: 0 0 6px rgba(187,134,252,0.3); } 50% { box-shadow: 0 0 14px rgba(187,134,252,0.7), 0 0 30px rgba(108,99,255,0.2); } }
@keyframes heater-glow { 0%,100% { box-shadow: 0 0 8px rgba(255,152,0,0.3); } 50% { box-shadow: 0 0 20px rgba(255,152,0,0.6), 0 0 40px rgba(255,87,34,0.3); } }
@keyframes dot-ping { 0% { transform: scale(1); } 50% { transform: scale(1.3); } 100% { transform: scale(1); } }
@keyframes title-gradient { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
.carousel { display: flex; align-items: center; justify-content: center; gap: 4px; padding: 12px 0; }
.carousel-item { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 8px 12px; border-radius: 10px; background: #1a1a30; transition: all 0.3s; min-width: 60px; }
.carousel-item span { font-size: 0.65em; color: #555; text-transform: uppercase; letter-spacing: 1px; transition: color 0.3s; }
.carousel-dot { width: 14px; height: 14px; border-radius: 50%; background: #2a2a40; border: 2px solid #333; transition: all 0.3s; }
.carousel-item.active { background: rgba(187,134,252,0.1); border: 1px solid rgba(187,134,252,0.3); }
.carousel-item.active .carousel-dot { background: #bb86fc; border-color: #bb86fc; box-shadow: 0 0 10px rgba(187,134,252,0.6); animation: glow-pulse 2s ease-in-out infinite; }
.carousel-item.active span { color: #bb86fc; font-weight: 600; }
.carousel-arrow { color: #333; font-size: 0.8em; }
.dash-timer-row { padding: 10px 0; }
.timer-block { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.timer-val { font-size: 2em; font-weight: 700; font-variant-numeric: tabular-nums; color: #e0e0e0; font-family: 'SF Mono', 'Consolas', monospace; }
.timer-total { font-size: 1em; color: #555; font-family: 'SF Mono', 'Consolas', monospace; }
.progress-wrap { height: 6px; background: #1a1a30; border-radius: 3px; overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, #6c63ff, #bb86fc, #6c63ff); background-size: 200% auto; border-radius: 3px; transition: width 0.5s ease; animation: shimmer 2s linear infinite, progress-glow 2s ease-in-out infinite; }
.dash-info { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.info-item { flex: 1; min-width: 70px; background: #12122a; border-radius: 8px; padding: 8px 10px; text-align: center; border: 1px solid #1e1e3a; }
.info-lbl { display: block; font-size: 0.6em; color: #5a5a8a; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.info-val { font-size: 1em; font-weight: 600; color: #aaa; }
.info-val.on { color: #4caf50; text-shadow: 0 0 8px rgba(76,175,80,0.5); }
.info-val.off { color: #555; }
.button-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.mode-grid { grid-template-columns: repeat(3, 1fr); }
.btn { padding: 14px; border: none; border-radius: 10px; font-size: 0.95em; font-weight: 600; cursor: pointer; background: #1e1e3a; color: #aaa; transition: all 0.2s; border: 1px solid #2a2a4a; }
.btn:hover { background: #2a2a4a; color: #fff; transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
.btn:active { transform: translateY(0) scale(0.96); box-shadow: none; }
.btn-green { background: linear-gradient(135deg, #2e7d32, #4caf50); color: #fff; border-color: #4caf50; }
.btn-green:hover { box-shadow: 0 0 20px rgba(76,175,80,0.5), 0 4px 15px rgba(0,0,0,0.3); }
.btn-red { background: linear-gradient(135deg, #c62828, #f44336); color: #fff; border-color: #f44336; }
.btn-red:hover { box-shadow: 0 0 20px rgba(244,67,54,0.5), 0 4px 15px rgba(0,0,0,0.3); }
.btn-blue { background: linear-gradient(135deg, #1565c0, #2196f3); color: #fff; border-color: #2196f3; }
.btn-orange { background: linear-gradient(135deg, #e65100, #ff9800); color: #fff; border-color: #ff9800; animation: heater-glow 1.5s ease-in-out infinite; }
.btn-primary { background: linear-gradient(135deg, #6c63ff, #bb86fc); color: #fff; border-color: #bb86fc; box-shadow: 0 0 10px rgba(187,134,252,0.3); animation: glow-pulse 2.5s ease-in-out infinite; }
.btn-small { padding: 10px; font-size: 0.85em; }
.jog-pos { font-size: 1.4em; font-weight: 700; color: #bb86fc; font-family: 'SF Mono', 'Consolas', monospace; }
.z-slider-container { padding: 4px 0; }
.z-slider-labels { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.z-end-label { font-size: 0.7em; color: #5a5a8a; text-transform: uppercase; letter-spacing: 1px; }
.z-slider { -webkit-appearance: none; appearance: none; width: 100%; height: 10px; border-radius: 5px; background: linear-gradient(90deg, #1a1a30, #2a2a50); outline: none; cursor: pointer; }
.z-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, #6c63ff, #bb86fc); border: 2px solid #bb86fc; box-shadow: 0 0 12px rgba(187,134,252,0.5); cursor: pointer; }
.z-slider::-moz-range-thumb { width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, #6c63ff, #bb86fc); border: 2px solid #bb86fc; box-shadow: 0 0 12px rgba(187,134,252,0.5); cursor: pointer; }
.z-slider::-webkit-slider-thumb:hover { box-shadow: 0 0 20px rgba(187,134,252,0.8), 0 0 40px rgba(108,99,255,0.3); transform: scale(1.15); }
.z-slider::-webkit-slider-thumb:active { box-shadow: 0 0 25px rgba(187,134,252,1), 0 0 50px rgba(108,99,255,0.5); }
.z-slider::-webkit-slider-runnable-track { height: 10px; border-radius: 5px; }
.z-ticks { display: flex; justify-content: space-between; margin-top: 6px; font-size: 0.65em; color: #444; }
details { margin: 8px 0; }
summary { cursor: pointer; padding: 10px; background: #12122a; border-radius: 8px; color: #888; font-size: 0.9em; }
summary:hover { color: #bbb; }
.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 12px 0; align-items: center; }
.settings-grid label { color: #6a6a9a; font-size: 0.9em; }
.settings-grid input, .settings-grid select { padding: 8px; border: 1px solid #2a2a4a; border-radius: 6px; background: #0a0a1a; color: #ddd; }
.settings-grid input:focus, .settings-grid select:focus { border-color: #bb86fc; outline: none; box-shadow: 0 0 6px rgba(187,134,252,0.3); }
#wifi-status { padding: 10px; background: #12122a; border-radius: 8px; margin-bottom: 10px; }'''

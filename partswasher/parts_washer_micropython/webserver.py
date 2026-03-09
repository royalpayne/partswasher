"""
Parts Washer v2.0 - Async Web Server
REST API and web interface for remote control
Two-page UI: main (controls) and /config (settings/wifi/OTA)
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

            # Handle streaming file upload (raw body, no JSON)
            path_only = path.split("?")[0]
            if path_only.startswith("/api/ota/raw/") and method == "POST" and content_length > 0:
                response = await self._handle_ota_raw_upload(
                    path_only[13:], reader, content_length)
            else:
                # Read body if present (loop to handle large payloads)
                body = None
                if content_length > 0:
                    chunks = []
                    remaining = content_length
                    while remaining > 0:
                        chunk = await reader.read(min(remaining, 2048))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    body = b"".join(chunks).decode()

                # Route request
                response = await self._route(method, path, body)

            # Send response
            if isinstance(response, tuple) and response[0] == "__stream__":
                await self._stream_page(writer, response[1])
            elif isinstance(response, tuple):
                header, body_content = response
                writer.write(header.encode())
                await writer.drain()
                for i in range(0, len(body_content), 1024):
                    writer.write(body_content[i:i+1024].encode())
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
        path_only = path.split("?")[0]

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
            return ("__stream__", "main")
        elif path_only == "/config":
            return ("__stream__", "config")
        else:
            return self._response(404, "Not Found")

    # ============== STATUS & HANDLERS ==============

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
            "auto_sub_mode": self.washer.auto_sub_mode,
            "auto_total": 23,
            "auto_total_min": (self.washer.settings.get('wash_duration') +
                self.washer.settings.get('rinse1_duration') +
                self.washer.settings.get('rinse2_duration') +
                self.washer.settings.get('heat_duration') +
                3 * self.washer.settings.get('spin_duration')) // 60,
            "wifi": self.wifi.get_status()
        }

    def _handle_settings(self, body):
        try:
            data = json.loads(body)
            self.settings.set_multiple(data)
            self.settings.save()
            return self._json_response({"success": True})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    async def _handle_control(self, body):
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
                async def _home_task():
                    self.washer.home_all()
                asyncio.create_task(_home_task())
                return self._json_response({"success": True, "action": "homing"})
            elif action == "mode":
                mode = data.get("mode", 0)
                self.washer.set_mode(mode)
                return self._json_response({"success": True, "mode": mode})
            elif action == "station":
                station = data.get("station", 0)
                self.washer.select_station(station)
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
            elif action == "restart":
                asyncio.create_task(self.washer.restart_cycle())
                return self._json_response({"success": True, "action": "restarting"})
            elif action == "beep":
                self.washer.beep(1)
                return self._json_response({"success": True, "action": "beep"})
            else:
                return self._json_response({"success": False, "error": "Unknown action"}, 400)
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _handle_wifi_connect(self, body):
        try:
            data = json.loads(body)
            ssid = data.get("ssid")
            password = data.get("password", "")
            if self.wifi.connect(ssid, password, timeout=20):
                return self._json_response({"success": True, "ip": self.wifi.ip_address})
            else:
                return self._json_response({"success": False, "error": "Connection failed"}, 400)
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _handle_static_ip(self, body):
        try:
            data = json.loads(body)
            static_ip = data.get("static_ip")
            if static_ip:
                subnet = data.get("subnet", "255.255.255.0")
                gateway = data.get("gateway")
                dns = data.get("dns", "8.8.8.8")
                self.wifi.set_static_ip(static_ip, subnet, gateway, dns)
                return self._json_response({"success": True, "message": f"Static IP {static_ip} configured. Reboot to apply."})
            else:
                self.wifi.clear_static_ip()
                return self._json_response({"success": True, "message": "Static IP cleared. Will use DHCP on next connect."})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    def _handle_ota_files(self):
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
        try:
            data = json.loads(body)
            filename = data.get("filename", "")
            content = data.get("content", "")
            if not filename or ".." in filename or "/" in filename:
                return self._json_response({"success": False, "error": "Invalid filename"}, 400)
            protected = ("settings.json", "wifi_config.json")
            if filename in protected:
                return self._json_response({"success": False, "error": f"{filename} is protected"}, 400)
            with open("/" + filename, "w") as f:
                written = f.write(content)
            print(f"OTA: wrote {filename} ({written} bytes)")
            return self._json_response({"success": True, "filename": filename, "bytes": written})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    async def _handle_ota_raw_upload(self, filename, reader, content_length):
        """Stream file upload directly to flash — no JSON, minimal RAM."""
        gc.collect()
        if not filename or ".." in filename or "/" in filename:
            # Drain the body
            remaining = content_length
            while remaining > 0:
                chunk = await reader.read(min(remaining, 2048))
                if not chunk:
                    break
                remaining -= len(chunk)
            return self._json_response({"success": False, "error": "Invalid filename"}, 400)
        protected = ("settings.json", "wifi_config.json")
        if filename in protected:
            remaining = content_length
            while remaining > 0:
                chunk = await reader.read(min(remaining, 2048))
                if not chunk:
                    break
                remaining -= len(chunk)
            return self._json_response({"success": False, "error": f"{filename} is protected"}, 400)
        try:
            written = 0
            with open("/" + filename, "w") as f:
                remaining = content_length
                while remaining > 0:
                    chunk = await reader.read(min(remaining, 2048))
                    if not chunk:
                        break
                    f.write(chunk.decode())
                    written += len(chunk)
                    remaining -= len(chunk)
            gc.collect()
            print(f"OTA raw: wrote {filename} ({written} bytes)")
            return self._json_response({"success": True, "filename": filename, "bytes": written})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)}, 400)

    async def _handle_ota_reboot(self):
        self.washer.stop_all()
        print("OTA: rebooting...")
        async def _delayed_reset():
            await asyncio.sleep_ms(500)
            machine.soft_reset()
        asyncio.create_task(_delayed_reset())
        return self._json_response({"success": True, "message": "Rebooting..."})

    # ============== RESPONSE HELPERS ==============

    def _json_response(self, data, status=200):
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
        return (
            f"HTTP/1.1 {status} {message}\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{message}"
        )

    # ============== STREAMING HTML ==============

    async def _stream_page(self, writer, page):
        """Stream HTML page in chunks using chunked transfer encoding."""
        gc.collect()
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
        await writer.drain()

        parts = self._main_parts() if page == "main" else self._config_parts()
        for part_fn in parts:
            gc.collect()
            chunk = part_fn()
            writer.write(f"{len(chunk):x}\r\n".encode())
            for i in range(0, len(chunk), 1024):
                writer.write(chunk[i:i+1024].encode())
                await writer.drain()
            writer.write(b"\r\n")
            await writer.drain()
            del chunk
            gc.collect()

        writer.write(b"0\r\n\r\n")
        await writer.drain()

    def _main_parts(self):
        return [self._css, self._main_html, self._main_js]

    def _config_parts(self):
        return [self._css, self._config_html, self._config_js]

    # ============== CSS (shared) ==============

    def _css(self):
        return '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Parts Washer</title><style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a1a;color:#e0e0e0;min-height:100vh}
.container{max-width:600px;margin:0 auto;padding:10px}
header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:linear-gradient(135deg,#1a1a3e,#16213e);border-radius:12px;margin-bottom:12px;border:1px solid #2a2a4e}
h1{font-size:1.4em;background:linear-gradient(90deg,#bb86fc,#6c63ff,#bb86fc,#6c63ff);background-size:200% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:1px;animation:tg 4s ease infinite}
h2{font-size:.95em;margin-bottom:10px;color:#7a7aaa;text-transform:uppercase;letter-spacing:1px}
.hdr-right{display:flex;align-items:center;gap:8px}
.conn-text{font-size:.7em;color:#666;text-transform:uppercase;letter-spacing:1px}
.sd{width:10px;height:10px;border-radius:50%;background:#444;transition:all .3s}
.sd.on{background:#4caf50;box-shadow:0 0 8px #4caf50,0 0 20px rgba(76,175,80,.3);animation:dp 3s ease-in-out infinite}
.sd.off{background:#f44336;box-shadow:0 0 8px #f44336}
section{background:linear-gradient(180deg,#141428,#111122);border-radius:12px;padding:16px;margin:10px 0;border:1px solid #1e1e3a;transition:border-color .3s,box-shadow .3s}
section:hover{border-color:#2a2a5a;box-shadow:0 4px 20px rgba(108,99,255,.08)}
.db{background:linear-gradient(180deg,#161630,#111126);border:1px solid #2a2a50;padding:16px}
.dt{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.dl{font-size:.7em;color:#6a6a9a;text-transform:uppercase;letter-spacing:2px}
.dv{font-size:1.8em;font-weight:700;color:#bb86fc;letter-spacing:1px}
.dv.run{color:#4caf50;text-shadow:0 0 12px rgba(76,175,80,.5)}
.sb{padding:6px 16px;border-radius:20px;font-size:.8em;font-weight:700;letter-spacing:1px}
.sb.idle{background:#2a2a3a;color:#888}
.sb.ready{background:rgba(76,175,80,.15);color:#4caf50;border:1px solid rgba(76,175,80,.3)}
.sb.run{background:rgba(76,175,80,.15);color:#4caf50;border:1px solid rgba(76,175,80,.3);animation:pulse 2s infinite}
.sb.warn{background:rgba(255,152,0,.15);color:#ff9800;border:1px solid rgba(255,152,0,.3)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
@keyframes dp{0%{transform:scale(1)}50%{transform:scale(1.3)}100%{transform:scale(1)}}
@keyframes tg{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes shimmer{0%{background-position:-200% center}100%{background-position:200% center}}
@keyframes gp{0%,100%{box-shadow:0 0 8px rgba(187,134,252,.4)}50%{box-shadow:0 0 20px rgba(187,134,252,.8),0 0 40px rgba(108,99,255,.3)}}
.car{display:flex;align-items:center;justify-content:center;gap:4px;padding:12px 0}
.ci{display:flex;flex-direction:column;align-items:center;gap:6px;padding:8px 12px;border-radius:10px;background:#1a1a30;transition:all .3s;min-width:60px}
.ci span{font-size:.65em;color:#555;text-transform:uppercase;letter-spacing:1px;transition:color .3s}
.cd{width:14px;height:14px;border-radius:50%;background:#2a2a40;border:2px solid #333;transition:all .3s}
.ci.act{background:rgba(187,134,252,.1);border:1px solid rgba(187,134,252,.3)}
.ci.act .cd{background:#bb86fc;border-color:#bb86fc;box-shadow:0 0 10px rgba(187,134,252,.6);animation:gp 2s ease-in-out infinite}
.ci.act span{color:#bb86fc;font-weight:600}
.dtr{padding:10px 0}
.tb{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.tv{font-size:2em;font-weight:700;font-variant-numeric:tabular-nums;color:#e0e0e0;font-family:'SF Mono','Consolas',monospace}
.tt{font-size:1em;color:#555;font-family:'SF Mono','Consolas',monospace}
.pw{height:6px;background:#1a1a30;border-radius:3px;overflow:hidden}
.pb{height:100%;background:linear-gradient(90deg,#6c63ff,#bb86fc,#6c63ff);background-size:200% auto;border-radius:3px;transition:width .5s ease;animation:shimmer 2s linear infinite}
.di{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.ii{flex:1;min-width:70px;background:#12122a;border-radius:8px;padding:8px 10px;text-align:center;border:1px solid #1e1e3a}
.il{display:block;font-size:.6em;color:#5a5a8a;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.iv{font-size:1em;font-weight:600;color:#aaa}
.iv.on{color:#4caf50;text-shadow:0 0 8px rgba(76,175,80,.5)}
.iv.off{color:#555}
.bg{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.mg{grid-template-columns:repeat(3,1fr)}
.btn{padding:14px;border:none;border-radius:10px;font-size:.95em;font-weight:600;cursor:pointer;background:#1e1e3a;color:#aaa;transition:all .2s;border:1px solid #2a2a4a}
.btn:hover{background:#2a2a4a;color:#fff;transform:translateY(-2px);box-shadow:0 4px 15px rgba(0,0,0,.3)}
.btn:active{transform:translateY(0) scale(.96);box-shadow:none}
.bg0{background:linear-gradient(135deg,#2e7d32,#4caf50);color:#fff;border-color:#4caf50}
.bg0:hover{box-shadow:0 0 20px rgba(76,175,80,.5),0 4px 15px rgba(0,0,0,.3)}
.br0{background:linear-gradient(135deg,#c62828,#f44336);color:#fff;border-color:#f44336}
.br0:hover{box-shadow:0 0 20px rgba(244,67,54,.5),0 4px 15px rgba(0,0,0,.3)}
.bo0{background:linear-gradient(135deg,#e65100,#ff9800);color:#fff;border-color:#ff9800}
.bo0:hover{box-shadow:0 0 20px rgba(255,152,0,.5),0 4px 15px rgba(0,0,0,.3)}
.bb0{background:linear-gradient(135deg,#1565c0,#2196f3);color:#fff;border-color:#2196f3}
.bs{padding:10px;font-size:.85em}
.jp{font-size:1.4em;font-weight:700;color:#bb86fc;font-family:'SF Mono','Consolas',monospace}
.zsc{padding:4px 0}
.zsl{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.zel{font-size:.7em;color:#5a5a8a;text-transform:uppercase;letter-spacing:1px}
.zs{-webkit-appearance:none;appearance:none;width:100%;height:10px;border-radius:5px;background:linear-gradient(90deg,#1a1a30,#2a2a50);outline:none;cursor:pointer}
.zs::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#6c63ff,#bb86fc);border:2px solid #bb86fc;box-shadow:0 0 12px rgba(187,134,252,.5);cursor:pointer}
.zt{display:flex;justify-content:space-between;margin-top:6px;font-size:.65em;color:#444}
details{margin:8px 0}
summary{cursor:pointer;padding:10px;background:#12122a;border-radius:8px;color:#888;font-size:.9em}
summary:hover{color:#bbb}
.sg{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px 0;align-items:center}
.sg label{color:#6a6a9a;font-size:.9em}
.sg input,.sg select{padding:8px;border:1px solid #2a2a4a;border-radius:6px;background:#0a0a1a;color:#ddd}
.sg input:focus,.sg select:focus{border-color:#bb86fc;outline:none;box-shadow:0 0 6px rgba(187,134,252,.3)}
.nav{display:flex;gap:8px;margin-bottom:8px}
.nav a{color:#bb86fc;text-decoration:none;padding:8px 16px;border-radius:8px;background:#1a1a30;font-size:.85em;border:1px solid #2a2a4a}
.nav a:hover{background:#2a2a4a}
#ws{padding:10px;background:#12122a;border-radius:8px;margin-bottom:10px}
</style></head><body><div class="container">'''

    # ============== MAIN PAGE ==============

    def _main_html(self):
        return '''
<header><h1>Parts Washer</h1><div class="hdr-right"><span id="ct" class="conn-text">--</span><div id="si" class="sd"></div></div></header>
<div class="nav"><a href="/config">Settings</a></div>
<section class="db">
<div class="dt"><div><div class="dl">MODE</div><div id="dm" class="dv">--</div></div><div id="ds" class="sb idle">IDLE</div></div>
<div class="car">
<div id="sc-0" class="ci act"><div class="cd"></div><span>WASH</span></div><span style="color:#333">-</span>
<div id="sc-1" class="ci"><div class="cd"></div><span>RINSE 1</span></div><span style="color:#333">-</span>
<div id="sc-2" class="ci"><div class="cd"></div><span>RINSE 2</span></div><span style="color:#333">-</span>
<div id="sc-3" class="ci"><div class="cd"></div><span>HEATER</span></div>
</div>
<div class="dtr"><div class="tb"><span id="dt" class="tv">00:00</span><span id="dd" class="tt"></span></div><div class="pw"><div id="dp" class="pb" style="width:0%"></div></div></div>
<div class="di">
<div class="ii"><span class="il">Z</span><span id="dz" class="iv">0.0 mm</span></div>
<div class="ii"><span class="il">HEATER</span><span id="dh" class="iv off">OFF</span></div>
<div id="daw" class="ii" style="display:none"><span class="il">AUTO</span><span id="da" class="iv">0/23</span></div>
<div class="ii"><span class="il">CYCLE</span><span id="datv" class="iv">0 min</span></div>
<div class="ii"><span class="il">HOMED</span><span id="dhm" class="iv off">NO</span></div>
</div></section>
<section><h2>Controls</h2><div class="bg">
<button onclick="sc('start')" class="btn bg0">START</button>
<button onclick="sc('stop')" class="btn br0">STOP</button>
<button onclick="sc('restart')" class="btn bo0">RESTART</button>
<button onclick="sc('home')" class="btn bb0">HOME</button>
<button onclick="sc('heater',{state:!hs})" id="hb" class="btn">HEATER</button>
</div></section>
<section><h2>Mode Select</h2><div class="bg mg">
<button id="m-0" onclick="sc('mode',{mode:0})" class="btn bs">JITTER</button>
<button id="m-1" onclick="sc('mode',{mode:1})" class="btn bs">CLEAN</button>
<button id="m-2" onclick="sc('mode',{mode:2})" class="btn bs">SPIN</button>
<button id="m-3" onclick="sc('mode',{mode:3})" class="btn bs">HEAT</button>
<button id="m-4" onclick="sc('mode',{mode:4})" class="btn bs">AUTO</button>
</div></section>
<section><h2>Station Select</h2><div class="bg">
<button onclick="sc('station',{station:0})" class="btn bs">WASH</button>
<button onclick="sc('station',{station:1})" class="btn bs">RINSE 1</button>
<button onclick="sc('station',{station:2})" class="btn bs">RINSE 2</button>
<button onclick="sc('station',{station:3})" class="btn bs">HEATER</button>
</div></section>
<section><h2>Z-Axis</h2><div class="zsc">
<div class="zsl"><span class="zel">HOME</span><span id="jz" class="jp">0.0 cm</span><span class="zel">WASH</span></div>
<input type="range" id="zs" class="zs" min="0" max="20.6" step="0.1" value="0">
<div class="zt"><span>0</span><span>5</span><span>10</span><span>15</span><span>20.6</span></div>
</div></section>
</div></body>'''

    def _main_js(self):
        return '''<script>
var hs=false,za=false,zd=null;
(function(){var s=document.getElementById('zs');
s.addEventListener('input',function(){za=true;document.getElementById('jz').textContent=(parseFloat(s.value)).toFixed(1)+' cm';clearTimeout(zd);zd=setTimeout(function(){sc('z_move_to',{position:s.value*10});za=false},150)});
s.addEventListener('change',function(){sc('z_move_to',{position:s.value*10});za=false})})();
async function fs(){try{var r=await fetch('/api/status');var d=await r.json();uu(d)}catch(e){document.getElementById('si').className='sd off';document.getElementById('ct').textContent='OFFLINE'}}
function ft(ms){var s=Math.floor(ms/1000);var m=Math.floor(s/60);s=s%60;return(m<10?'0':'')+m+':'+(s<10?'0':'')+s}
function uu(d){document.getElementById('si').className='sd on';document.getElementById('ct').textContent='ONLINE';
var mn=d.mode_name||'--';if(d.mode===4&&d.running&&d.auto_sub_mode!==null){var sn=['JITTER','CLEAN','SPIN','HEAT'];mn='AUTO ('+sn[d.auto_sub_mode]+')'}document.getElementById('dm').textContent=mn;document.getElementById('dm').className=d.running?'dv run':'dv';
var sb=document.getElementById('ds');if(!d.homed){sb.textContent='NOT HOMED';sb.className='sb warn'}else if(d.running){sb.textContent='RUNNING';sb.className='sb run'}else{sb.textContent='READY';sb.className='sb ready'}
for(var i=0;i<4;i++){var e=document.getElementById('sc-'+i);if(e)e.className=i===d.station?'ci act':'ci'}
var tm=document.getElementById('dt'),du=document.getElementById('dd'),pg=document.getElementById('dp');
if(d.running&&d.duration_ms>0){tm.textContent=ft(d.elapsed_ms);du.textContent='/ '+ft(d.duration_ms);pg.style.width=Math.min(100,(d.elapsed_ms/d.duration_ms)*100)+'%'}else if(d.running){tm.textContent=ft(d.elapsed_ms);du.textContent='';pg.style.width='0%'}else{tm.textContent='00:00';du.textContent='';pg.style.width='0%'}
var zp=(parseFloat(d.z_pos||0)/10).toFixed(1);var zt=(parseFloat(d.z_target||0)/10).toFixed(1);var zm=zp!==zt;document.getElementById('dz').textContent=zp+' cm';
if(!za){document.getElementById('jz').textContent=(zm?zt:zp)+' cm';document.getElementById('zs').value=zm?zt:zp}
var h=document.getElementById('dh');h.textContent=d.heater?'ON':'OFF';h.className=d.heater?'iv on':'iv off';hs=d.heater;
var hm=document.getElementById('dhm');hm.textContent=d.homed?'YES':'NO';hm.className=d.homed?'iv on':'iv off';
var aw=document.getElementById('daw');if(d.mode===4&&d.running){aw.style.display='';document.getElementById('da').textContent=d.auto_step+'/'+d.auto_total}else{aw.style.display='none'}
document.getElementById('datv').textContent=d.auto_total_min+' min';
for(var i=0;i<5;i++){var mb=document.getElementById('m-'+i);if(mb)mb.style.borderColor=i===d.mode?'#bb86fc':'#2a2a4a'}}
async function sc(a,x){try{await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({action:a},x||{}))});setTimeout(fs,200)}catch(e){alert('Failed: '+e)}}
fs();setInterval(fs,1000);
</script></html>'''

    # ============== CONFIG PAGE ==============

    def _config_html(self):
        return '''
<header><h1>Parts Washer Config</h1></header>
<div class="nav"><a href="/">Dashboard</a></div>
<section><h2>Timing</h2><div class="sg">
<label>Wash (s):</label><input type="number" id="wash_duration" min="0" max="600">
<label>Rinse 1 (s):</label><input type="number" id="rinse1_duration" min="0" max="600">
<label>Rinse 2 (s):</label><input type="number" id="rinse2_duration" min="0" max="600">
<label>Spin (s):</label><input type="number" id="spin_duration" min="0" max="600">
<label>Heat (s):</label><input type="number" id="heat_duration" min="0" max="3600">
</div></section>
<section><h2>Motor Speeds</h2><div class="sg">
<label title="Agitation speed for wash/rinse cleaning. Higher=faster agitation">Clean RPM:</label><input type="number" id="clean_rpm" min="100" max="3000" title="Agitation RPM during clean mode (wash/rinse)">
<label title="Centrifugal spin dry speed. Higher=more water removal">Spin RPM:</label><input type="number" id="spin_rpm" min="100" max="3000" title="Spin dry RPM. Limited by motor torque">
<label title="Slow rotation during heat dry cycle">Heat RPM:</label><input type="number" id="heat_rpm" min="50" max="500" title="Gentle rotation while heating">
<label title="Oscillations per second in jitter mode. Higher=more vigorous">Jitter Osc/sec:</label><input type="number" id="jitter_osc" min="1" max="20" step="0.5" title="Direction changes per second for jitter">
<label title="Z-axis motor speed. Lower=smoother but slower travel">Z Speed (RPM):</label><input type="number" id="z_speed_rpm" min="50" max="500" title="Z motor RPM. Try 200-300 for smooth motion">
<label title="Rotation motor step rate. Higher=faster station changes">Rot Speed (Hz):</label><input type="number" id="rot_speed_hz" min="500" max="10000" step="100" title="Steps/sec for rotation motor">
</div></section>
<section><h2>Agitation Ramp</h2><div class="sg">
<label title="Hz added per ramp step. Lower=gentler acceleration">Ramp Hz/step:</label><input type="number" id="agit_ramp_hz" min="10" max="1000" step="10" title="Frequency increment per ramp step. Lower=smoother ramp-up/down">
<label title="Time between ramp steps. Higher=slower acceleration">Ramp ms/step:</label><input type="number" id="agit_ramp_ms" min="1" max="100" title="Milliseconds between each ramp step. Higher=gentler">
<label title="Pause after ramp-down before reversing direction">Rev Pause (ms):</label><input type="number" id="agit_rev_pause" min="0" max="5000" step="50" title="Dwell time at zero speed between direction changes">
</div></section>
<section><h2>Z-Axis Smoothness</h2><div class="sg">
<label title="Steps over which to accelerate/decelerate. Higher=smoother but longer ramp">Accel Steps:</label><input type="number" id="z_accel_steps" min="50" max="5000" step="50" title="Ramp length in steps. Try 800-1600 for smooth motion. Default 400">
<label title="Initial step delay in microseconds. Higher=slower start, less jerk">Start Delay (us):</label><input type="number" id="z_start_delay" min="500" max="10000" step="100" title="Step delay at start of ramp. Higher=gentler start. Default 2000">
<label title="Steps between speed changes during ramp. Lower=finer speed transitions">Ramp Interval:</label><input type="number" id="z_ramp_interval" min="8" max="64" title="ISR updates freq every N steps. Lower=smoother. Min 8 to avoid lockup. Default 16">
</div></section>
<section><h2>Z Positions (mm)</h2><div class="sg">
<label>Home (Top):</label><div><input type="number" id="z_pos_home" step="0.1" min="0" max="250" style="width:80px"> <button onclick="szc('z_pos_home')" class="btn bs">Set Current</button></div>
<label>Spin (Mid):</label><div><input type="number" id="z_pos_spin" step="0.1" min="0" max="250" style="width:80px"> <button onclick="szc('z_pos_spin')" class="btn bs">Set Current</button></div>
<label>Wash (Bottom):</label><div><input type="number" id="z_pos_wash" step="0.1" min="0" max="250" style="width:80px"> <button onclick="szc('z_pos_wash')" class="btn bs">Set Current</button></div>
<label>Max Travel:</label><input type="number" id="z_max_travel" step="0.1" min="0" max="250">
</div></section>
<button onclick="ss()" class="btn bb0" style="width:100%;margin:10px 0">Save Settings</button>
<section><h2>WiFi</h2><div id="ws"></div>
<details><summary>Configure WiFi</summary><div class="sg">
<label>SSID:</label><select id="wssid"></select>
<button onclick="wsc()" class="btn bs">Scan</button>
<label>Password:</label><input type="password" id="wpw">
</div><button onclick="wc()" class="btn bb0">Connect</button></details>
<details><summary>Static IP</summary><div class="sg">
<label>IP:</label><input type="text" id="sip" placeholder="192.168.71.154">
<label>Subnet:</label><input type="text" id="ssn" value="255.255.255.0">
<label>Gateway:</label><input type="text" id="sgw" placeholder="192.168.71.1">
<label>DNS:</label><input type="text" id="sdns" value="8.8.8.8">
</div><button onclick="ssi()" class="btn bb0">Set Static IP</button>
<button onclick="csi()" class="btn bs">Use DHCP</button></details></section>
<section><h2>OTA Update</h2>
<input type="file" id="of" multiple accept=".py" style="color:#888">
<button onclick="uf()" class="btn bb0" style="margin-top:10px">Upload Files</button>
<div id="os" style="padding:10px;background:#1a1a2e;border-radius:5px;margin:10px 0;font-family:monospace;font-size:.85em;white-space:pre-wrap"></div>
<details><summary>Files on Device</summary><div id="fl" style="padding:10px"></div>
<button onclick="lf()" class="btn bs">Refresh</button></details>
<button onclick="rb()" class="btn br0" style="margin-top:10px;width:100%">Reboot Device</button>
</section></div></body>'''

    def _config_js(self):
        return '''<script>
async function ls(){try{var r=await fetch('/api/settings');var d=await r.json();for(var k in d){var e=document.getElementById(k);if(e)e.value=d[k]}}catch(e){}}
async function szc(id){try{var r=await fetch('/api/status');var d=await r.json();document.getElementById(id).value=parseFloat(d.z_pos||0).toFixed(1);await ss()}catch(e){alert('Failed: '+e)}}
async function ss(){var s={};document.querySelectorAll('.sg input').forEach(function(i){if(i.id)s[i.id]=i.value});try{await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)});alert('Saved!')}catch(e){alert('Save failed: '+e)}}
async function wsc(){var s=document.getElementById('wssid');s.innerHTML='<option>Scanning...</option>';try{var r=await fetch('/api/wifi/scan');var d=await r.json();s.innerHTML=d.networks.map(function(n){return'<option value="'+n.ssid+'">'+n.ssid+' ('+n.rssi+'dBm)</option>'}).join('')}catch(e){s.innerHTML='<option>Failed</option>'}}
async function wc(){try{var r=await fetch('/api/wifi/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid:document.getElementById('wssid').value,password:document.getElementById('wpw').value})});var d=await r.json();alert(d.success?'Connected! IP: '+d.ip:'Failed: '+d.error)}catch(e){alert('Failed: '+e)}}
async function ssi(){var ip=document.getElementById('sip').value;if(!ip){alert('Enter IP');return}try{var r=await fetch('/api/wifi/static',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({static_ip:ip,subnet:document.getElementById('ssn').value,gateway:document.getElementById('sgw').value,dns:document.getElementById('sdns').value})});var d=await r.json();alert(d.message||'Done')}catch(e){alert('Failed: '+e)}}
async function csi(){try{await fetch('/api/wifi/static',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});alert('DHCP set');document.getElementById('sip').value=''}catch(e){alert('Failed: '+e)}}
async function lip(){try{var r=await fetch('/api/wifi/status');var d=await r.json();if(d.static_ip){document.getElementById('sip').value=d.static_ip;document.getElementById('ssn').value=d.subnet||'255.255.255.0';document.getElementById('sgw').value=d.gateway||'';document.getElementById('sdns').value=d.dns||'8.8.8.8'}}catch(e){}}
async function uf(){var i=document.getElementById('of'),st=document.getElementById('os');if(!i.files.length){st.textContent='No files';return}st.textContent='';for(var f of i.files){st.textContent+='Uploading '+f.name+'...\\n';try{var c=await f.text();var r=await fetch('/api/ota/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:f.name,content:c})});var d=await r.json();st.textContent+=d.success?'  OK ('+d.bytes+' B)\\n':'  FAIL: '+d.error+'\\n'}catch(e){st.textContent+='  ERR: '+e+'\\n'}}st.textContent+='Done.\\n';i.value=''}
async function lf(){var l=document.getElementById('fl');l.innerHTML='Loading...';try{var r=await fetch('/api/ota/files');var d=await r.json();l.innerHTML=d.files.map(function(f){return'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #333"><span>'+f.name+'</span><span style="color:#888">'+f.size+' B</span></div>'}).join('')}catch(e){l.innerHTML='Failed'}}
async function rb(){if(!confirm('Reboot?'))return;try{await fetch('/api/ota/reboot',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})}catch(e){}document.getElementById('os').textContent='Rebooting...';setTimeout(function(){location.reload()},10000)}
ls();lip();
</script></html>'''

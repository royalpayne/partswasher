"""Minimal OTA server for large file uploads (fallback recovery).
Connects WiFi from saved config, then serves on port 8080.

Upload: POST /upload/<filename> with raw file content as body
List:   GET /files
Reboot: POST /reboot
"""
import uasyncio as asyncio
import json
import os
import gc
import machine
import network
import time


def connect_wifi():
    """Connect WiFi using saved config."""
    try:
        with open("/wifi_config.json", "r") as f:
            cfg = json.load(f)
    except:
        print("No wifi config found")
        return False

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    static_ip = cfg.get("static_ip")
    if static_ip:
        subnet = cfg.get("subnet", "255.255.255.0")
        gateway = cfg.get("gateway", static_ip.rsplit('.', 1)[0] + ".1")
        dns = cfg.get("dns", "8.8.8.8")
        sta.ifconfig((static_ip, subnet, gateway, dns))

    ssid = cfg.get("ssid", "")
    if not ssid:
        return False

    print("Bootstrap WiFi:", ssid)
    sta.connect(ssid, cfg.get("password", ""))
    start = time.time()
    while not sta.isconnected():
        if time.time() - start > 15:
            print("WiFi timeout")
            return False
        time.sleep(0.5)
    print("Connected:", sta.ifconfig()[0])
    return True


async def handle(reader, writer):
    gc.collect()
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=30)
        if not line:
            return
        parts = line.decode().strip().split(" ")
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1].split("?")[0]

        cl = 0
        while True:
            h = await reader.readline()
            if h == b"\r\n" or h == b"":
                break
            if h.lower().startswith(b"content-length:"):
                cl = int(h.decode().split(":")[1].strip())

        if path.startswith("/upload/") and method == "POST" and cl > 0:
            fn = path[8:]
            if not fn or ".." in fn:
                while cl > 0:
                    chunk = await reader.read(min(cl, 2048))
                    if not chunk:
                        break
                    cl -= len(chunk)
                resp = '{"ok":false,"e":"bad name"}'
            else:
                n = 0
                with open("/" + fn, "w") as f:
                    while cl > 0:
                        chunk = await reader.read(min(cl, 2048))
                        if not chunk:
                            break
                        f.write(chunk.decode())
                        n += len(chunk)
                        cl -= len(chunk)
                gc.collect()
                resp = '{"ok":true,"f":"' + fn + '","b":' + str(n) + '}'

        elif path == "/files":
            files = []
            for name in os.listdir("/"):
                files.append({"n": name, "s": os.stat("/" + name)[6]})
            resp = json.dumps({"files": files})

        elif path == "/reboot" and method == "POST":
            resp = '{"ok":true,"msg":"rebooting"}'
            writer.write(("HTTP/1.0 200 OK\r\nContent-Length: " + str(len(resp)) + "\r\n\r\n" + resp).encode())
            await writer.drain()
            writer.close()
            await asyncio.sleep_ms(500)
            machine.soft_reset()
            return
        else:
            resp = '{"ok":false,"e":"use POST /upload/<filename>, GET /files, POST /reboot"}'

        writer.write(("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: " + str(len(resp)) + "\r\n\r\n" + resp).encode())
        await writer.drain()
    except Exception as e:
        print("ota_bootstrap err:", e)
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    srv = await asyncio.start_server(handle, "0.0.0.0", 8080)
    print("OTA bootstrap on port 8080")
    while True:
        await asyncio.sleep(60)

if connect_wifi():
    asyncio.run(main())
else:
    print("Bootstrap: no WiFi, halting")

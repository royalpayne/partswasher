#!/usr/bin/env python3
"""OTA Push - Watch for file changes and auto-upload to ESP32-S3 over WiFi.

Usage:
    python3 ota_push.py                     # Upload all + watch for changes
    python3 ota_push.py main.py stepper.py  # Upload specific files + watch
    python3 ota_push.py --no-watch          # Upload all, don't watch
    python3 ota_push.py --reboot            # Upload all + reboot + watch
    python3 ota_push.py --bootstrap         # Bootstrap: upload helper, reboot,
                                            # then upload all via port 8080
"""

import json
import os
import socket
import sys
import time

DEVICE_IP = "192.168.71.157"
DEVICE_PORT = 80
BOOTSTRAP_PORT = 8080

WATCH_FILES = [
    "config.py", "settings.py", "stepper.py", "ssd1306.py",
    "wifi_manager.py", "webserver.py", "main.py",
]


def http_post(path, data, port=None):
    """POST JSON to device, return parsed response."""
    p = port or DEVICE_PORT
    body = json.dumps(data).encode()
    s = socket.socket()
    s.settimeout(60)
    try:
        s.connect((DEVICE_IP, p))
        headers = (
            f"POST {path} HTTP/1.0\r\n"
            f"Host: {DEVICE_IP}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
        ).encode()
        s.sendall(headers)

        # Send body in chunks so ESP32 TCP buffer can keep up
        CHUNK = 2048
        for i in range(0, len(body), CHUNK):
            s.sendall(body[i:i + CHUNK])
            if len(body) > 10000:
                time.sleep(0.05)

        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()

        parts = resp.split(b"\r\n\r\n", 1)
        if len(parts) == 2:
            return json.loads(parts[1])
        return {"error": "No response body"}
    except Exception as e:
        try:
            s.close()
        except Exception:
            pass
        return {"error": str(e)}


def http_get(path, port=None):
    """GET from device, return parsed JSON response."""
    p = port or DEVICE_PORT
    s = socket.socket()
    s.settimeout(10)
    try:
        s.connect((DEVICE_IP, p))
        s.sendall(f"GET {path} HTTP/1.0\r\nHost: {DEVICE_IP}\r\n\r\n".encode())
        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()
        parts = resp.split(b"\r\n\r\n", 1)
        if len(parts) == 2:
            return json.loads(parts[1])
        return {"error": "No response body"}
    except Exception as e:
        try:
            s.close()
        except Exception:
            pass
        return {"error": str(e)}


def upload_file_raw(filepath, port, path=None):
    """Upload file via raw POST (no JSON wrapping)."""
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        content = f.read()
    size = len(content)
    print(f"  {filename} ({size} bytes)...", end="", flush=True)

    upload_path = path or f"/upload/{filename}"
    s = socket.socket()
    s.settimeout(60)
    try:
        s.connect((DEVICE_IP, port))
        headers = (
            f"POST {upload_path} HTTP/1.0\r\n"
            f"Host: {DEVICE_IP}\r\n"
            f"Content-Length: {size}\r\n"
            f"\r\n"
        ).encode()
        s.sendall(headers)

        # Send in chunks
        CHUNK = 2048
        for i in range(0, size, CHUNK):
            s.sendall(content[i:i + CHUNK])
            if size > 10000:
                time.sleep(0.05)

        resp = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
        s.close()

        parts = resp.split(b"\r\n\r\n", 1)
        if len(parts) == 2:
            result = json.loads(parts[1])
            if result.get("ok") or result.get("success"):
                written = result.get("b") or result.get("bytes") or "?"
                print(f"  OK ({written} bytes written)")
                return True
            else:
                err = result.get("e") or result.get("error") or "unknown"
                print(f"  FAILED: {err}")
                return False
        print("  FAILED: No response body")
        return False
    except Exception as e:
        try:
            s.close()
        except Exception:
            pass
        print(f"  FAILED: {e}")
        return False


def upload_file(filepath, port=None, api_path=None):
    """Upload a single file to the device using raw POST (streaming, no JSON)."""
    p = port or DEVICE_PORT
    filename = os.path.basename(filepath)

    # Build the upload path
    if p != DEVICE_PORT:
        path = f"/upload/{filename}"
    else:
        path = f"/api/ota/raw/{filename}"

    return upload_file_raw(filepath, p, path)


def reboot(port=None):
    """Reboot the device."""
    p = port or DEVICE_PORT
    path = "/api/ota/reboot" if p == DEVICE_PORT else "/reboot"
    print("Rebooting device...")
    http_post(path, {}, port=p)
    print("Waiting for device to come back up...")
    time.sleep(10)
    if check_device():
        print("Device is back online!")
        return True
    else:
        print("Device not responding — may need power cycle.")
        return False


def check_device(port=None):
    """Check if device is reachable."""
    p = port or DEVICE_PORT
    try:
        s = socket.socket()
        s.settimeout(5)
        s.connect((DEVICE_IP, p))
        path = "/api/ota/files" if p == DEVICE_PORT else "/files"
        s.sendall(f"GET {path} HTTP/1.0\r\nHost: {DEVICE_IP}\r\n\r\n".encode())
        resp = s.recv(1024)
        s.close()
        return b"200" in resp
    except Exception:
        return False


def bootstrap():
    """Bootstrap: upload tiny OTA helper via port 80, reboot into it,
    then upload all large files via port 8080's robust reader."""
    print("=== BOOTSTRAP MODE ===")
    print(f"Step 1: Upload ota_bootstrap.py via main server (port {DEVICE_PORT})...")

    if not check_device():
        print(f"Cannot reach device at {DEVICE_IP}:{DEVICE_PORT}")
        return False

    if not upload_file("ota_bootstrap.py"):
        print("Failed to upload bootstrap script!")
        return False

    # Upload a boot.py that runs the bootstrap server
    print("  Creating boot loader...")
    boot_code = "import ota_bootstrap"
    result = http_post("/api/ota/upload", {
        "filename": "boot.py",
        "content": boot_code,
    })
    if not (result.get("success") or result.get("ok")):
        print(f"  Failed to upload boot.py: {result}")
        return False
    print("  boot.py OK")

    print(f"\nStep 2: Rebooting into bootstrap server...")
    http_post("/api/ota/reboot", {})
    print("Waiting for bootstrap server on port 8080...")
    time.sleep(10)

    # Wait for bootstrap server
    retries = 10
    while retries > 0:
        if check_device(BOOTSTRAP_PORT):
            break
        print(f"  Waiting... ({retries} retries left)")
        time.sleep(3)
        retries -= 1

    if retries == 0:
        print("Bootstrap server didn't come up!")
        return False
    print("Bootstrap server is ready!\n")

    print(f"Step 3: Uploading all files via bootstrap (port {BOOTSTRAP_PORT})...")
    ok = 0
    fail = 0
    for f in WATCH_FILES:
        if os.path.exists(f):
            if upload_file(f, port=BOOTSTRAP_PORT, api_path="/upload"):
                ok += 1
            else:
                fail += 1
        else:
            print(f"  SKIP  {f} (not found)")

    print(f"\n  {ok} uploaded, {fail} failed")

    if fail > 0:
        print("Some uploads failed!")
        return False

    # Remove bootstrap boot.py and restore normal boot
    print("\nStep 4: Cleaning up bootstrap...")
    # Upload empty boot.py to restore normal startup
    http_post("/upload", {"filename": "boot.py", "content": ""}, port=BOOTSTRAP_PORT)
    print("  boot.py cleared")

    print("\nStep 5: Rebooting into normal firmware...")
    http_post("/reboot", {}, port=BOOTSTRAP_PORT)
    time.sleep(10)

    retries = 10
    while retries > 0:
        if check_device():
            break
        print(f"  Waiting... ({retries} retries left)")
        time.sleep(3)
        retries -= 1

    if check_device():
        print("Device is back online with updated firmware!")
        return True
    else:
        print("Device not responding after reboot — may need power cycle.")
        return False


def watch_files(files, do_reboot=False):
    """Watch files for changes using poll loop."""
    print(f"\nWatching for changes... (Ctrl+C to stop)")
    print(f"Files: {', '.join(files)}")

    mtimes = {}
    for f in files:
        if os.path.exists(f):
            mtimes[f] = os.path.getmtime(f)

    try:
        while True:
            time.sleep(1)
            for f in files:
                if not os.path.exists(f):
                    continue
                mtime = os.path.getmtime(f)
                if f in mtimes and mtime != mtimes[f]:
                    ts = time.strftime("%H:%M:%S")
                    print(f"\n{ts} {f} changed, uploading...")
                    mtimes[f] = mtime
                    if upload_file(f):
                        if do_reboot:
                            reboot()
                        else:
                            print("  (use --reboot flag to auto-reboot after upload)")
                elif f not in mtimes:
                    mtimes[f] = mtime
    except KeyboardInterrupt:
        print("\nStopped watching.")


def main():
    args = sys.argv[1:]

    if "--bootstrap" in args:
        bootstrap()
        return

    do_watch = "--no-watch" not in args
    do_reboot = "--reboot" in args
    flags = {"--no-watch", "--reboot", "--bootstrap"}
    specific_files = [a for a in args if a not in flags]

    files = specific_files if specific_files else WATCH_FILES

    print(f"OTA Push — device: {DEVICE_IP}")
    print(f"Checking device...", end=" ", flush=True)
    if not check_device():
        print(f"FAILED — cannot reach {DEVICE_IP}")
        sys.exit(1)
    print("online")

    # Upload
    print(f"\nUploading {len(files)} file(s)...")
    ok = 0
    fail = 0
    for f in files:
        if os.path.exists(f):
            if upload_file(f):
                ok += 1
            else:
                fail += 1
        else:
            print(f"  SKIP  {f} (not found)")

    print(f"\n  {ok} uploaded, {fail} failed")

    if fail > 0:
        print("  Some uploads failed.")
        print("  TIP: Run 'python3 ota_push.py --bootstrap' to fix large file uploads.")

    if ok > 0 and do_reboot:
        reboot()

    if do_watch:
        watch_files(files, do_reboot)


if __name__ == "__main__":
    main()

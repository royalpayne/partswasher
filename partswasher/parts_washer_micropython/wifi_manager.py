"""
Parts Washer v2.0 - WiFi Manager
Handles WiFi connection and AP mode for configuration
"""

import network
import time
import json


class WiFiManager:
    """Manages WiFi connectivity with fallback to AP mode."""

    CONFIG_FILE = "/wifi_config.json"
    AP_SSID = "PartsWasher"
    AP_PASSWORD = "washparts"

    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self.connected = False
        self.ap_mode = False
        self.ip_address = None
        self.static_ip = None

    def load_config(self):
        """Load WiFi credentials from file."""
        try:
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return None

    def save_config(self, ssid, password, static_ip=None, subnet=None, gateway=None, dns=None):
        """Save WiFi credentials and optional static IP to file."""
        config = {"ssid": ssid, "password": password}
        if static_ip:
            config["static_ip"] = static_ip
            config["subnet"] = subnet or "255.255.255.0"
            config["gateway"] = gateway or static_ip.rsplit('.', 1)[0] + ".1"
            config["dns"] = dns or "8.8.8.8"
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def connect(self, ssid=None, password=None, static_ip=None, subnet=None, gateway=None, dns=None, timeout=15):
        """
        Connect to WiFi network.
        If no credentials provided, tries to load from config.
        Returns True if connected, False if failed.
        """
        # Load saved config if not provided
        config = None
        if ssid is None:
            config = self.load_config()
            if config:
                ssid = config.get("ssid")
                password = config.get("password")
                static_ip = config.get("static_ip")
                subnet = config.get("subnet")
                gateway = config.get("gateway")
                dns = config.get("dns")
            else:
                print("No WiFi config found")
                return False

        if not ssid:
            return False

        # Disable AP mode while connecting
        self.ap.active(False)

        # Enable station mode
        self.sta.active(True)

        # Apply static IP before connecting if configured
        if static_ip:
            subnet = subnet or "255.255.255.0"
            gateway = gateway or static_ip.rsplit('.', 1)[0] + ".1"
            dns = dns or "8.8.8.8"
            print(f"Setting static IP: {static_ip}")
            self.sta.ifconfig((static_ip, subnet, gateway, dns))
            self.static_ip = static_ip

        # Already connected to this network?
        if self.sta.isconnected() and self.sta.config("ssid") == ssid:
            self.connected = True
            self.ip_address = self.sta.ifconfig()[0]
            return True

        print(f"Connecting to WiFi: {ssid}")
        self.sta.connect(ssid, password)

        # Wait for connection
        start = time.time()
        while not self.sta.isconnected():
            if time.time() - start > timeout:
                print("WiFi connection timeout")
                self.sta.active(False)
                return False
            time.sleep(0.5)

        self.connected = True
        self.ap_mode = False
        self.ip_address = self.sta.ifconfig()[0]
        print(f"Connected! IP: {self.ip_address}")

        # Save working credentials with static IP if provided
        self.save_config(ssid, password, static_ip, subnet, gateway, dns)
        return True

    def start_ap(self, ssid=None, password=None):
        """Start Access Point mode for initial configuration."""
        ssid = ssid or self.AP_SSID
        password = password or self.AP_PASSWORD

        # Disable station mode
        self.sta.active(False)

        # Enable and configure AP
        self.ap.active(True)
        self.ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA2_PSK)

        self.ap_mode = True
        self.connected = False
        self.ip_address = self.ap.ifconfig()[0]

        print(f"AP Mode started: {ssid}")
        print(f"Connect to WiFi '{ssid}' with password '{password}'")
        print(f"Then visit: http://{self.ip_address}")
        return self.ip_address

    def scan_networks(self):
        """Scan for available WiFi networks."""
        self.sta.active(True)
        try:
            networks = self.sta.scan()
            # Return list of (ssid, rssi, security)
            result = []
            seen = set()
            for net in networks:
                ssid = net[0].decode("utf-8")
                if ssid and ssid not in seen:
                    seen.add(ssid)
                    result.append({
                        "ssid": ssid,
                        "rssi": net[3],
                        "secure": net[4] != 0
                    })
            # Sort by signal strength
            result.sort(key=lambda x: x["rssi"], reverse=True)
            return result
        except Exception as e:
            print(f"Scan error: {e}")
            return []

    def disconnect(self):
        """Disconnect from WiFi."""
        self.sta.disconnect()
        self.sta.active(False)
        self.connected = False
        self.ip_address = None

    def stop_ap(self):
        """Stop Access Point."""
        self.ap.active(False)
        self.ap_mode = False

    def get_status(self):
        """Get current WiFi status."""
        config = self.load_config() or {}
        return {
            "connected": self.connected,
            "ap_mode": self.ap_mode,
            "ip": self.ip_address,
            "ssid": self.sta.config("ssid") if self.connected else None,
            "rssi": self.sta.status("rssi") if self.connected else None,
            "static_ip": config.get("static_ip"),
            "subnet": config.get("subnet"),
            "gateway": config.get("gateway"),
            "dns": config.get("dns")
        }

    def set_static_ip(self, static_ip, subnet=None, gateway=None, dns=None):
        """Set static IP configuration (saves to config, takes effect on next connect)."""
        config = self.load_config() or {}
        ssid = config.get("ssid", "")
        password = config.get("password", "")
        self.save_config(ssid, password, static_ip, subnet, gateway, dns)
        print(f"Static IP configured: {static_ip}")
        return True

    def clear_static_ip(self):
        """Clear static IP configuration (use DHCP)."""
        config = self.load_config() or {}
        ssid = config.get("ssid", "")
        password = config.get("password", "")
        self.save_config(ssid, password)  # Save without static IP
        self.static_ip = None
        print("Static IP cleared, will use DHCP")
        return True

    def auto_connect(self):
        """
        Try to connect to saved network.
        Falls back to AP mode if connection fails.
        """
        if self.connect():
            return True
        else:
            self.start_ap()
            return False

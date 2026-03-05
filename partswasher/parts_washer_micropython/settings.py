"""
Parts Washer v2.0 - Settings Storage
Persistent configuration stored in flash
"""

import json


class Settings:
    """Persistent settings with defaults."""

    CONFIG_FILE = "/settings.json"

    # Default settings
    DEFAULTS = {
        # Timing (seconds)
        "wash_duration": 180,
        "rinse1_duration": 120,
        "rinse2_duration": 120,
        "spin_duration": 60,
        "heat_duration": 1200,
        "jitter_duration": 180,

        # Motor speeds (RPM)
        "clean_rpm": 850,
        "spin_rpm": 950,
        "heat_rpm": 250,
        "jitter_osc": 6.0,
        "jitter_degrees": 100,

        # Z-axis
        "z_speed_mm_s": 10.0,
        "z_max_travel": 100.0,

        # Auto cycle options
        "auto_wash_enabled": True,
        "auto_rinse1_enabled": True,
        "auto_rinse2_enabled": True,
        "auto_spin_enabled": True,
        "auto_heat_enabled": True,

        # WiFi
        "wifi_ssid": "",
        "wifi_password": "",
        "ap_ssid": "PartsWasher",
        "ap_password": "washparts",

        # Display
        "display_brightness": 255,
        "display_timeout": 0,  # 0 = never off

        # System
        "device_name": "Parts Washer",
        "sound_enabled": True,
        "sim_mode": False,
    }

    def __init__(self):
        self._settings = dict(self.DEFAULTS)
        self.load()

    def load(self):
        """Load settings from flash."""
        try:
            with open(self.CONFIG_FILE, "r") as f:
                saved = json.load(f)
                # Merge with defaults (in case new settings added)
                self._settings.update(saved)
                print("Settings loaded")
        except OSError:
            print("No settings file, using defaults")
        except Exception as e:
            print(f"Settings load error: {e}")

    def save(self):
        """Save settings to flash."""
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(self._settings, f)
            print("Settings saved")
            return True
        except Exception as e:
            print(f"Settings save error: {e}")
            return False

    def get(self, key, default=None):
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key, value):
        """Set a setting value (doesn't auto-save)."""
        if key in self.DEFAULTS:
            # Type coercion based on default type
            default_type = type(self.DEFAULTS[key])
            try:
                if default_type == bool:
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "on")
                    else:
                        value = bool(value)
                elif default_type == int:
                    value = int(float(value))
                elif default_type == float:
                    value = float(value)
                else:
                    value = str(value)
            except (ValueError, TypeError):
                return False

            self._settings[key] = value
            return True
        return False

    def get_all(self):
        """Get all settings as dict."""
        return dict(self._settings)

    def set_multiple(self, settings_dict):
        """Set multiple settings at once."""
        changed = False
        for key, value in settings_dict.items():
            if self.set(key, value):
                changed = True
        return changed

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self._settings = dict(self.DEFAULTS)
        self.save()

    def get_timing_ms(self, key):
        """Get timing setting in milliseconds."""
        return self.get(key, 0) * 1000

    def export_json(self):
        """Export settings as JSON string."""
        return json.dumps(self._settings)

    def import_json(self, json_str):
        """Import settings from JSON string."""
        try:
            data = json.loads(json_str)
            self.set_multiple(data)
            self.save()
            return True
        except:
            return False


# Global settings instance
settings = Settings()

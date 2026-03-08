"""
Parts Washer v2.0 - Main Application
3-Axis Automated Watchmaker's Parts Washer
ESP32-S3 with MicroPython + Web Interface
"""

import time
from machine import Pin, I2C, PWM
import uasyncio as asyncio
import gc

import config
from stepper import AgitationMotor, ZAxisMotor, RotationMotor
from ssd1306 import SSD1306_I2C
from wifi_manager import WiFiManager
from settings import settings
from webserver import WebServer


class PartsWasher:
    """Main Parts Washer Controller."""

    VERSION = "2.0"

    def __init__(self):
        print("Parts Washer v{} - Initializing...".format(self.VERSION))

        # Settings reference (persistent, web-configurable)
        self.settings = settings

        # Initialize motors
        self.agit_motor = AgitationMotor(
            config.PIN_AGIT_STEP,
            config.PIN_AGIT_DIR,
            config.PIN_AGIT_EN,
            config.AGIT_STEPS_PER_REV,
            invert=True  # TB6600: 5V on + side, GPIO on - side
        )

        self.z_motor = ZAxisMotor(
            config.PIN_Z_STEP,
            config.PIN_Z_DIR,
            config.PIN_Z_EN,
            config.Z_STEPS_PER_MM,
            config.Z_MAX_TRAVEL_MM
        )

        self.rot_motor = RotationMotor(
            config.PIN_ROT_STEP,
            config.PIN_ROT_DIR,
            config.PIN_ROT_EN,
            config.ROT_STEPS_PER_STATION,
            config.NUM_STATIONS
        )

        # Initialize limit switches
        self.z_top = Pin(config.PIN_Z_TOP, Pin.IN, Pin.PULL_UP)
        self.z_bottom = Pin(config.PIN_Z_BOTTOM, Pin.IN, Pin.PULL_UP)
        self.rot_home = Pin(config.PIN_ROT_HOME, Pin.IN, Pin.PULL_UP)

        # Initialize buttons
        self.btn_start = Pin(config.PIN_START, Pin.IN, Pin.PULL_UP)
        self.btn_mode = Pin(config.PIN_MODE, Pin.IN, Pin.PULL_UP)

        # Initialize heater relay
        self.heater = Pin(config.PIN_HEAT, Pin.OUT, value=0)  # Active HIGH, off

        # Initialize buzzer
        self.buzzer = PWM(Pin(config.PIN_BUZZER), freq=2000, duty=0)

        # Initialize display (with error handling for missing hardware)
        self.display = None
        try:
            self.i2c = I2C(0, sda=Pin(config.PIN_SDA), scl=Pin(config.PIN_SCL), freq=400000)
            devices = self.i2c.scan()
            print("I2C devices found:", [hex(d) for d in devices])
            if config.OLED_ADDR in devices:
                self.display = SSD1306_I2C(128, 64, self.i2c, config.OLED_ADDR)
                print("OLED display initialized")
            else:
                print("WARNING: OLED not found at address", hex(config.OLED_ADDR))
        except Exception as e:
            print("WARNING: I2C/Display init failed:", e)

        # State variables
        self.current_mode = config.MODE_AUTO
        self.current_station = config.STATION_WASH
        self.is_homed = False
        self.is_running = False
        self.auto_step = 0
        self.auto_running = False
        self.mode_start_time = 0

        # Button state
        self.last_start_state = True
        self.last_mode_state = True
        self.start_press_time = 0

        print("Initialization complete")
        self.beep(2)

    # ============== DISPLAY METHODS ==============

    def show_startup(self):
        """Display startup screen."""
        if not self.display:
            return
        self.display.fill(0)
        self.display.text("PARTS", 35, 5, 1)
        self.display.text("WASHER", 30, 20, 1)
        self.display.text("v{} ESP32-S3".format(self.VERSION), 15, 40, 1)
        self.display.text("MicroPython", 25, 52, 1)
        self.display.show()

    def show_home_prompt(self):
        """Display homing prompt."""
        if not self.display:
            return
        self.display.fill(0)
        self.display.text("PARTS WASHER v2.0", 0, 0, 1)
        self.display.text("----------------", 0, 10, 1)
        self.display.text("System not homed", 0, 25, 1)
        self.display.text("Press START to", 0, 40, 1)
        self.display.text("begin homing", 0, 50, 1)
        self.display.show()

    def show_status(self):
        """Display current status."""
        if not self.display:
            return
        self.display.fill(0)

        # Mode
        self.display.text("Mode: {}".format(config.MODE_NAMES[self.current_mode]), 0, 0, 1)

        # Station
        self.display.text("Stn: {}".format(config.STATION_NAMES[self.current_station]), 0, 10, 1)

        # Z position
        z_mm = self.z_motor.get_position_mm()
        self.display.text("Z: {:.1f}mm".format(z_mm), 0, 20, 1)

        # State
        if self.is_running:
            elapsed = (time.ticks_ms() - self.mode_start_time) // 1000
            mins = elapsed // 60
            secs = elapsed % 60
            self.display.text("RUNNING {:02d}:{:02d}".format(mins, secs), 0, 30, 1)
        else:
            self.display.text("READY", 0, 30, 1)

        # Auto cycle progress
        if self.current_mode == config.MODE_AUTO and self.is_running:
            self.display.text("Auto: Step {}/23".format(self.auto_step), 0, 40, 1)

        # Limits status
        z_status = "T" if self.z_top.value() else "-"
        z_status += "B" if self.z_bottom.value() else "-"
        r_status = "H" if self.rot_home.value() else "-"
        h_status = "ON" if self.heater.value() else "--"
        self.display.text("Z:{} R:{} H:{}".format(z_status, r_status, h_status), 0, 54, 1)

        self.display.show()

    def show_homing(self, axis):
        """Display homing progress."""
        if not self.display:
            return
        self.display.fill(0)
        self.display.text("HOMING...", 30, 10, 1)
        self.display.text(axis, 40, 30, 1)
        self.display.show()

    def show_error(self, message):
        """Display error message."""
        if not self.display:
            print("ERROR:", message)
            return
        self.display.fill(0)
        self.display.text("ERROR", 45, 5, 1)
        self.display.text("-" * 16, 0, 15, 1)

        # Word wrap message
        words = message.split()
        lines = []
        line = ""
        for word in words:
            if len(line + word) < 16:
                line += word + " "
            else:
                lines.append(line.strip())
                line = word + " "
        lines.append(line.strip())

        for i, line in enumerate(lines[:3]):
            self.display.text(line, 0, 25 + i * 10, 1)

        self.display.text("Press START", 20, 54, 1)
        self.display.show()

    # ============== SOUND METHODS ==============

    def beep(self, count=1, freq=2000, duration_ms=200):
        """Play beep sound."""
        for _ in range(count):
            self.buzzer.freq(freq)
            self.buzzer.duty(512)
            time.sleep_ms(duration_ms)
            self.buzzer.duty(0)
            time.sleep_ms(100)

    def fast_beep(self, count=1):
        """Play fast beep."""
        self.beep(count, 2500, 80)

    # ============== HOMING METHODS ==============

    def home_all(self):
        """Home all axes. In sim_mode, skip physical homing."""
        print("Starting homing sequence...")

        if self.settings.get('sim_mode'):
            print("SIM MODE: Skipping physical homing")
            self.z_motor.set_position(0)
            self.rot_motor.set_position(0)
            self.rot_motor.current_station = 0
            self.is_homed = True
            self.current_station = config.STATION_WASH
            self.beep(2)
            return True

        # Home Z-axis first (move up)
        self.show_homing("Z-Axis UP")
        if not self.home_z():
            print("Z-axis home failed - entering sim mode")
            self.z_motor.set_position(0)
            self.rot_motor.set_position(0)
            self.rot_motor.current_station = 0
            self.is_homed = True
            self.current_station = config.STATION_WASH
            self.settings.set('sim_mode', True)
            self.beep(2)
            return True

        # Home rotation
        self.show_homing("Rotation")
        if not self.home_rotation():
            print("Rotation home failed - entering sim mode")
            self.rot_motor.set_position(0)
            self.rot_motor.current_station = 0
            self.is_homed = True
            self.current_station = config.STATION_WASH
            self.settings.set('sim_mode', True)
            self.beep(2)
            return True

        self.is_homed = True
        self.current_station = config.STATION_WASH
        print("Homing complete")
        self.beep(2)
        return True

    def home_z(self):
        """Home Z-axis by moving up until limit switch."""
        print("Homing Z-axis...")
        return self.z_motor.home(self.z_top, direction=1)

    def home_rotation(self):
        """Home rotation platform."""
        print("Homing rotation...")
        return self.rot_motor.home(self.rot_home, direction=1)

    # ============== MOVEMENT METHODS ==============

    def lower_head(self):
        """Lower head into current station."""
        print("Lowering head...")
        self.z_motor.set_speed_rpm(300)
        self.z_motor.move_to_mm(self.settings.get('z_max_travel'))

    def raise_to_spin(self):
        """Raise head to spin position (above fluid, still in jar)."""
        print("Raising to spin position...")
        self.z_motor.set_speed_rpm(300)
        self.z_motor.move_to_mm(self.settings.get('z_pos_spin'))

    def raise_head(self):
        """Raise head to home (top, clears dividers)."""
        print("Raising head...")
        self.z_motor.set_speed_rpm(300)
        self.z_motor.move_to_mm(0)

    def go_to_station(self, station):
        """Move to specified station."""
        print("Moving to station: {}".format(config.STATION_NAMES[station]))
        self.rot_motor.set_speed_rpm(30)
        self.rot_motor.move_to_station(station)
        self.current_station = station

    # ============== AGITATION METHODS ==============

    def start_jitter(self):
        """Start jitter mode."""
        print("Starting JITTER mode")
        self.mode_start_time = time.ticks_ms()
        jitter_deg = self.settings.get('jitter_degrees')
        jitter_steps = int(jitter_deg / 360.0 * config.AGIT_STEPS_PER_REV)
        self.agit_motor.start_jitter(jitter_steps, self.settings.get('jitter_osc'))
        self.is_running = True

    def start_clean(self):
        """Start clean mode."""
        print("Starting CLEAN mode")
        self.mode_start_time = time.ticks_ms()
        self.agit_motor.start_continuous(self.settings.get('clean_rpm'), reverse_every_revs=60)
        self.is_running = True

    def start_spin(self):
        """Start spin dry mode."""
        print("Starting SPIN mode")
        self.mode_start_time = time.ticks_ms()
        self.agit_motor.start_spin(self.settings.get('spin_rpm'))
        self.is_running = True

    def start_heat(self):
        """Start heat mode with slow rotation. Only allowed at HEATER station."""
        if self.current_station != config.STATION_HEATER:
            print("SAFETY: Heater blocked - not at HEATER station (at {})".format(
                config.STATION_NAMES[self.current_station]))
            return
        print("Starting HEAT mode")
        self.mode_start_time = time.ticks_ms()
        self.heater.value(1)  # Turn on heater (active HIGH)
        self.agit_motor.start_spin(self.settings.get('heat_rpm'))
        self.is_running = True

    def stop_all(self):
        """Stop all motors and heater."""
        print("Stopping all")
        self.agit_motor.stop()
        self.agit_motor.disable()
        self.z_motor.stop()
        self.z_motor.disable()
        self.rot_motor.stop()
        self.rot_motor.disable()
        self.heater.value(0)  # Off
        self.is_running = False

    # ============== MODE DURATION CHECK ==============

    def get_mode_duration_ms(self):
        """Get target duration in ms for the current mode/station."""
        if self.current_mode == config.MODE_JITTER:
            return self.settings.get_timing_ms('wash_duration') // 2
        elif self.current_mode == config.MODE_CLEAN:
            if self.current_station == config.STATION_WASH:
                return self.settings.get_timing_ms('wash_duration') // 2
            elif self.current_station == config.STATION_RINSE2:
                return self.settings.get_timing_ms('rinse2_duration')
            else:
                return self.settings.get_timing_ms('rinse1_duration')
        elif self.current_mode == config.MODE_SPIN_DRY:
            return self.settings.get_timing_ms('spin_duration')
        elif self.current_mode == config.MODE_HEAT:
            return self.settings.get_timing_ms('heat_duration')
        return 0

    def check_mode_complete(self):
        """Check if current agitation mode is complete."""
        if not self.is_running:
            return False

        elapsed = time.ticks_ms() - self.mode_start_time
        duration = self.get_mode_duration_ms()

        if elapsed >= duration:
            self.stop_all()
            return True

        return False

    # ============== AUTO CYCLE ==============

    async def run_auto_cycle(self):
        """Run full automatic wash cycle."""
        print("Starting AUTO cycle")
        self.auto_running = True
        self.auto_step = 0

        steps = [
            # Wash station (steps 0-6)
            (self.lower_head, None),                      # 0  submerge
            (self.start_jitter, None),                    # 1  jitter wash
            (self.start_clean, None),                     # 2  clean wash
            (self.raise_to_spin, None),                   # 3  above fluid
            (self.start_spin, None),                      # 4  spin dry
            (self.raise_head, None),                      # 5  clear dividers
            (self.go_to_station, config.STATION_RINSE1),  # 6  rotate to rinse1

            # Rinse 1 (steps 7-12)
            (self.lower_head, None),                      # 7  submerge
            (self.start_clean, None),                     # 8  clean rinse
            (self.raise_to_spin, None),                   # 9  above fluid
            (self.start_spin, None),                      # 10 spin dry
            (self.raise_head, None),                      # 11 clear dividers
            (self.go_to_station, config.STATION_RINSE2),  # 12 rotate to rinse2

            # Rinse 2 (steps 13-18)
            (self.lower_head, None),                      # 13 submerge
            (self.start_clean, None),                     # 14 clean rinse
            (self.raise_to_spin, None),                   # 15 above fluid
            (self.start_spin, None),                      # 16 spin dry
            (self.raise_head, None),                      # 17 clear dividers
            (self.go_to_station, config.STATION_HEATER),  # 18 rotate to heater

            # Heat dry (steps 19-22)
            (self.lower_head, None),                      # 19 lower into heater
            (self.start_heat, None),                      # 20 heat dry
            (self.raise_head, None),                      # 21 clear dividers
            (self.go_to_station, config.STATION_WASH),    # 22 return home
        ]

        for i, (func, arg) in enumerate(steps):
            self.auto_step = i
            self.show_status()

            # Execute step
            if arg is not None:
                func(arg)
            else:
                func()

            # Wait for completion
            if func in (self.lower_head, self.raise_head, self.raise_to_spin):
                while self.z_motor.is_moving():
                    self.z_motor.update()
                    await asyncio.sleep_ms(1)

            elif func == self.go_to_station:
                while self.rot_motor.is_moving():
                    self.rot_motor.update()
                    await asyncio.sleep_ms(1)

            elif func in (self.start_jitter, self.start_clean, self.start_spin, self.start_heat):
                # Set current_mode so get_mode_duration_ms() returns correct duration
                mode_map = {
                    self.start_jitter: config.MODE_JITTER,
                    self.start_clean: config.MODE_CLEAN,
                    self.start_spin: config.MODE_SPIN_DRY,
                    self.start_heat: config.MODE_HEAT,
                }
                self.current_mode = mode_map[func]
                while not self.check_mode_complete():
                    self.agit_motor.update()
                    self.show_status()
                    await asyncio.sleep_ms(10)
                    # Check for abort
                    if not self.btn_start.value():
                        print("Auto cycle aborted")
                        self.stop_all()
                        self.auto_running = False
                        self.current_mode = config.MODE_AUTO
                        return
                self.current_mode = config.MODE_AUTO

        print("AUTO cycle complete!")
        self.stop_all()
        self.auto_running = False
        self.auto_step = 0
        self.current_mode = config.MODE_AUTO
        self.beep(4)

    # ============== BUTTON HANDLING ==============

    def check_buttons(self):
        """Check button states and handle presses."""
        start_state = self.btn_start.value()
        mode_state = self.btn_mode.value()

        # START button pressed
        if not start_state and self.last_start_state:
            self.start_press_time = time.ticks_ms()

        # START button released
        if start_state and not self.last_start_state:
            press_duration = time.ticks_ms() - self.start_press_time

            if press_duration > config.LONG_PRESS_MS:
                # Long press - emergency stop and re-home
                print("Long press - emergency stop")
                self.stop_all()
                self.is_homed = False
                self.beep(3)
            else:
                # Short press
                self.handle_start_press()

        # MODE button pressed
        if not mode_state and self.last_mode_state:
            if not self.is_running:
                self.current_mode = (self.current_mode + 1) % config.NUM_MODES
                print("Mode: {}".format(config.MODE_NAMES[self.current_mode]))

        self.last_start_state = start_state
        self.last_mode_state = mode_state

    def handle_start_press(self):
        """Handle START button short press."""
        if not self.is_homed:
            self.home_all()
        elif self.is_running:
            self.stop_all()
        else:
            self.start_current_mode()

    def start_current_mode(self):
        """Start the currently selected mode."""
        if self.current_mode == config.MODE_AUTO:
            if self.auto_running:
                print("Auto cycle already running")
                return
            asyncio.create_task(self.run_auto_cycle())
        elif self.current_mode == config.MODE_JITTER:
            self.start_jitter()
        elif self.current_mode == config.MODE_CLEAN:
            self.start_clean()
        elif self.current_mode == config.MODE_SPIN_DRY:
            self.start_spin()
        elif self.current_mode == config.MODE_HEAT:
            self.start_heat()
        elif self.current_mode == config.MODE_MANUAL_Z:
            # Toggle Z position
            if self.z_motor.get_position_mm() < self.settings.get('z_max_travel') / 2:
                self.lower_head()
            else:
                self.raise_head()
        elif self.current_mode == config.MODE_MANUAL_ROT:
            self.rot_motor.next_station()
            self.current_station = self.rot_motor.get_station()

    # ============== WEB API HELPER METHODS ==============

    def get_mode_name(self):
        """Get current mode name."""
        return config.MODE_NAMES[self.current_mode]

    def get_station_name(self):
        """Get current station name."""
        return config.STATION_NAMES[self.current_station]

    def set_mode(self, mode):
        """Set operating mode."""
        if 0 <= mode < config.NUM_MODES:
            self.current_mode = mode
            print(f"Mode set to: {config.MODE_NAMES[mode]}")

    def start_cycle(self):
        """Start the current mode (for web API)."""
        if not self.is_homed:
            print("Cannot start - not homed")
            return False
        if self.auto_running:
            print("Auto cycle already running")
            return False
        self.start_current_mode()
        return True

    def stop_cycle(self):
        """Stop current operation (for web API)."""
        self.stop_all()

    def move_to_station(self, station):
        """Move to station (for web API)."""
        if 0 <= station < config.NUM_STATIONS:
            self.go_to_station(station)

    def jog_z(self, mm):
        """Jog Z-axis by mm amount."""
        current = self.z_motor.get_position_mm()
        new_pos = max(0, min(config.Z_MAX_TRAVEL_MM, current + mm))
        self.z_motor.set_speed_rpm(300)
        self.z_motor.move_to_mm(new_pos)

    def move_z_to(self, mm):
        """Move Z-axis to absolute position in mm."""
        pos = max(0, min(config.Z_MAX_TRAVEL_MM, mm))
        self.z_motor.set_speed_rpm(300)
        self.z_motor.move_to_mm(pos)

    def set_heater(self, state):
        """Set heater state. Only allowed at HEATER station."""
        if state and self.current_station != config.STATION_HEATER:
            print("SAFETY: Heater blocked - not at HEATER station (at {})".format(
                config.STATION_NAMES[self.current_station]))
            return
        self.heater.value(1 if state else 0)
        print(f"Heater {'ON' if state else 'OFF'}")

    # ============== MAIN LOOP ==============

    async def run(self, wifi, webserver):
        """Main application loop."""
        self.show_startup()
        await asyncio.sleep(2)

        # Start web server
        await webserver.start()

        # Show IP address on display
        if self.display and wifi.ip_address:
            self.display.fill(0)
            self.display.text("WiFi Connected", 10, 10, 1)
            self.display.text(wifi.ip_address, 15, 30, 1)
            self.display.text("Open in browser", 10, 50, 1)
            self.display.show()
            await asyncio.sleep(3)

        # Auto-home on boot
        print("Auto-homing on boot...")
        self.show_homing("All Axes")
        self.home_all()

        while True:
            if self.agit_motor._thread_running:
                # Yield long to keep GIL free for stepper thread
                if self.is_running and not self.auto_running:
                    self.check_mode_complete()
                await asyncio.sleep_ms(500)
            else:
                self.check_buttons()
                self.z_motor.update()
                self.rot_motor.update()
                self.agit_motor.update()
                if self.is_running and not self.auto_running:
                    self.check_mode_complete()
                if self.is_homed:
                    self.show_status()
                await asyncio.sleep_ms(10)


# ============== ENTRY POINT ==============

def main():
    """Main entry point."""
    washer = PartsWasher()

    # Initialize WiFi
    print("Initializing WiFi...")
    wifi = WiFiManager()

    # Try to connect to saved network, fallback to AP mode
    if not wifi.auto_connect():
        print("WiFi not configured - AP mode active")
        if washer.display:
            washer.display.fill(0)
            washer.display.text("WiFi Setup", 25, 5, 1)
            washer.display.text("Connect to:", 20, 20, 1)
            washer.display.text(wifi.AP_SSID, 25, 32, 1)
            washer.display.text("Password:", 25, 44, 1)
            washer.display.text(wifi.AP_PASSWORD, 20, 56, 1)
            washer.display.show()

    # Initialize web server
    webserver = WebServer(washer, wifi, settings)

    try:
        asyncio.run(washer.run(wifi, webserver))
    except KeyboardInterrupt:
        print("Interrupted")
        washer.stop_all()


if __name__ == "__main__":
    main()

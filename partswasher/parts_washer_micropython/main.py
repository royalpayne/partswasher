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
        )
        self.agit_motor.set_ramp(
            self.settings.get('agit_ramp_hz'),
            self.settings.get('agit_ramp_ms'),
            self.settings.get('agit_ramp_min_hz')
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
        self.auto_sub_mode = None  # Sub-mode during auto cycle (JITTER, CLEAN, etc.)
        self.auto_start_time = 0
        self.moving_to_station = False
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

    def _apply_z_ramp(self):
        """Apply current Z-axis ramp settings."""
        self.z_motor.set_accel(
            self.settings.get('z_accel_steps'),
            self.settings.get('z_start_delay')
        )
        self.z_motor.set_ramp_interval(self.settings.get('z_ramp_interval'))

    def lower_head(self):
        """Lower head into current station."""
        print("Lowering head...")
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(self.settings.get('z_pos_wash'))

    def lower_to_heat(self):
        """Lower head to heater position (2cm above wash depth)."""
        heat_depth = max(0, self.settings.get('z_pos_wash') - 20.0)
        print("Lowering to heat position ({:.0f}mm)...".format(heat_depth))
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(heat_depth)

    def raise_to_spin(self):
        """Raise head to spin position (above fluid, still in jar)."""
        print("Raising to spin position...")
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(self.settings.get('z_pos_spin'))

    def raise_head(self):
        """Raise head to home (top, clears dividers)."""
        print("Raising head...")
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(self.settings.get('z_pos_home'))

    def go_to_station(self, station):
        """Move to specified station. Requires Z at home and stops agitator."""
        # Safety: Z must be at home (0) before rotating
        if not self.auto_running and self.z_motor.get_position_mm() > 1.0:
            print("SAFETY: Station change blocked - Z not at home ({:.1f}mm)".format(
                self.z_motor.get_position_mm()))
            return False
        self.heater.value(0)  # Always turn off heater when changing stations
        self.agit_motor.stop()  # Stop agitator during rotation
        self.agit_motor.disable()
        self.is_running = False
        print("Moving to station: {}".format(config.STATION_NAMES[station]))
        self.rot_motor.set_speed_hz(self.settings.get('rot_speed_hz'))
        self.rot_motor.move_to_station(station)
        self.current_station = station
        return True

    # ============== AGITATION METHODS ==============

    def _apply_agit_ramp(self):
        """Apply current ramp settings to agitation motor."""
        self.agit_motor.set_ramp(
            self.settings.get('agit_ramp_hz'),
            self.settings.get('agit_ramp_ms'),
            self.settings.get('agit_ramp_min_hz')
        )
        self.agit_motor.set_reverse_pause(
            self.settings.get('agit_rev_pause')
        )

    def _check_z_depth(self, min_depth=None):
        """Check Z is at required depth. Returns True if safe to agitate.
        min_depth: required Z position in mm. Defaults to z_pos_wash (full wash depth).
        """
        if self.auto_running:
            return True
        z_pos = self.z_motor.get_position_mm()
        if min_depth is None:
            min_depth = self.settings.get('z_pos_wash')
        if z_pos < min_depth - 1.0:
            print("SAFETY: Agitator blocked - Z too high ({:.1f}mm, need >={:.1f}mm)".format(
                z_pos, min_depth))
            return False
        return True

    def start_jitter(self):
        """Start jitter mode."""
        if not self._check_z_depth():
            return
        print("Starting JITTER mode")
        self._apply_agit_ramp()
        self.mode_start_time = time.ticks_ms()
        jitter_deg = self.settings.get('jitter_degrees')
        jitter_steps = int(jitter_deg / 360.0 * config.AGIT_STEPS_PER_REV)
        self.agit_motor.start_jitter(jitter_steps, self.settings.get('jitter_osc'))
        self.is_running = True

    def start_clean(self):
        """Start clean mode."""
        if not self._check_z_depth():
            return
        print("Starting CLEAN mode")
        self._apply_agit_ramp()
        self.mode_start_time = time.ticks_ms()
        self.agit_motor.start_continuous(self.settings.get('clean_rpm'), reverse_every_revs=60)
        self.is_running = True

    def start_spin(self):
        """Start spin dry mode."""
        if not self._check_z_depth(self.settings.get('z_pos_spin')):
            return
        print("Starting SPIN mode")
        self._apply_agit_ramp()
        self.mode_start_time = time.ticks_ms()
        self.agit_motor.start_spin(self.settings.get('spin_rpm'))
        self.is_running = True

    def start_heat(self):
        """Start heat mode with slow rotation. Only allowed at HEATER station."""
        if self.current_station != config.STATION_HEATER:
            print("SAFETY: Heater blocked - not at HEATER station (at {})".format(
                config.STATION_NAMES[self.current_station]))
            return
        heat_depth = self.settings.get('z_pos_wash') - 20.0  # 2cm above wash depth
        if not self._check_z_depth(max(0, heat_depth)):
            return
        print("Starting HEAT mode")
        self._apply_agit_ramp()
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
        self.auto_running = False

    # ============== MODE DURATION CHECK ==============

    def get_mode_duration_ms(self):
        """Get target duration in ms for the current mode/station."""
        # During auto cycle, use sub-mode for duration lookup
        mode = self.auto_sub_mode if self.auto_running and self.auto_sub_mode is not None else self.current_mode
        if mode == config.MODE_JITTER:
            return self.settings.get_timing_ms('wash_duration') // 2
        elif mode == config.MODE_CLEAN:
            if self.current_station == config.STATION_WASH:
                return self.settings.get_timing_ms('wash_duration') // 2
            elif self.current_station == config.STATION_RINSE2:
                return self.settings.get_timing_ms('rinse2_duration')
            else:
                return self.settings.get_timing_ms('rinse1_duration')
        elif mode == config.MODE_SPIN_DRY:
            return self.settings.get_timing_ms('spin_duration')
        elif mode == config.MODE_HEAT:
            return self.settings.get_timing_ms('heat_duration')
        return 0

    def check_mode_complete(self):
        """Check if current agitation mode is complete."""
        if not self.is_running:
            return False

        # Already ramping down - wait for it to finish
        if self.agit_motor.is_stopping():
            if not self.agit_motor.running:
                # Ramp-down finished
                self.agit_motor.disable()
                self.heater.value(0)
                self.is_running = False
                return True
            return False

        elapsed = time.ticks_ms() - self.mode_start_time
        duration = self.get_mode_duration_ms()

        if elapsed >= duration:
            check_mode = self.auto_sub_mode if self.auto_running and self.auto_sub_mode is not None else self.current_mode
            if check_mode in (config.MODE_SPIN_DRY, config.MODE_CLEAN):
                if not self.agit_motor.running:
                    # Ramp-down already completed (stop() cleared _stopping flag)
                    self.agit_motor.disable()
                    self.heater.value(0)
                    self.is_running = False
                    return True
                # Ramp down gracefully
                self.agit_motor.ramp_down()
                return False  # Not done yet, ramp-down in progress
            # Jitter/heat: stop immediately
            self.agit_motor.stop()
            self.agit_motor.disable()
            self.heater.value(0)
            self.is_running = False
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
            (self.lower_to_heat, None),                    # 19 lower to heat depth
            (self.start_heat, None),                      # 20 heat dry
            (self.raise_head, None),                      # 21 clear dividers
            (self.go_to_station, config.STATION_WASH),    # 22 return home
        ]

        for i, (func, arg) in enumerate(steps):
            self.auto_step = i
            print("AUTO step {}: {} z={:.1f}mm".format(i, func.__name__,
                  self.z_motor.get_position_mm()))
            self.show_status()

            # Execute step
            if arg is not None:
                func(arg)
            else:
                func()

            # Wait for completion
            if func in (self.lower_head, self.lower_to_heat, self.raise_head, self.raise_to_spin):
                while self.z_motor.is_moving():
                    self.z_motor.update()
                    await asyncio.sleep_ms(1)
                print("  Z move done: {:.1f}mm".format(self.z_motor.get_position_mm()))

            elif func == self.go_to_station:
                while self.rot_motor.is_moving():
                    self.rot_motor.update()
                    await asyncio.sleep_ms(1)
                print("  Station move done")

            elif func in (self.start_jitter, self.start_clean, self.start_spin, self.start_heat):
                # Set auto_sub_mode so get_mode_duration_ms() returns correct duration
                mode_map = {
                    self.start_jitter: config.MODE_JITTER,
                    self.start_clean: config.MODE_CLEAN,
                    self.start_spin: config.MODE_SPIN_DRY,
                    self.start_heat: config.MODE_HEAT,
                }
                self.auto_sub_mode = mode_map[func]
                print("  Sub-mode {} running, is_running={}".format(
                    config.MODE_NAMES[self.auto_sub_mode], self.is_running))
                while not self.check_mode_complete():
                    self.agit_motor.update()
                    self.show_status()
                    await asyncio.sleep_ms(10)
                    # Check for abort
                    if not self.btn_start.value():
                        print("Auto cycle aborted")
                        self.stop_all()
                        self.auto_sub_mode = None
                        return
                print("  Mode complete")
                self.auto_sub_mode = None

        print("AUTO cycle complete!")
        self.stop_all()
        self.auto_running = False
        self.auto_sub_mode = None
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

    async def _lower_then_start(self, mode, station=None):
        """Raise Z to home, rotate to station if needed, lower to depth, start mode."""
        # Raise Z to home first
        z_pos = self.z_motor.get_position_mm()
        if z_pos > 1.0:
            print("Raising Z to home before starting...")
            self._apply_z_ramp()
            self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
            self.z_motor.move_to_mm(self.settings.get('z_pos_home'))
            while self.z_motor.is_moving():
                self.z_motor.update()
                await asyncio.sleep_ms(1)

        # Rotate to station if specified and not already there
        if station is not None and station != self.current_station:
            print("Rotating to station {}...".format(config.STATION_NAMES[station]))
            self.go_to_station(station)
            while self.rot_motor.is_moving():
                self.rot_motor.update()
                await asyncio.sleep_ms(1)

        # Determine target depth
        if mode == config.MODE_SPIN_DRY:
            target_mm = self.settings.get('z_pos_spin')
        elif mode == config.MODE_HEAT:
            target_mm = max(0, self.settings.get('z_pos_wash') - 20.0)
        else:
            target_mm = self.settings.get('z_pos_wash')

        # Lower Z to target depth
        print("Lowering to {:.0f}mm for {}...".format(
            target_mm, config.MODE_NAMES[mode]))
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(target_mm)
        while self.z_motor.is_moving():
            self.z_motor.update()
            await asyncio.sleep_ms(1)

        # Start the mode (jitter only at wash station)
        if mode == config.MODE_JITTER and self.current_station != config.STATION_WASH:
            print("JITTER only at WASH station, running CLEAN instead")
            mode = config.MODE_CLEAN
        self.current_mode = mode
        if mode == config.MODE_JITTER:
            self.start_jitter()
        elif mode == config.MODE_CLEAN:
            self.start_clean()
        elif mode == config.MODE_SPIN_DRY:
            self.start_spin()
        elif mode == config.MODE_HEAT:
            self.start_heat()

    def start_current_mode(self):
        """Start the currently selected mode."""
        if self.moving_to_station:
            print("Wait - moving to station")
            return
        if self.current_mode == config.MODE_AUTO:
            if self.auto_running:
                print("Auto cycle already running")
                return
            asyncio.create_task(self.run_auto_cycle())
        elif self.current_mode in (config.MODE_JITTER, config.MODE_CLEAN,
                                    config.MODE_SPIN_DRY, config.MODE_HEAT):
            asyncio.create_task(self._lower_then_start(self.current_mode, self.current_station))
        elif self.current_mode == config.MODE_MANUAL_Z:
            # Toggle Z position
            if self.z_motor.get_position_mm() < self.settings.get('z_pos_wash') / 2:
                self.lower_head()
            else:
                self.raise_head()
        elif self.current_mode == config.MODE_MANUAL_ROT:
            if self.z_motor.get_position_mm() > 1.0:
                print("SAFETY: Rotate blocked - Z not at home ({:.1f}mm)".format(
                    self.z_motor.get_position_mm()))
                return
            self.agit_motor.stop()
            self.agit_motor.disable()
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

    async def restart_cycle(self):
        """Stop everything, return to start position, ready for new cycle."""
        print("Restarting - returning to home position...")
        self.stop_all()
        self.current_mode = config.MODE_AUTO
        self.auto_step = 0

        if not self.is_homed:
            print("Not homed, cannot restart")
            return

        # Raise head to top
        self.raise_head()
        while self.z_motor.is_moving():
            self.z_motor.update()
            await asyncio.sleep_ms(1)

        # Rotate to wash station
        self.go_to_station(config.STATION_WASH)
        while self.rot_motor.is_moving():
            self.rot_motor.update()
            await asyncio.sleep_ms(1)

        print("Restart complete - ready for new cycle")

    def select_station(self, station):
        """Select station: raise Z to home, rotate to station, auto-set mode."""
        if 0 <= station < config.NUM_STATIONS:
            if self.moving_to_station:
                print("Already moving to station, ignoring")
                return
            # Auto-set appropriate mode for station
            if station == config.STATION_WASH:
                self.current_mode = config.MODE_JITTER
            elif station == config.STATION_HEATER:
                self.current_mode = config.MODE_HEAT
            else:
                self.current_mode = config.MODE_CLEAN
            print("Station {} -> mode {}".format(
                config.STATION_NAMES[station], config.MODE_NAMES[self.current_mode]))
            asyncio.create_task(self._move_to_station(station))

    async def _move_to_station(self, station):
        """Stop everything, raise Z to home, then rotate to station."""
        self.moving_to_station = True

        # Stop any running mode first
        self.agit_motor.stop()
        self.agit_motor.disable()
        self.heater.value(0)
        self.is_running = False
        self.rot_motor.stop()
        self.rot_motor.disable()

        # Raise Z to home
        z_now = self.z_motor.get_position_mm()
        z_home = self.settings.get('z_pos_home')
        print("Raising Z: {:.1f}mm -> {:.1f}mm (running={})".format(
            z_now, z_home, self.z_motor.is_moving()))
        self.z_motor.stop()  # Stop any in-progress Z move
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(z_home)
        print("  Z move started: running={}, pos={}, target={}".format(
            self.z_motor.is_moving(), self.z_motor.position, self.z_motor.target))
        while self.z_motor.is_moving():
            self.z_motor.update()
            await asyncio.sleep_ms(1)
        print("  Z at home: {:.1f}mm".format(self.z_motor.get_position_mm()))

        # Rotate to station
        if station != self.current_station:
            print("Rotating to {}...".format(config.STATION_NAMES[station]))
            self.rot_motor.set_speed_hz(self.settings.get('rot_speed_hz'))
            self.rot_motor.move_to_station(station)
            self.current_station = station
            while self.rot_motor.is_moving():
                self.rot_motor.update()
                await asyncio.sleep_ms(1)
        else:
            self.current_station = station

        self.moving_to_station = False
        print("At station {}, ready".format(config.STATION_NAMES[station]))

    def jog_z(self, mm):
        """Jog Z-axis by mm amount."""
        current = self.z_motor.get_position_mm()
        new_pos = max(0, min(config.Z_MAX_TRAVEL_MM, current + mm))
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
        self.z_motor.move_to_mm(new_pos)

    def move_z_to(self, mm):
        """Move Z-axis to absolute position in mm."""
        pos = max(0, min(config.Z_MAX_TRAVEL_MM, mm))
        self._apply_z_ramp()
        self.z_motor.set_speed_rpm(self.settings.get('z_speed_rpm'))
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
            self.check_buttons()
            self.z_motor.update()
            self.rot_motor.update()
            self.agit_motor.update()
            if self.is_running and not self.auto_running:
                if self.check_mode_complete():
                    if self.current_mode == config.MODE_SPIN_DRY:
                        self.raise_head()
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

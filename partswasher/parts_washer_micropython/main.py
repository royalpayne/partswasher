"""
Parts Washer v2.0 - Main Application
3-Axis Automated Watchmaker's Parts Washer
ESP32-S3 with MicroPython
"""

import time
from machine import Pin, I2C, PWM
import asyncio

import config
from stepper import AgitationMotor, ZAxisMotor, RotationMotor
from ssd1306 import SSD1306_I2C


class PartsWasher:
    """Main Parts Washer Controller."""

    VERSION = "2.0"

    def __init__(self):
        print("Parts Washer v{} - Initializing...".format(self.VERSION))

        # Initialize motors
        self.agit_motor = AgitationMotor(
            config.PIN_AGIT_STEP,
            config.PIN_AGIT_DIR,
            config.PIN_AGIT_EN,
            config.AGIT_STEPS_PER_REV
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
        self.heater = Pin(config.PIN_HEAT, Pin.OUT, value=1)  # Active LOW, off

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
            self.display.text("Auto: Step {}/21".format(self.auto_step), 0, 40, 1)

        # Limits status
        z_status = "T" if not self.z_top.value() else "-"
        z_status += "B" if not self.z_bottom.value() else "-"
        r_status = "H" if not self.rot_home.value() else "-"
        h_status = "ON" if not self.heater.value() else "--"
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
        """Home all axes."""
        print("Starting homing sequence...")

        # Home Z-axis first (move up)
        self.show_homing("Z-Axis UP")
        if not self.home_z():
            self.show_error("Z-axis home failed")
            return False

        # Home rotation
        self.show_homing("Rotation")
        if not self.home_rotation():
            self.show_error("Rotation home failed")
            return False

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
        self.z_motor.set_speed_rpm(60)  # Slow for safety
        self.z_motor.move_to_mm(config.Z_MAX_TRAVEL_MM)

    def raise_head(self):
        """Raise head out of station."""
        print("Raising head...")
        self.z_motor.set_speed_rpm(60)
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
        self.agit_motor.start_jitter(config.JITTER_STEPS, config.JITTER_OSC)
        self.is_running = True

    def start_clean(self):
        """Start clean mode."""
        print("Starting CLEAN mode")
        self.mode_start_time = time.ticks_ms()
        self.agit_motor.start_continuous(config.CLEAN_RPM, reverse_every_revs=60)
        self.is_running = True

    def start_spin(self):
        """Start spin dry mode."""
        print("Starting SPIN mode")
        self.mode_start_time = time.ticks_ms()
        self.agit_motor.start_spin(config.SPIN_DRY_RPM)
        self.is_running = True

    def start_heat(self):
        """Start heat mode with slow rotation."""
        print("Starting HEAT mode")
        self.mode_start_time = time.ticks_ms()
        self.heater.value(0)  # Turn on heater (active LOW)
        self.agit_motor.start_spin(config.HEAT_RPM)
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
        self.heater.value(1)  # Off
        self.is_running = False

    # ============== MODE DURATION CHECK ==============

    def check_mode_complete(self):
        """Check if current agitation mode is complete."""
        if not self.is_running:
            return False

        elapsed = time.ticks_ms() - self.mode_start_time

        duration = 0
        if self.current_mode == config.MODE_JITTER:
            duration = config.JITTER_DURATION_MS
        elif self.current_mode == config.MODE_CLEAN:
            if self.current_station == config.STATION_WASH:
                duration = config.WASH_DURATION_MS
            else:
                duration = config.RINSE_DURATION_MS
        elif self.current_mode == config.MODE_SPIN_DRY:
            duration = config.SPIN_DURATION_MS
        elif self.current_mode == config.MODE_HEAT:
            duration = config.HEAT_DURATION_MS

        if elapsed >= duration:
            self.stop_all()
            return True

        return False

    # ============== AUTO CYCLE ==============

    async def run_auto_cycle(self):
        """Run full automatic wash cycle."""
        print("Starting AUTO cycle")
        self.auto_step = 0

        steps = [
            # Step 0-3: Wash station
            (self.go_to_station, config.STATION_WASH),
            (self.lower_head, None),
            (self.start_jitter, None),
            (self.start_clean, None),
            (self.raise_head, None),
            (self.start_spin, None),

            # Step 6-9: Rinse 1
            (self.go_to_station, config.STATION_RINSE1),
            (self.lower_head, None),
            (self.start_clean, None),
            (self.raise_head, None),
            (self.start_spin, None),

            # Step 11-14: Rinse 2
            (self.go_to_station, config.STATION_RINSE2),
            (self.lower_head, None),
            (self.start_clean, None),
            (self.raise_head, None),
            (self.start_spin, None),

            # Step 16-19: Heat dry
            (self.go_to_station, config.STATION_HEATER),
            (self.lower_head, None),
            (self.start_heat, None),
            (self.raise_head, None),

            # Step 20: Return home
            (self.go_to_station, config.STATION_WASH),
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
            if func in (self.lower_head, self.raise_head):
                while self.z_motor.is_moving():
                    self.z_motor.update()
                    await asyncio.sleep_ms(1)

            elif func == self.go_to_station:
                while self.rot_motor.is_moving():
                    self.rot_motor.update()
                    await asyncio.sleep_ms(1)

            elif func in (self.start_jitter, self.start_clean, self.start_spin, self.start_heat):
                while not self.check_mode_complete():
                    self.agit_motor.update()
                    self.show_status()
                    await asyncio.sleep_ms(10)

                    # Check for abort
                    if not self.btn_start.value():
                        print("Auto cycle aborted")
                        self.stop_all()
                        return

        print("AUTO cycle complete!")
        self.beep(4)
        self.auto_step = 0

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
            if self.z_motor.get_position_mm() < config.Z_MAX_TRAVEL_MM / 2:
                self.lower_head()
            else:
                self.raise_head()
        elif self.current_mode == config.MODE_MANUAL_ROT:
            self.rot_motor.next_station()
            self.current_station = self.rot_motor.get_station()

    # ============== MAIN LOOP ==============

    async def run(self):
        """Main application loop."""
        self.show_startup()
        await asyncio.sleep(2)

        self.show_home_prompt()

        while True:
            # Check buttons
            self.check_buttons()

            # Update motors
            self.z_motor.update()
            self.rot_motor.update()
            self.agit_motor.update()

            # Check mode completion
            if self.is_running and self.current_mode != config.MODE_AUTO:
                self.check_mode_complete()

            # Update display
            if self.is_homed:
                self.show_status()

            await asyncio.sleep_ms(10)


# ============== ENTRY POINT ==============

def main():
    """Main entry point."""
    washer = PartsWasher()

    try:
        asyncio.run(washer.run())
    except KeyboardInterrupt:
        print("Interrupted")
        washer.stop_all()


if __name__ == "__main__":
    main()

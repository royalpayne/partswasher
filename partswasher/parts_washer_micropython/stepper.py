"""
Parts Washer v2.0 - Stepper Motor Driver
Non-blocking stepper control using timer interrupts
"""

from machine import Pin, Timer
import time


class Stepper:
    """
    Non-blocking stepper motor controller.
    Uses a timer for step generation to avoid blocking the main loop.
    """

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_rev=200, name="Stepper"):
        self.step = Pin(step_pin, Pin.OUT, value=0)
        self.dir = Pin(dir_pin, Pin.OUT, value=0)
        self.en = Pin(en_pin, Pin.OUT, value=1)  # Disabled by default (active LOW)

        self.steps_per_rev = steps_per_rev
        self.name = name

        # Position tracking
        self.position = 0  # Current position in steps
        self.target = 0  # Target position in steps

        # Movement state
        self.running = False
        self.direction = 1  # 1 = forward, -1 = reverse

        # Speed settings
        self.step_delay_us = 500  # Microseconds between steps
        self.last_step_time = 0

        # Timer for non-blocking operation
        self.timer = None
        self._step_state = False

    def enable(self):
        """Enable the motor driver."""
        self.en.value(0)  # Active LOW

    def disable(self):
        """Disable the motor driver."""
        self.en.value(1)
        self.running = False

    def set_speed_rpm(self, rpm):
        """Set speed in RPM."""
        if rpm < 1:
            rpm = 1
        steps_per_sec = (rpm * self.steps_per_rev) / 60.0
        self.step_delay_us = int(1000000 / steps_per_sec)

    def set_speed_hz(self, hz):
        """Set speed in steps per second (Hz)."""
        if hz < 1:
            hz = 1
        self.step_delay_us = int(1000000 / hz)

    def move_to(self, target_steps):
        """
        Move to an absolute position (non-blocking).
        Call update() regularly to execute movement.
        """
        self.target = int(target_steps)
        if self.target != self.position:
            self.direction = 1 if self.target > self.position else -1
            self.dir.value(1 if self.direction > 0 else 0)
            self.enable()
            self.running = True
            self.last_step_time = time.ticks_us()

    def move_relative(self, steps):
        """Move relative to current position."""
        self.move_to(self.position + steps)

    def stop(self):
        """Stop movement immediately."""
        self.running = False
        self.target = self.position

    def update(self):
        """
        Update stepper - call this frequently in main loop.
        Catches up on missed steps if called infrequently.
        Returns True if still moving, False if complete.
        """
        if not self.running:
            return False

        if self.position == self.target:
            self.running = False
            return False

        now = time.ticks_us()
        elapsed = time.ticks_diff(now, self.last_step_time)
        if elapsed >= self.step_delay_us:
            # Calculate how many steps we should have taken
            steps_due = min(elapsed // self.step_delay_us, abs(self.target - self.position))
            for _ in range(steps_due):
                self._do_step()
            self.last_step_time = now

        return True

    def _do_step(self):
        """Execute one step pulse."""
        self.step.value(1)
        time.sleep_us(5)
        self.step.value(0)
        self.position += self.direction

    def is_moving(self):
        """Check if motor is currently moving."""
        return self.running

    def get_position(self):
        """Get current position in steps."""
        return self.position

    def set_position(self, pos):
        """Set current position (for homing)."""
        self.position = pos
        self.target = pos

    def wait_until_done(self):
        """Block until movement is complete."""
        while self.update():
            time.sleep_us(10)


class AgitationMotor(Stepper):
    """
    Specialized stepper for agitation (jitter/clean/spin modes).
    Supports continuous oscillation and direction changes.
    """

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_rev=400):
        super().__init__(step_pin, dir_pin, en_pin, steps_per_rev, "Agitation")

        # Jitter mode state
        self.jitter_steps = 0
        self.jitter_count = 0
        self.jitter_mode = False

        # Continuous mode
        self.continuous = False
        self.revolution_count = 0
        self.steps_this_rev = 0
        self.reverse_interval = 60  # Reverse every N revolutions

    def start_jitter(self, steps_per_osc, osc_per_sec):
        """Start jitter mode - rapid oscillation."""
        self.jitter_steps = steps_per_osc
        self.jitter_count = 0
        self.jitter_mode = True
        self.continuous = True

        # Calculate step frequency for desired oscillation rate
        steps_per_sec = osc_per_sec * 2 * steps_per_osc
        self.set_speed_hz(steps_per_sec)

        self.enable()
        self.running = True
        self.last_step_time = time.ticks_us()

    def start_continuous(self, rpm, reverse_every_revs=60):
        """Start continuous rotation with periodic reversal."""
        self.jitter_mode = False
        self.continuous = True
        self.reverse_interval = reverse_every_revs
        self.revolution_count = 0
        self.steps_this_rev = 0

        self.set_speed_rpm(rpm)
        self.enable()
        self.running = True
        self.direction = 1
        self.dir.value(1)
        self.last_step_time = time.ticks_us()

    def start_spin(self, rpm):
        """Start continuous spin in one direction."""
        self.jitter_mode = False
        self.continuous = True
        self.reverse_interval = 0  # Never reverse

        self.set_speed_rpm(rpm)
        self.enable()
        self.running = True
        self.direction = 1
        self.dir.value(1)
        self.last_step_time = time.ticks_us()

    def update(self):
        """Update agitation motor."""
        if not self.running:
            return False

        now = time.ticks_us()
        if time.ticks_diff(now, self.last_step_time) >= self.step_delay_us:
            self._do_step()
            self.last_step_time = now

            if self.jitter_mode:
                self.jitter_count += 1
                if self.jitter_count >= self.jitter_steps:
                    self.jitter_count = 0
                    self.direction *= -1
                    self.dir.value(1 if self.direction > 0 else 0)

            elif self.continuous and self.reverse_interval > 0:
                self.steps_this_rev += 1
                if self.steps_this_rev >= self.steps_per_rev:
                    self.steps_this_rev = 0
                    self.revolution_count += 1
                    if self.revolution_count >= self.reverse_interval:
                        self.revolution_count = 0
                        self.direction *= -1
                        self.dir.value(1 if self.direction > 0 else 0)

        return True

    def stop(self):
        """Stop agitation."""
        self.running = False
        self.continuous = False
        self.jitter_mode = False


class HomingMixin:
    """Mixin for homing functionality with limit switches."""

    def home(self, limit_pin, direction=1, fast_speed=1000, slow_speed=200, backoff_steps=100):
        """
        Home the axis using a limit switch.

        Args:
            limit_pin: Pin object for limit switch (active LOW)
            direction: 1 for positive, -1 for negative
            fast_speed: Fast approach speed (steps/sec)
            slow_speed: Slow final approach speed (steps/sec)
            backoff_steps: Steps to back off after hitting limit

        Returns:
            True if homing successful, False if failed
        """
        self.enable()
        time.sleep_ms(10)

        # Set direction
        self.dir.value(1 if direction > 0 else 0)

        # Fast approach until limit triggers
        self.set_speed_hz(fast_speed)
        max_steps = self.steps_per_rev * 10  # Safety limit
        steps = 0

        while limit_pin.value() == 1 and steps < max_steps:
            self._do_step()
            time.sleep_us(self.step_delay_us)
            steps += 1

        if steps >= max_steps:
            self.disable()
            return False

        # Back off
        self.dir.value(0 if direction > 0 else 1)
        for _ in range(backoff_steps):
            self._do_step()
            time.sleep_us(1000)

        # Slow approach
        self.dir.value(1 if direction > 0 else 0)
        self.set_speed_hz(slow_speed)

        while limit_pin.value() == 1:
            self._do_step()
            time.sleep_us(self.step_delay_us)

        # Set home position
        self.set_position(0)
        self.disable()
        return True


class ZAxisMotor(Stepper, HomingMixin):
    """Z-axis motor with homing support."""

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_mm=400, max_travel_mm=100):
        super().__init__(step_pin, dir_pin, en_pin, int(steps_per_mm * 8), "Z-Axis")
        self.steps_per_mm = steps_per_mm
        self.max_travel_mm = max_travel_mm
        self.max_steps = int(max_travel_mm * steps_per_mm)

    def move_to_mm(self, mm):
        """Move to position in millimeters."""
        mm = max(0, min(mm, self.max_travel_mm))
        steps = int(mm * self.steps_per_mm)
        self.move_to(steps)

    def get_position_mm(self):
        """Get current position in millimeters."""
        return self.position / self.steps_per_mm

    def get_target_mm(self):
        """Get target position in millimeters."""
        return self.target / self.steps_per_mm


class RotationMotor(Stepper, HomingMixin):
    """Rotation motor with station positioning."""

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_station, num_stations=4):
        total_steps = int(steps_per_station * num_stations)
        super().__init__(step_pin, dir_pin, en_pin, total_steps, "Rotation")
        self.steps_per_station = int(steps_per_station)
        self.num_stations = num_stations
        self.current_station = 0

    def move_to_station(self, station):
        """Move to a specific station (0-3)."""
        station = station % self.num_stations
        target_steps = station * self.steps_per_station
        self.move_to(target_steps)
        self.current_station = station

    def next_station(self):
        """Move to next station."""
        self.move_to_station((self.current_station + 1) % self.num_stations)

    def get_station(self):
        """Get current station number."""
        return self.current_station

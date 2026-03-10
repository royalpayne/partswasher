"""
Parts Washer v2.0 - Stepper Motor Driver
Non-blocking stepper control with PWM for agitation
"""

from machine import Pin, PWM, Timer
import time
import gc


class Stepper:
    """
    Non-blocking stepper motor controller.
    Call update() in main loop for position-based moves.
    """

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_rev=200, name="Stepper", invert=False):
        self.invert = invert  # True for TB6600 with 5V on + side, GPIO on - side
        if invert:
            self.step = Pin(step_pin, Pin.OPEN_DRAIN, value=1)
            self.dir = Pin(dir_pin, Pin.OPEN_DRAIN, value=1)
            self.en = Pin(en_pin, Pin.OPEN_DRAIN, value=0)  # Disabled by default
        else:
            self.step = Pin(step_pin, Pin.OUT, value=0)
            self.dir = Pin(dir_pin, Pin.OUT, value=0)
            self.en = Pin(en_pin, Pin.OUT, value=1)  # Disabled by default

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

        # Acceleration
        self._accel_steps = 0       # Steps to ramp over (0 = no accel)
        self._start_delay_us = 2000 # Starting delay (slow)
        self._steps_taken = 0       # Steps taken in current move

    def enable(self):
        """Enable the motor driver."""
        self.en.value(1 if self.invert else 0)

    def disable(self):
        """Disable the motor driver."""
        self.en.value(0 if self.invert else 1)
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

    def set_accel(self, accel_steps, start_delay_us=2000):
        """Set acceleration ramp. accel_steps=0 disables."""
        self._accel_steps = accel_steps
        self._start_delay_us = start_delay_us

    def _dir_value(self, val):
        """Set direction pin, respecting invert."""
        self.dir.value(val ^ self.invert)

    def move_to(self, target_steps):
        """
        Move to an absolute position (non-blocking).
        Call update() regularly to execute movement.
        """
        self.target = int(target_steps)
        if self.target != self.position:
            self._steps_taken = 0
            self._total_move_steps = abs(self.target - self.position)
            self.direction = 1 if self.target > self.position else -1
            self._dir_value(1 if self.direction > 0 else 0)
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

    def _get_delay(self):
        """Get current step delay with acceleration profile."""
        if self._accel_steps == 0:
            return self.step_delay_us
        remaining = abs(self.target - self.position)
        ramp_pos = min(self._steps_taken, remaining)
        if ramp_pos >= self._accel_steps:
            return self.step_delay_us
        # Integer-only interpolation (no float division)
        delta = self._start_delay_us - self.step_delay_us
        return self._start_delay_us - (delta * ramp_pos // self._accel_steps)

    def update(self):
        """
        Update stepper - call this frequently in main loop.
        Executes all overdue steps in a burst for smooth motion.
        Returns True if still moving, False if complete.
        """
        if not self.running:
            return False

        if self.position == self.target:
            self.running = False
            return False

        now = time.ticks_us()
        elapsed = time.ticks_diff(now, self.last_step_time)
        delay = self._get_delay()

        while elapsed >= delay and self.position != self.target:
            self._do_step()
            self._steps_taken += 1
            elapsed -= delay
            delay = self._get_delay()

        self.last_step_time = time.ticks_us()
        return self.position != self.target

    def _do_step(self):
        """Execute one step pulse."""
        if self.invert:
            self.step.value(0)
            time.sleep_us(20)
            self.step.value(1)
        else:
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
    Uses hardware PWM for step generation via NPN transistor.
    Direction changes handled by Timer callback for jitter,
    or by update() polling for continuous reversal.
    """

    RAMP_STEP_HZ = 200     # Hz increment per ramp step (default)
    RAMP_INTERVAL_MS = 15   # ms between ramp steps (default)
    RAMP_MIN_HZ = 100       # Minimum frequency before cutting PWM

    def set_ramp(self, step_hz, interval_ms, min_hz=None):
        """Set ramp parameters. Lower step_hz or higher interval_ms = gentler ramp."""
        self.RAMP_STEP_HZ = max(1, step_hz)
        self.RAMP_INTERVAL_MS = max(1, interval_ms)
        if min_hz is not None:
            self.RAMP_MIN_HZ = max(1, min_hz)

    def set_reverse_pause(self, pause_ms):
        """Set pause duration (ms) between direction changes."""
        self.reverse_pause_ms = max(0, pause_ms)

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_rev=400, timer_id=0):
        # NPN transistor: always use Pin.OUT (push-pull), no invert
        super().__init__(step_pin, dir_pin, en_pin, steps_per_rev, "Agitation", invert=False)

        self._step_pin_num = step_pin

        # PWM state
        self._pwm = None
        self._pwm_running = False
        self._target_freq = 0
        self._current_freq = 0

        # Jitter mode state
        self.jitter_steps = 0
        self.jitter_mode = False
        self._jitter_timer = Timer(timer_id)
        self._jitter_timer_running = False

        # Continuous mode
        self.continuous = False
        self.revolution_count = 0
        self.steps_this_rev = 0
        self.reverse_interval = 60

        # Ramp state
        self._ramping = False
        self._last_ramp_time = 0
        self._reversing = False
        self._cruise_freq = 0  # Target freq to resume after reversal
        self._pausing = False
        self._pause_start = 0
        self.reverse_pause_ms = 500  # Pause duration between direction changes
        self._stopping = False  # Ramp-down to stop

    def _start_pwm(self, target_freq):
        """Start PWM with ramp-up from current speed."""
        self._target_freq = max(1, target_freq)
        if not self._pwm_running:
            self._current_freq = max(1, min(self.RAMP_MIN_HZ, self._target_freq))
            self._pwm = PWM(Pin(self._step_pin_num, Pin.OUT), freq=self._current_freq, duty=512)
            self._pwm_running = True
        self._ramping = self._current_freq != self._target_freq
        self._last_ramp_time = time.ticks_ms()

    def _stop_pwm(self):
        """Stop PWM output."""
        if self._pwm_running:
            self._pwm.deinit()
            self._pwm = None
            self._pwm_running = False
            # Re-init step pin as output LOW
            self.step = Pin(self._step_pin_num, Pin.OUT, value=0)
        self._current_freq = 0
        self._ramping = False

    def _update_ramp(self):
        """Ramp PWM frequency toward target. Call from update()."""
        # Handle pause between direction changes
        if self._pausing:
            if time.ticks_diff(time.ticks_ms(), self._pause_start) >= self.reverse_pause_ms:
                # Pause complete: flip direction, ramp back up
                self._pausing = False
                self.direction *= -1
                self.dir.value(1 if self.direction > 0 else 0)
                self._target_freq = self._cruise_freq
                self._start_pwm(self._cruise_freq)
            return

        if not self._ramping or not self._pwm_running:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_ramp_time) < self.RAMP_INTERVAL_MS:
            return
        self._last_ramp_time = now

        if self._current_freq < self._target_freq:
            self._current_freq = min(self._current_freq + self.RAMP_STEP_HZ, self._target_freq)
        elif self._current_freq > self._target_freq:
            self._current_freq = max(self._current_freq - self.RAMP_STEP_HZ, self._target_freq)

        self._pwm.freq(self._current_freq)
        if self._current_freq == self._target_freq:
            if self._stopping:
                # Ramp-down complete: full stop
                self._stopping = False
                self.stop()
            elif self._reversing:
                # Ramp-down complete: stop PWM, enter pause
                self._reversing = False
                self._stop_pwm()
                self._pausing = True
                self._pause_start = time.ticks_ms()
            else:
                self._ramping = False

    def ramp_down(self):
        """Initiate ramp-down to stop. Returns immediately; poll is_stopping()."""
        if not self._pwm_running:
            self.stop()
            return
        self._stopping = True
        self._target_freq = max(1, min(self.RAMP_MIN_HZ, self._current_freq))
        self._ramping = True
        self._last_ramp_time = time.ticks_ms()

    def is_stopping(self):
        """True if currently ramping down to stop."""
        return self._stopping

    def _start_reversal(self):
        """Initiate a ramp-down, direction change, ramp-up sequence."""
        self._reversing = True
        self._cruise_freq = self._target_freq
        # Ramp down to minimum speed before flipping
        self._target_freq = max(1, min(self.RAMP_MIN_HZ, self._cruise_freq))
        self._ramping = True
        self._last_ramp_time = time.ticks_ms()

    def _jitter_callback(self, t):
        """Timer callback for jitter direction changes."""
        if not self.running or not self.jitter_mode:
            return
        self.direction *= -1
        self.dir.value(1 if self.direction > 0 else 0)

    def start_jitter(self, steps_per_osc, osc_per_sec):
        """Start jitter mode - rapid oscillation using PWM + timer for direction."""
        self.jitter_steps = steps_per_osc
        self.jitter_mode = True
        self.continuous = True

        steps_per_sec = int(osc_per_sec * 2 * steps_per_osc)
        osc_period_ms = int(1000 / (osc_per_sec * 2))

        self.enable()
        self.running = True
        self.direction = 1
        self.dir.value(1)

        self._start_pwm(steps_per_sec)

        # Timer for direction changes
        if self._jitter_timer_running:
            self._jitter_timer.deinit()
        self._jitter_timer.init(period=osc_period_ms, mode=Timer.PERIODIC,
                                callback=self._jitter_callback)
        self._jitter_timer_running = True

    def start_continuous(self, rpm, reverse_every_revs=60):
        """Start continuous rotation with periodic reversal."""
        self.jitter_mode = False
        self.continuous = True
        self.reverse_interval = reverse_every_revs
        self.revolution_count = 0
        self.steps_this_rev = 0

        freq = max(1, int(rpm * self.steps_per_rev / 60))
        self.enable()
        self.running = True
        self.direction = 1
        self.dir.value(1)
        self._start_pwm(freq)

    def start_spin(self, rpm):
        """Start continuous spin in one direction."""
        self.jitter_mode = False
        self.continuous = True
        self.reverse_interval = 0

        freq = max(1, int(rpm * self.steps_per_rev / 60))
        self.enable()
        self.running = True
        self.direction = 1
        self.dir.value(1)
        self._start_pwm(freq)

    def update(self):
        """Handle ramp and direction reversals. Returns True if running."""
        if not self.running:
            return False
        self._update_ramp()

        # Track revolutions for continuous reversal (approximate from freq)
        if self.continuous and self.reverse_interval > 0 and not self.jitter_mode:
            if self._pwm_running and self._current_freq > 0:
                now = time.ticks_ms()
                if not hasattr(self, '_last_rev_check'):
                    self._last_rev_check = now
                    self._step_accumulator = 0
                elapsed = time.ticks_diff(now, self._last_rev_check)
                if elapsed >= 100:  # Check every 100ms
                    self._step_accumulator += self._current_freq * elapsed // 1000
                    self._last_rev_check = now
                    if self._step_accumulator >= self.steps_per_rev:
                        revs = self._step_accumulator // self.steps_per_rev
                        self._step_accumulator %= self.steps_per_rev
                        self.revolution_count += revs
                        if self.revolution_count >= self.reverse_interval:
                            self.revolution_count = 0
                            if not self._reversing:
                                self._start_reversal()

        return True

    def stop(self):
        """Stop agitation."""
        if self._jitter_timer_running:
            self._jitter_timer.deinit()
            self._jitter_timer_running = False
        self._stop_pwm()
        self.running = False
        self.continuous = False
        self.jitter_mode = False
        self._stopping = False
        self._reversing = False
        self._pausing = False


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
        self._dir_value(1 if direction > 0 else 0)

        # Fast approach until limit triggers
        # NC switches: closed (LOW) = not at limit, open (HIGH) = at limit
        self.set_speed_hz(fast_speed)
        max_steps = self.steps_per_rev * 10  # Safety limit
        steps = 0

        while limit_pin.value() == 0 and steps < max_steps:
            self._do_step()
            time.sleep_us(self.step_delay_us)
            steps += 1

        if steps >= max_steps:
            self.disable()
            return False

        # Back off
        self._dir_value(0 if direction > 0 else 1)
        for _ in range(backoff_steps):
            self._do_step()
            time.sleep_us(1000)

        # Slow approach
        self._dir_value(1 if direction > 0 else 0)
        self.set_speed_hz(slow_speed)

        while limit_pin.value() == 0:
            self._do_step()
            time.sleep_us(self.step_delay_us)

        # Set home position
        self.set_position(0)
        self.disable()
        return True


class ZAxisMotor(Stepper, HomingMixin):
    """Z-axis motor with hardware PWM stepping and acceleration ramp.

    PWM generates step pulses in hardware (smooth, jitter-free).
    Disables motor briefly before direction changes to release holding torque.
    """

    RAMP_START_HZ = 200     # Starting frequency (gentle start)
    RAMP_STEP_HZ = 100      # Hz increase per ramp step
    RAMP_INTERVAL_MS = 15   # ms between ramp steps

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_mm=400, max_travel_mm=100, timer_id=1):
        super().__init__(step_pin, dir_pin, en_pin, int(steps_per_mm * 8), "Z-Axis")
        self.steps_per_mm = steps_per_mm
        self.max_travel_mm = max_travel_mm
        self.max_steps = int(max_travel_mm * steps_per_mm)
        self._step_pin_num = step_pin
        self._pwm = None
        self._pwm_running = False
        self._move_steps = 0
        self._target_freq = 0
        self._current_freq = 0
        self._ramping = False
        self._last_ramp_time = 0
        self._steps_counted = 0
        self._step_remainder = 0
        self._last_count_time = 0
        self._move_start_pos = 0

    def set_ramp_interval(self, interval):
        """No-op for compatibility."""
        pass

    def _stop_pwm(self):
        """Stop PWM and restore step pin as output."""
        if self._pwm_running:
            self._pwm.deinit()
            self._pwm = None
            self._pwm_running = False
            self.step = Pin(self._step_pin_num, Pin.OUT, value=0)

    def _update_position(self):
        """Accumulate steps based on current frequency and elapsed time."""
        if not self._pwm_running:
            return
        now = time.ticks_ms()
        elapsed_ms = time.ticks_diff(now, self._last_count_time)
        if elapsed_ms > 0:
            total = self._current_freq * elapsed_ms + self._step_remainder
            steps = total // 1000
            self._step_remainder = total % 1000
            self._steps_counted += steps
            if self._steps_counted > self._move_steps:
                self._steps_counted = self._move_steps
            self.position = self._move_start_pos + self._steps_counted * self.direction
            self._last_count_time = now

    def _update_ramp(self):
        """Ramp PWM frequency toward target."""
        if not self._ramping or not self._pwm_running:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_ramp_time) < self.RAMP_INTERVAL_MS:
            return
        self._last_ramp_time = now
        if self._current_freq < self._target_freq:
            self._current_freq = min(self._current_freq + self.RAMP_STEP_HZ, self._target_freq)
            self._pwm.freq(self._current_freq)
            if self._current_freq >= self._target_freq:
                self._ramping = False

    def move_to(self, target_steps):
        """Start hardware PWM-driven move to absolute position with ramp."""
        target_steps = int(target_steps)
        if target_steps == self.position:
            return
        if self._pwm_running:
            self._stop_pwm()

        self.target = target_steps
        self._move_start_pos = self.position
        self._move_steps = abs(self.target - self.position)
        self._steps_counted = 0
        self._step_remainder = 0
        self.direction = 1 if self.target > self.position else -1
        self._dir_value(1 if self.direction > 0 else 0)
        self.enable()
        time.sleep_ms(5)
        self.running = True

        self._target_freq = max(1, 1000000 // max(1, self.step_delay_us))
        self._current_freq = min(self.RAMP_START_HZ, self._target_freq)
        self._ramping = self._current_freq < self._target_freq
        self._last_ramp_time = time.ticks_ms()
        self._last_count_time = time.ticks_ms()

        # Start PWM at ramp start speed, 50% duty for reliable step detection
        self._pwm = PWM(Pin(self._step_pin_num, Pin.OUT), freq=self._current_freq, duty=512)
        self._pwm_running = True

    def stop(self):
        """Stop movement immediately."""
        if self._pwm_running:
            self._update_position()
            self._stop_pwm()
        self.running = False
        self._ramping = False
        self.target = self.position

    def update(self):
        """Ramp speed and check if PWM move is complete."""
        if not self.running:
            return False
        if not self._pwm_running:
            return False
        self._update_ramp()
        self._update_position()
        if self._steps_counted >= self._move_steps:
            self._stop_pwm()
            self.position = self.target
            self.running = False
            return False
        return True

    def wait_until_done(self):
        """Block until movement is complete."""
        while self.running:
            self.update()
            time.sleep_ms(10)

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
    """Rotation motor with hardware PWM stepping.

    PWM generates step pulses in hardware (zero CPU/ISR overhead).
    Position is estimated from elapsed time and step frequency.
    """

    def __init__(self, step_pin, dir_pin, en_pin, steps_per_station, num_stations=4, timer_id=2):
        total_steps = int(steps_per_station * num_stations)
        super().__init__(step_pin, dir_pin, en_pin, total_steps, "Rotation")
        self.steps_per_station = int(steps_per_station)
        self.num_stations = num_stations
        self.current_station = 0
        self._step_pin_num = step_pin
        self._pwm = None
        self._pwm_running = False
        self._move_start_time = 0
        self._move_start_pos = 0
        self._move_steps = 0
        self._step_freq = 0

    def _stop_pwm(self):
        """Stop PWM and restore step pin as output."""
        if self._pwm_running:
            self._pwm.deinit()
            self._pwm = None
            self._pwm_running = False
            self.step = Pin(self._step_pin_num, Pin.OUT, value=0)

    def _update_position(self):
        """Estimate position from elapsed time and step frequency."""
        if not self._pwm_running:
            return
        elapsed_ms = time.ticks_diff(time.ticks_ms(), self._move_start_time)
        steps_done = min(self._move_steps, self._step_freq * elapsed_ms // 1000)
        self.position = self._move_start_pos + steps_done * self.direction

    def move_to(self, target_steps):
        """Start hardware PWM-driven move to absolute position."""
        target_steps = int(target_steps)
        if target_steps == self.position:
            return
        if self._pwm_running:
            self._stop_pwm()

        self.target = target_steps
        self._move_start_pos = self.position
        self._move_steps = abs(self.target - self.position)
        self.direction = 1 if self.target > self.position else -1
        self._dir_value(1 if self.direction > 0 else 0)
        self.enable()
        self.running = True

        self._step_freq = max(1, 1000000 // max(1, self.step_delay_us))
        self._move_start_time = time.ticks_ms()

        # Hardware PWM - pulses generated with zero CPU overhead
        self._pwm = PWM(Pin(self._step_pin_num, Pin.OUT), freq=self._step_freq, duty=51)
        self._pwm_running = True

    def stop(self):
        """Stop movement immediately."""
        if self._pwm_running:
            self._update_position()
            self._stop_pwm()
        self.running = False
        self.target = self.position

    def update(self):
        """Check if PWM move is complete. Call regularly from main loop."""
        if not self.running:
            return False
        if not self._pwm_running:
            return False
        self._update_position()
        if abs(self.position - self.target) <= 1:
            self._stop_pwm()
            self.position = self.target
            self.running = False
            return False
        return True

    def wait_until_done(self):
        """Block until movement is complete."""
        while self.running:
            time.sleep_ms(10)

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

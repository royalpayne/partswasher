# Parts Washer MicroPython - Project Guide

## What This Is
3-axis automated watchmaker's parts washer running MicroPython on an ESP32-S3. Controls three stepper motors (agitation via TB6600, Z-axis + rotation via TMC2209) to cycle parts through 4 stations: Wash, Rinse 1, Rinse 2, Heat Dry. Includes a web interface for remote control and an OLED display for local status.

## Architecture

| File | Purpose |
|------|---------|
| `main.py` | `PartsWasher` class - main controller, state machine, button handling, auto-cycle orchestration |
| `config.py` | Pin assignments (ESP32-S3), hardware motor parameters, mode/station enums (defaults only; runtime values come from settings) |
| `stepper.py` | Non-blocking stepper motor classes: AgitationMotor (PWM+ramp), ZAxisMotor (PWM position), RotationMotor (PWM position), HomingMixin |
| `webserver.py` | Async HTTP server (`uasyncio`) with REST API + embedded single-page HTML/CSS/JS UI |
| `wifi_manager.py` | WiFi STA/AP management, static IP support, credential persistence to `/wifi_config.json` |
| `settings.py` | JSON-backed persistent settings with type coercion, stored at `/settings.json` |
| `ssd1306.py` | SSD1306 128x64 OLED I2C driver (standard MicroPython framebuf-based) |
| `upload.sh` | Deployment script using `mpremote` over `/dev/ttyACM0` |

## Hardware
- **MCU:** ESP32-S3-N16R8 (16MB flash, 8MB PSRAM), 44-pin board
- **Agitation:** NEMA23 (57HBC027Y-21B0805) + TB6600 driver, 2/B half-step (400 steps/rev)
  - **Inverted wiring:** 5V (external USB charger) on PUL+/DIR+, ESP32 GPIO on PUL-/DIR-, ENA disconnected
  - Pins use `Pin.OPEN_DRAIN` mode (3.3V GPIO cannot drive TB6600 optocouplers directly)
  - DIP switches for 2/B: SW1=OFF, SW2=ON, SW3=ON
  - Uses hardware PWM via NPN transistor for step generation (duty=512, 50%)
  - Software ramp-up/ramp-down for smooth speed transitions and graceful stops
- **Z-Axis:** NEMA17 + TMC2209, 1/16 microstep (3200 steps/rev), hardware PWM stepping (duty=51, ~5%)
- **Rotation:** NEMA17 + TMC2209, 1/16 microstep (3200 steps/rev), hardware PWM stepping (duty=51, ~5%)
- **Z-axis mechanism:** Cable winch — NEMA17 drives a cable spool (20mm core dia, 32mm flange) with 625ZZ bearing support. ~62.83mm cable per motor rev. 206mm travel (92mm lowered to 298mm raised). Braided steel wire cable runs alongside center tube to head anchor. See `3d_models/assembly_view.scad` for full mechanical design.
- **Rotation mechanism:** Belt-driven 4-station carousel (3:1 gear ratio), home limit switch
- **Peripherals:** 128x64 I2C OLED (0x3C, optional), piezo buzzer (PWM), heater relay (active HIGH), start/mode buttons (active LOW, pull-up)
- **5V source:** ESP32-S3 5V pin only outputs ~1.5V; use external USB charger for TB6600 signal voltage

## 3D Printed Parts
4 custom parts (see `3d_models/`): motor mount (plug + platform + walls + bearing boss), cable spool, cable anchor (on washer head), motor cover. Hardware: NEMA17, 625ZZ bearing, ~400mm braided steel wire.

## Key Patterns

### Motor Control
All three motors use **hardware PWM** for step pulse generation (zero CPU/ISR overhead):
- **AgitationMotor**: PWM at 50% duty via NPN transistor to TB6600. Software ramp-up/ramp-down via `_update_ramp()` polling. Supports jitter (Timer callback for direction changes), continuous rotation with periodic reversal, and spin modes. Graceful stop via `ramp_down()`.
- **ZAxisMotor**: PWM at 5% duty direct to TMC2209. Position estimated from elapsed time × frequency. Max error: 1 step (~0.02mm). `update()` checks completion.
- **RotationMotor**: Same PWM approach as ZAxisMotor. Position estimated from elapsed time.

Call `motor.move_to()` to start, `motor.update()` in main loop to check completion.

### Homing
`HomingMixin` provides a two-pass homing sequence: fast approach to limit switch, back off, then slow approach for precision. Used by `ZAxisMotor` and `RotationMotor`.

### Async Architecture
The main loop and web server both run on `uasyncio`. The main loop polls buttons, updates motors, checks mode timers, and refreshes the OLED at ~100Hz. The auto-cycle runs as an async task with `await asyncio.sleep_ms()` yield points.

### Web API Endpoints
- `GET /` - Embedded HTML UI
- `GET /api/status` - Machine state (mode, station, running, heater, limits, wifi)
- `GET /api/settings` / `POST /api/settings` - Read/write persistent settings
- `POST /api/control` - Actions: start, stop, home, mode, station, z_up, z_down, z_move_to, heater, beep
- `GET /api/wifi/scan` / `POST /api/wifi/connect` / `GET /api/wifi/status` / `POST /api/wifi/static`

### Settings
`settings.py` provides a singleton `Settings` instance with defaults. Values are type-coerced to match default types. `main.py` reads operational parameters (durations, RPM speeds, Z travel, jitter settings) from `self.settings` at runtime, so changes made via the web UI take effect immediately. Hardware constants (pin assignments, steps-per-rev, gear ratios) remain in `config.py`.

## Simulation Mode
Set `sim_mode: true` in settings (via web UI or `/settings.json`) to test without hardware. Skips physical homing (sets positions to 0, marks homed), so the auto cycle can run. Motors still pulse GPIO internally — movements complete at configured speeds but with no physical effect. Shorten durations via settings for faster testing.

## Build & Deploy
```bash
# Upload all files to ESP32-S3 via USB
./upload.sh

# Or manually with mpremote
mpremote connect /dev/ttyACM0 fs cp main.py :main.py

# Run without flashing
mpremote connect /dev/ttyACM0 run main.py
```

## Conventions
- MicroPython subset of Python 3 (no typing, limited stdlib)
- Pin logic: TMC2209 enable = active LOW, TB6600 ENA disconnected (always enabled), limit switches = NC (LOW=not triggered, HIGH=triggered), heater relay = active HIGH
- TB6600 step pulse: hardware PWM 50% duty via NPN transistor, TMC2209: hardware PWM 5% duty direct GPIO
- Display updates are guarded by `if not self.display: return` for headless operation
- WiFi falls back to AP mode ("PartsWasher" / "washparts") if no saved credentials
- All HTTP responses include `Access-Control-Allow-Origin: *` for CORS
- Embedded HTML/CSS/JS in `webserver.py` (no separate static files on flash)

## Modes
| # | Name | Description |
|---|------|-------------|
| 0 | JITTER | Rapid oscillation (default 100 deg, 6 osc/sec) |
| 1 | CLEAN | Continuous rotation (default 200 RPM*), reverses every 60 revs |
| 2 | SPIN | Spin dry (default 200 RPM*, 1 min) |
| 3 | HEAT | Heater ON + slow rotation (default 250 RPM, 20 min) |
| 4 | AUTO | Full 23-step cycle through all stations |
| 5 | Z-AXIS | Manual Z toggle (up/down) |
| 6 | ROTATE | Manual advance to next station |

## Auto Cycle Sequence (23 steps)
1. WASH: Lower -> Jitter (wash_duration/2) -> Clean (wash_duration/2) -> Raise to spin -> Spin dry -> Raise head -> Rotate to RINSE1
2. RINSE1: Lower -> Clean (rinse1_duration) -> Raise to spin -> Spin dry -> Raise head -> Rotate to RINSE2
3. RINSE2: Lower -> Clean (rinse2_duration) -> Raise to spin -> Spin dry -> Raise head -> Rotate to HEATER
4. HEATER: Lower to heat depth -> Heat (heat_duration) -> Raise head -> Rotate to WASH

## Z-Axis Positions
- **Home (0mm)**: Top, clears station dividers for rotation
- **Spin (`z_pos_spin`)**: Above fluid level for centrifugal drying (default 40mm)
- **Heat (`z_max_travel - 20mm`)**: 2cm above full depth to prevent overheating basket
- **Wash (`z_max_travel`)**: Bottom, fully submerged (default 100mm)

## Safety Interlocks
- **Station change**: Blocked unless Z is at home (<1mm) — prevents carousel rotation while basket is lowered
- **Agitation start**: Jitter/Clean/Heat require Z at full wash depth (`z_max_travel`); Spin requires Z at spin depth (`z_pos_spin`)
- **Heater**: Only allowed at HEATER station; auto-off when changing stations; Z depth at `z_max_travel - 20mm`
- **Station change stops agitator**: Agitation motor stopped and disabled before any rotation
- **Auto cycle bypass**: Safety checks skip depth validation during auto cycle (`auto_running` flag) since the cycle manages Z positioning
- Double-start protection: `start_current_mode()` and `start_cycle()` reject if `auto_running` is already True
- Homing auto-fallback: if physical homing fails, enters sim mode automatically

"""
Parts Washer v2.0 - Configuration
ESP32-S3 Pin Definitions and Settings
"""

# ============== PIN DEFINITIONS (ESP32-S3) ==============

# Agitation Motor (TB6600 External)
PIN_AGIT_STEP = 4
PIN_AGIT_DIR = 5
PIN_AGIT_EN = 6

# Z-Axis Motor (TMC2209 On-PCB)
PIN_Z_STEP = 35
PIN_Z_DIR = 36
PIN_Z_EN = 37

# Rotation Motor (TMC2209 On-PCB)
PIN_ROT_STEP = 38
PIN_ROT_DIR = 39
PIN_ROT_EN = 40

# Limit Switches (active LOW - NC switches)
PIN_Z_TOP = 41
PIN_Z_BOTTOM = 42
PIN_ROT_HOME = 2

# Interface
PIN_START = 7
PIN_MODE = 15
PIN_BUZZER = 16
PIN_HEAT = 17

# I2C for OLED
PIN_SDA = 8
PIN_SCL = 9
OLED_ADDR = 0x3C

# ============== MOTOR CONFIGURATION ==============

# Agitation Motor (NEMA23 + TB6600 half-step)
AGIT_MICROSTEPS = 2
AGIT_STEPS_PER_REV = 200 * AGIT_MICROSTEPS  # 400 steps/rev

# Z-Axis Motor (NEMA17 + TMC2209 16x microstepping)
Z_MICROSTEPS = 16
Z_STEPS_PER_REV = 200 * Z_MICROSTEPS  # 3200 steps/rev
Z_LEAD_MM = 8.0  # 8mm lead screw pitch (T8)
Z_STEPS_PER_MM = Z_STEPS_PER_REV / Z_LEAD_MM  # 400 steps/mm
Z_MAX_TRAVEL_MM = 100.0  # Maximum Z travel in mm
Z_SPEED_MM_S = 10.0  # Z movement speed mm/s

# Rotation Motor (NEMA17 + TMC2209 16x microstepping)
ROT_MICROSTEPS = 16
ROT_STEPS_PER_REV = 200 * ROT_MICROSTEPS  # 3200 steps/rev
ROT_GEAR_RATIO = 3.0  # Belt reduction ratio
ROT_STEPS_PER_PLAT_REV = ROT_STEPS_PER_REV * ROT_GEAR_RATIO
ROT_STEPS_PER_STATION = ROT_STEPS_PER_PLAT_REV / 4  # 90 degrees

# ============== STATION DEFINITIONS ==============
STATION_WASH = 0
STATION_RINSE1 = 1
STATION_RINSE2 = 2
STATION_HEATER = 3
NUM_STATIONS = 4

STATION_NAMES = ["WASH", "RINSE1", "RINSE2", "HEATER"]

# ============== MODE DEFINITIONS ==============
MODE_JITTER = 0
MODE_CLEAN = 1
MODE_SPIN_DRY = 2
MODE_HEAT = 3
MODE_AUTO = 4
MODE_MANUAL_Z = 5
MODE_MANUAL_ROT = 6
NUM_MODES = 7

MODE_NAMES = ["JITTER", "CLEAN", "SPIN", "HEAT", "AUTO", "Z-AXIS", "ROTATE"]

# ============== TIMING SETTINGS (milliseconds) ==============
WASH_DURATION_MS = 180000  # 3 minutes
RINSE_DURATION_MS = 120000  # 2 minutes
SPIN_DURATION_MS = 60000  # 1 minute
HEAT_DURATION_MS = 1200000  # 20 minutes
JITTER_DURATION_MS = 180000  # 3 minutes

# ============== AGITATION SETTINGS ==============
CLEAN_RPM = 850.0
SPIN_DRY_RPM = 950.0
HEAT_RPM = 250.0
JITTER_OSC = 6.0  # Oscillations per second
JITTER_DEGREES = 100.0
JITTER_STEPS = int(JITTER_DEGREES / 360.0 * AGIT_STEPS_PER_REV)

# ============== DEBOUNCE ==============
DEBOUNCE_MS = 50
LONG_PRESS_MS = 1000

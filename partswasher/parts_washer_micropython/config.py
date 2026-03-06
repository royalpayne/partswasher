"""
Parts Washer v2.0 - Configuration
ESP32-S3 Pin Definitions and Settings
"""

# ============== PIN DEFINITIONS (ESP32-S3-N16R8) ==============
# GPIOs 26-37 reserved for flash/PSRAM, 19-20 for USB
# Grouped for consolidated wiring harnesses

# I2C for OLED (2 pins)
PIN_SDA = 1
PIN_SCL = 2
OLED_ADDR = 0x3C

# Agitation Motor - TB6600 (3 pins)
PIN_AGIT_STEP = 4
PIN_AGIT_DIR = 5
PIN_AGIT_EN = 6

# Z-Axis Motor - TMC2209 (3 pins)
PIN_Z_STEP = 7
PIN_Z_DIR = 8
PIN_Z_EN = 9

# Rotation Motor - TMC2209 (3 pins)
PIN_ROT_STEP = 10
PIN_ROT_DIR = 11
PIN_ROT_EN = 12

# Limit Switches - active LOW, NC (3 pins)
PIN_Z_TOP = 13
PIN_Z_BOTTOM = 14
PIN_ROT_HOME = 15

# Interface (4 pins)
PIN_START = 38
PIN_MODE = 17
PIN_BUZZER = 18
PIN_HEAT = 21

# ============== MOTOR CONFIGURATION ==============

# Agitation Motor (NEMA23 + TB6600 2/B half-stepping)
AGIT_MICROSTEPS = 2
AGIT_STEPS_PER_REV = 200 * AGIT_MICROSTEPS  # 400 steps/rev

# Z-Axis Motor (NEMA17 + TMC2209 16x microstepping + cable winch)
Z_MICROSTEPS = 16
Z_STEPS_PER_REV = 200 * Z_MICROSTEPS  # 3200 steps/rev
Z_SPOOL_CORE_DIA = 20.0  # Cable spool core diameter (mm)
Z_MM_PER_REV = 3.14159 * Z_SPOOL_CORE_DIA  # ~62.83mm per rev
Z_STEPS_PER_MM = Z_STEPS_PER_REV / Z_MM_PER_REV  # ~50.93 steps/mm
Z_MAX_TRAVEL_MM = 206.0  # Maximum Z travel in mm (298 - 92 from assembly)
Z_SPEED_MM_S = 30.0  # Z movement speed mm/s

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

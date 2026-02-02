# EasyEDA Build Guide - Parts Washer Controller

## Quick Start

1. Go to https://easyeda.com
2. Create account or sign in
3. File -> New -> Project -> "PartsWasher_Controller"
4. File -> New -> Schematic

## Component Placement (Search by LCSC#)

### Power Section
| Ref | LCSC# | Description |
|-----|-------|-------------|
| J1 | C8465 | 24V Power Input (2P terminal) |
| F1 | C89657 | 5A PTC Fuse |
| D1 | C123799 | SMBJ26A TVS Diode |
| U1 | C14259 | MP1584EN 5V Buck |
| L1 | C341017 | 33uH Inductor |
| D2 | C8678 | SS34 Schottky |
| C1 | C249473 | 470uF/35V Electrolytic |
| C2 | C72505 | 100uF/10V Electrolytic |
| U2 | C6186 | AMS1117-3.3 LDO |
| C3 | C15850 | 10uF Ceramic |
| C4 | C45783 | 22uF Ceramic |

### Main Controller
| Ref | LCSC# | Description |
|-----|-------|-------------|
| U3 | C2913202 | ESP32-S3-WROOM-1-N16R8 |
| J2 | C165948 | USB-C Connector |
| Q1, Q2 | C2146 | S8050 NPN (auto-reset) |

### Motor Drivers (x3)
| Ref | LCSC# | Description |
|-----|-------|-------------|
| U5, U6, U7 | C80539 | TMC2209 |
| R3, R4, R5 | C25092 | 0.11R Sense Resistors |
| C9, C12, C15 | C249474 | 100uF/35V VMOT caps |
| C7-C14 | C14663 | 100nF Bypass caps |

### Connectors
| Ref | LCSC# | Description |
|-----|-------|-------------|
| J3, J4, J5, J12 | C144394 | JST-XH 4P (Motors, OLED) |
| J6, J7, J8 | C144395 | JST-XH 3P (Limit switches) |
| J9, J10, J13 | C144396 | JST-XH 2P (Buttons, Fan) |
| J11 | C8466 | 3P Terminal (Heater relay) |

### Relay & Buzzer
| Ref | LCSC# | Description |
|-----|-------|-------------|
| K1 | C35449 | SRD-05VDC-SL-C Relay |
| Q3, Q4 | C2146 | S8050 NPN drivers |
| D4 | C64898 | 1N4007 Flyback |
| BZ1 | C96256 | Passive Buzzer |

### Resistors (all 0603)
| Ref | LCSC# | Value |
|-----|-------|-------|
| R1, R2, R6-R8 | C25804 | 10K |
| R11-R13, R16-R18 | C21190 | 1K |
| R14, R15 | C23162 | 4.7K |

### LEDs (all 0805)
| Ref | LCSC# | Color |
|-----|-------|-------|
| LED1 | C84256 | Red (Relay) |
| LED2 | C72043 | Green (Power) |
| LED3 | C72041 | Blue (3.3V) |
| LED4 | C72038 | Yellow (Motor) |

---

## Wiring Connections

### ESP32-S3 to TMC2209 Drivers

```
GPIO4  -> U5.STEP  (Agitation)
GPIO5  -> U5.DIR
GPIO6  -> U5.ENN

GPIO35 -> U6.STEP  (Z-Axis)
GPIO36 -> U6.DIR
GPIO37 -> U6.ENN

GPIO38 -> U7.STEP  (Rotation)
GPIO39 -> U7.DIR
GPIO40 -> U7.ENN
```

### TMC2209 Microstepping Config

```
U5 (Agitation): MS1=GND, MS2=GND  -> 1/8 step (1600 steps/rev)
U6 (Z-Axis):    MS1=VCC, MS2=GND  -> 1/16 step (3200 steps/rev)
U7 (Rotation):  MS1=VCC, MS2=GND  -> 1/16 step (3200 steps/rev)
```

### Limit Switches & Buttons

```
GPIO41 -> J6.2 (Z-Top)    + R6 pullup to 3V3
GPIO42 -> J7.2 (Z-Bottom) + R7 pullup to 3V3
GPIO2  -> J8.2 (Rot Home) + R8 pullup to 3V3
GPIO7  -> J9.2 (Start)    internal pullup
GPIO15 -> J10.2 (Mode)    internal pullup
```

### I2C (OLED Display)

```
GPIO8 (SDA) -> J12.4 + R14 pullup to 3V3
GPIO9 (SCL) -> J12.3 + R15 pullup to 3V3
J12.1 -> GND
J12.2 -> 3V3
```

### Buzzer Circuit

```
GPIO16 -> R11 (1K) -> Q3.base
Q3.collector -> BZ1.-
Q3.emitter -> GND
BZ1.+ -> +5V
```

### Heater Relay Circuit

```
GPIO17 -> R12 (1K) -> Q4.base
Q4.collector -> K1.coil-
Q4.emitter -> GND
K1.coil+ -> +5V
D4 across K1 coil (flyback)
K1.COM -> J11.1
K1.NO  -> J11.2
K1.NC  -> J11.3
```

### USB-C Native

```
GPIO19 -> J2.D-
GPIO20 -> J2.D+
CC1, CC2 -> 5.1K to GND each
```

---

## Power Rails

```
+24V: J1.1 -> F1 -> TVS -> Motor drivers (VM pins)
+5V:  MP1584 output -> Relay, Buzzer, LEDs, USB
+3V3: AMS1117 output -> ESP32, TMC2209 logic, pullups
GND:  Common ground for all
```

---

## After Schematic Complete

1. Run ERC check (Design -> Design Manager -> ERC)
2. Fix any errors
3. Design -> Convert to PCB
4. Set board: 100mm x 80mm, 4 layers
5. Reference pcb_layout.svg for placement
6. Route with trace widths:
   - Signal: 0.25mm
   - 3V3: 0.5mm
   - 5V: 0.75mm
   - 24V/Motors: 1.0mm+
7. Add ground pours
8. Generate Gerbers -> Order at JLCPCB

// Parts Washer - Rotation Motor Bracket (Barrel-Conforming Saddle)
// Curved saddle wraps barrel exterior, motor platform extends outward
// Pancake NEMA17 drives GT2 belt around carousel belt race
//
// Two-piece design:
//   1. Saddle bracket — curved to match barrel OD (150mm radius),
//      bolts through barrel wall, motor platform extends outward
//   2. Motor plate — NEMA17 bolt pattern, slides on platform for
//      belt tension adjustment via M5 slotted bolts
//
// Print: saddle with flat back on bed (curved face up)
//   or on side with supports for curved surface
// Material: PETG or ABS

$fn = 80;

// === Barrel geometry (must match base_bottom.scad) ===
barrel_r = 150;               // barrel outer radius (300mm OD / 2)
barrel_wall = 2;              // barrel wall thickness

// === NEMA17 pancake motor dimensions ===
n17_face = 42.3;              // motor face square
n17_body_len = 24;            // pancake body length
n17_bolt_spacing = 31;        // bolt pattern center-to-center
n17_bolt_d = 3.2;             // M3 clearance
n17_pilot_d = 22;             // front pilot/register diameter
n17_pilot_h = 2;              // pilot protrusion

// === Saddle dimensions ===
saddle_arc = 60;              // degrees of barrel circumference
saddle_height = 65;           // vertical height of saddle
saddle_thick = 4;             // wall thickness of saddle shell
saddle_inner_r = barrel_r;    // matches barrel OD

// === Motor platform (extends outward from saddle) ===
platform_length = 70;         // radial extent outward from barrel surface
platform_width = 55;          // tangential width (matches motor + margins)
platform_thick = 5;           // platform thickness
platform_z_offset = 5;        // platform height above saddle bottom

// === Tension adjustment ===
slot_length = 20;             // radial travel range
slot_width = 5.5;             // M5 clearance slot width
slot_spacing = 48;            // between slot centers (flanking motor)
slot_start = 15;              // slot start from platform inner edge

// === M5 clamping bolts ===
m5_bolt_d = 5.5;              // M5 clearance
m5_head_d = 8.5;              // M5 socket head
m5_head_h = 5;                // socket head height
m5_nut_w = 8;                 // M5 nut across flats
m5_nut_h = 4;                 // M5 nut height

// === Barrel mounting (through barrel wall) ===
m4_bolt_d = 4.2;              // M4 clearance
m4_head_d = 7.5;              // M4 socket head
m4_head_h = 4;                // socket head depth
mount_cols = 2;               // 2 columns of bolts
mount_rows = 2;               // 2 rows of bolts
mount_col_spacing = 40;       // vertical spacing
mount_row_angle = 30;         // angular spacing (degrees on barrel)

// === Motor plate ===
motor_plate_width = n17_face + 10;   // 52.3mm
motor_plate_length = n17_face + 10;  // 52.3mm
motor_plate_thick = 5;
motor_cx = motor_plate_length / 2;
motor_cy = motor_plate_width / 2;

// === Gusset ribs ===
gusset_thick = 4;
gusset_height = 40;           // triangular support height

// ==========================================
// SADDLE BRACKET — curved shell + outward platform
// ==========================================
module saddle_bracket() {
    difference() {
        union() {
            // --- Curved saddle shell (wraps barrel exterior) ---
            // Arc centered at origin, saddle_arc degrees
            rotate([0, 0, -saddle_arc/2])
            difference() {
                // Outer shell
                rotate_extrude(angle=saddle_arc, $fn=120)
                translate([saddle_inner_r, 0, 0])
                    square([saddle_thick, saddle_height]);
                // (solid saddle, no inner cut needed — it sits ON the barrel)
            }

            // --- Motor platform (flat shelf extending outward) ---
            // Platform extends radially from barrel surface
            // Centered at 0° (middle of saddle arc)
            translate([saddle_inner_r, -platform_width/2, platform_z_offset])
                cube([platform_length, platform_width, platform_thick]);

            // --- Gusset ribs (triangular supports, platform to saddle) ---
            for (side = [-1, 1])
            translate([0, 0, platform_z_offset])
            hull() {
                // At saddle surface
                translate([saddle_inner_r, side * (platform_width/2 - gusset_thick/2), 0])
                    cube([saddle_thick, gusset_thick, gusset_height]);
                // At platform outer edge
                translate([saddle_inner_r + platform_length - 10,
                           side * (platform_width/2 - gusset_thick/2), 0])
                    cube([10, gusset_thick, platform_thick]);
            }
        }

        // --- Tension adjustment slots (in platform) ---
        for (side = [-1, 1])
            translate([saddle_inner_r + slot_start,
                       side * slot_spacing/2,
                       platform_z_offset - 0.1])
            hull() {
                cylinder(d=slot_width, h=platform_thick + 0.2);
                translate([slot_length, 0, 0])
                    cylinder(d=slot_width, h=platform_thick + 0.2);
            }

        // --- M5 nut traps on underside of platform ---
        for (side = [-1, 1])
            translate([saddle_inner_r + slot_start + slot_length/2,
                       side * slot_spacing/2,
                       platform_z_offset])
            hull() {
                cylinder(d=m5_nut_w, h=m5_nut_h, $fn=6);
                translate([slot_length/2, 0, 0])
                    cylinder(d=m5_nut_w, h=m5_nut_h, $fn=6);
                translate([-slot_length/2, 0, 0])
                    cylinder(d=m5_nut_w, h=m5_nut_h, $fn=6);
            }

        // --- M4 barrel mounting bolt holes (through saddle into barrel wall) ---
        for (row = [-1, 1])
            for (col = [-1, 1])
                rotate([0, 0, row * mount_row_angle/2])
                translate([0, 0, saddle_height/2 + col * mount_col_spacing/2]) {
                    // Bolt hole (radial, through saddle shell)
                    translate([saddle_inner_r - 0.1, 0, 0])
                        rotate([0, 90, 0])
                        cylinder(d=m4_bolt_d, h=saddle_thick + 0.2);
                    // Socket head counterbore (from outside)
                    translate([saddle_inner_r + saddle_thick - m4_head_h, 0, 0])
                        rotate([0, 90, 0])
                        cylinder(d=m4_head_d, h=m4_head_h + 0.1);
                }
    }
}

// ==========================================
// MOTOR PLATE — holds NEMA17, slides on platform
// ==========================================
module motor_plate() {
    difference() {
        cube([motor_plate_length, motor_plate_width, motor_plate_thick]);

        // NEMA17 bolt holes (4 corners of 31mm square pattern)
        for (dx = [-1, 1])
            for (dy = [-1, 1])
                translate([motor_cx + dx * n17_bolt_spacing/2,
                           motor_cy + dy * n17_bolt_spacing/2,
                           -0.1])
                    cylinder(d=n17_bolt_d, h=motor_plate_thick + 0.2);

        // NEMA17 pilot clearance hole (center)
        translate([motor_cx, motor_cy, -0.1])
            cylinder(d=n17_pilot_d + 1, h=motor_plate_thick + 0.2);

        // M5 clamping bolt holes (match slot positions on platform)
        for (side = [-1, 1])
            translate([motor_plate_length/2,
                       motor_cy + side * slot_spacing/2,
                       -0.1])
                cylinder(d=m5_bolt_d, h=motor_plate_thick + 0.2);

        // M5 head counterbore (from top, so bolt heads are flush)
        for (side = [-1, 1])
            translate([motor_plate_length/2,
                       motor_cy + side * slot_spacing/2,
                       motor_plate_thick - m5_head_h])
                cylinder(d=m5_head_d, h=m5_head_h + 0.1);
    }
}

// ==========================================
// DISPLAY — assembled view
// ==========================================

// Barrel reference (transparent cylinder for context)
%cylinder(r=barrel_r, h=saddle_height + 20);

// Saddle bracket
color([0.6, 0.6, 0.65])
saddle_bracket();

// Motor plate (on platform, at mid-travel)
_mp_x = saddle_inner_r + slot_start + slot_length/2 - motor_plate_length/2;
_mp_y = -motor_plate_width/2;
_mp_z = platform_z_offset + platform_thick;
color([0.3, 0.7, 0.9])
translate([_mp_x, _mp_y, _mp_z])
    motor_plate();

// NEMA17 motor reference (on top of motor plate)
color([0.15, 0.15, 0.15])
translate([_mp_x + motor_cx, _mp_y + motor_cy, _mp_z + motor_plate_thick]) {
    // Pilot boss
    cylinder(d=n17_pilot_d, h=n17_pilot_h);
    // Motor body
    translate([-n17_face/2, -n17_face/2, n17_pilot_h])
        cube([n17_face, n17_face, n17_body_len]);
}

// Motor shaft (extends down through bracket)
color("Silver")
translate([_mp_x + motor_cx, _mp_y + motor_cy, _mp_z + motor_plate_thick - 24])
    cylinder(d=5, h=24);

// ==========================================
// PRINT LAYOUT (offset to the right)
// ==========================================
translate([barrel_r * 2 + 40, 0, 0]) {
    // Saddle bracket — printed curved-side up, flat back on bed
    // Rotate so the inner (barrel-contact) surface faces down
    color([0.6, 0.6, 0.65])
    translate([0, 0, saddle_inner_r + saddle_thick])
    rotate([0, 90, 0])
    rotate([0, 0, saddle_arc/2])  // center the arc
    saddle_bracket();

    // Motor plate — flat on bed, offset
    translate([saddle_height + 20, 0, 0])
    color([0.3, 0.7, 0.9])
    motor_plate();
}

// =====================================================================
// PRINT & ASSEMBLY INSTRUCTIONS
// =====================================================================
//
// WHAT THIS PART DOES:
//   Barrel-conforming saddle bracket for the carousel rotation motor.
//   The curved saddle wraps 60° of the barrel exterior (150mm radius)
//   and bolts through the barrel wall. A flat motor platform extends
//   radially outward with slotted M5 tension adjustment. A pancake
//   NEMA17 with GT2 pulley drives the belt around the carousel race.
//
// TENSION ADJUSTMENT:
//   1. Loosen the 2x M5 clamping bolts.
//   2. Slide motor plate outward (away from barrel) to tension belt.
//   3. Retighten M5 bolts.
//   Slot provides 20mm of travel range.
//
// PRINT SETTINGS:
//   Saddle bracket:
//     Orientation: On its side — inner curve down, platform pointing up
//                  (or flat back on bed with supports for curved surface)
//     Material:    PETG or ABS (needs rigidity)
//     Infill:      80%
//     Layer height: 0.2mm
//     Supports:    YES (for curved saddle surface if printing upright)
//     Walls:       4 perimeters
//   Motor plate:
//     Orientation: Flat on bed
//     Supports:    NO
//
// HARDWARE:
//   - 4x M4 × 12mm socket head bolts + nuts (saddle to barrel wall)
//   - 2x M5 × 25mm socket head bolts (tension clamping)
//   - 2x M5 nuts (in platform nut traps)
//   - 4x M3 × 8mm (motor to motor plate)
//   - 1x pancake NEMA17 stepper motor
//   - 1x GT2 20T pulley (5mm bore)
//
// ASSEMBLY:
//   1. Press M5 nuts into platform nut traps (hex traps hold them).
//   2. Position saddle bracket on barrel exterior, centered on the
//      belt slot opening. Drill 4x M4 holes through barrel wall.
//   3. Bolt saddle to barrel (4x M4 through wall, nuts inside).
//   4. Bolt NEMA17 to motor plate (4x M3), shaft pointing down
//      through the pilot hole.
//   5. Place motor plate on platform, insert 2x M5 bolts through
//      motor plate into platform slots.
//   6. Slide to desired belt tension, tighten M5 bolts.
//   7. Install GT2 pulley on motor shaft, align with belt race.
// =====================================================================

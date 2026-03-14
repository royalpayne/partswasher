// Parts Washer - Cable Anchor (Shift Cable Barrel End)
// Mounts on top of agitator sleeve via M3 heat-set inserts
// Shift cable barrel drops into pocket from top, cable exits bottom
//
// Uses universal shift cable: 4mm barrel, 4.5mm tall, 1.2mm wire
//
// Print: flat on bed (base flange down)
// Material: PETG or ABS
// Infill: 80%

$fn = 80;

// === Shift cable dimensions ===
cable_d = 1.2;               // shift cable wire diameter
barrel_d = 4.0;              // barrel/nipple diameter
barrel_h = 4.5;              // barrel height
barrel_clear = 0.3;          // fit clearance

// === Anchor body ===
boss_d = 12;                 // main boss diameter
boss_h = 8;                  // boss height above mounting surface

// === M3 mounting hardware ===
m3_bolt_d = 3.0;
m3_clear = 0.2;
m3_head_d = 5.5;             // socket head cap diameter
m3_head_h = 3.0;             // socket head height
bolt_spread = 10;            // bolt center distance from boss (along Y)

// === Derived ===
barrel_pocket_d = barrel_d + barrel_clear;  // 4.3mm
cable_hole_d = cable_d + 0.5;              // 1.7mm

// === ANCHOR BODY ===
difference() {
    union() {
        // Central barrel boss (slight taper for strength)
        cylinder(d1=boss_d + 1, d2=boss_d, h=boss_h);

        // +Y mounting flange
        hull() {
            cylinder(d=boss_d, h=0.5);
            translate([0, bolt_spread, 0])
                cylinder(d=m3_head_d + 4, h=0.5);
        }
        hull() {
            cylinder(d=boss_d, h=boss_h * 0.4);
            translate([0, bolt_spread, 0])
                cylinder(d=m3_head_d + 3, h=boss_h * 0.35);
        }

        // -Y mounting flange
        hull() {
            cylinder(d=boss_d, h=0.5);
            translate([0, -bolt_spread, 0])
                cylinder(d=m3_head_d + 4, h=0.5);
        }
        hull() {
            cylinder(d=boss_d, h=boss_h * 0.4);
            translate([0, -bolt_spread, 0])
                cylinder(d=m3_head_d + 3, h=boss_h * 0.35);
        }

        // Base flange connecting bolt pads
        hull() {
            translate([0, bolt_spread, 0])
                cylinder(d=m3_head_d + 4, h=1.5);
            cylinder(d=boss_d + 1, h=1.5);
            translate([0, -bolt_spread, 0])
                cylinder(d=m3_head_d + 4, h=1.5);
        }
    }

    // === Barrel pocket (open from top, barrel drops in) ===
    translate([0, 0, boss_h - barrel_h - 0.5])
        cylinder(d=barrel_pocket_d, h=barrel_h + 0.6);

    // === Cable exit hole (through bottom) ===
    translate([0, 0, -0.1])
        cylinder(d=cable_hole_d, h=boss_h + 0.2);

    // === M3 bolt holes (+Y) ===
    // Through-hole
    translate([0, bolt_spread, -0.1])
        cylinder(d=m3_bolt_d + m3_clear, h=boss_h * 0.4 + 0.2);
    // Socket head counterbore (from top)
    translate([0, bolt_spread, boss_h * 0.35 - m3_head_h])
        cylinder(d=m3_head_d + m3_clear, h=m3_head_h + 0.1);

    // === M3 bolt holes (-Y) ===
    translate([0, -bolt_spread, -0.1])
        cylinder(d=m3_bolt_d + m3_clear, h=boss_h * 0.4 + 0.2);
    translate([0, -bolt_spread, boss_h * 0.35 - m3_head_h])
        cylinder(d=m3_head_d + m3_clear, h=m3_head_h + 0.1);
}

// =====================================================================
// PRINT & ASSEMBLY INSTRUCTIONS
// =====================================================================
//
// WHAT THIS PART DOES:
//   Cable anchor on top of the agitator mount sleeve. A universal
//   shift cable barrel end drops into the pocket from the top.
//   The cable exits through the bottom hole, runs down alongside
//   the center tube to the cable spool on the Z-axis winch.
//
// CABLE: Universal bicycle shift cable
//   - 1.2mm braided steel wire
//   - 4mm × 4.5mm barrel/nipple end
//
// PRINT SETTINGS:
//   Orientation: Base flange flat on bed
//   Material:    PETG or ABS
//   Infill:      80%
//   Layer height: 0.15mm
//   Supports:    NO
//   Walls:       4 perimeters
//
// HARDWARE:
//   - 2x M3 × 8mm socket head bolts (thread into heat-set inserts
//     in the agitator mount sleeve)
//   - 1x universal shift cable (~500mm)
//
// ASSEMBLY:
//   1. Drop shift cable barrel into top pocket.
//   2. Thread cable down through exit hole.
//   3. Bolt anchor to sleeve (2x M3 into heat-set inserts).
//   4. Route cable down alongside tube to spool.
// =====================================================================

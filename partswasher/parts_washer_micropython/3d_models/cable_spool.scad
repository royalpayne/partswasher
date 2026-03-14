// Parts Washer - Cable Spool (Shift Cable, Crimp Ferrule Anchor)
// Fits directly on NEMA17 5mm D-shaft.
// Winds/unwinds shift cable to raise/lower washer head.
//
// Cable threads through a radial cross-hole in the core.
// A crimp ferrule on the exit side acts as a positive stop.
// Cable: 1.2mm wire (universal shift cable)
//
// Print: one flange flat on bed (spool standing up)
// Material: PETG or ABS
// Infill: 80%

$fn = 80;

// === Motor shaft ===
shaft_bore = 5.2;             // 5mm + clearance
shaft_flat = 4.5;             // D-shaft flat

// === Set screw ===
setscrew_d = 3.2;             // M3 grub screw

// === Shift cable ===
cable_d = 1.2;                // wire diameter
cable_hole_d = 1.7;           // cross-hole (cable + clearance)
ferrule_d = 3.0;              // crimp ferrule OD (countersink on exit side)

// === Spool core ===
core_od = 20.0;               // ~63mm cable per revolution
core_width = 10.0;            // winding width

// === Flanges ===
flange_od = 32.0;             // keeps cable from walking off
flange_thick = 2.5;

// === Hub ===
hub_od = 12.0;

// === Total width ===
total_width = core_width + flange_thick * 2;  // 15mm

// === Cross-hole position ===
// 2mm from left flange, cable starts winding from here
hole_z = flange_thick + 2;

// === SPOOL ===
difference() {
    union() {
        // Hub (full width)
        cylinder(d=hub_od, h=total_width);

        // Core (between flanges)
        translate([0, 0, flange_thick])
            cylinder(d=core_od, h=core_width);

        // Left flange (on bed)
        cylinder(d=flange_od, h=flange_thick);

        // Right flange
        translate([0, 0, total_width - flange_thick])
            cylinder(d=flange_od, h=flange_thick);
    }

    // === Shaft bore ===
    translate([0, 0, -0.1])
        cylinder(d=shaft_bore, h=total_width + 0.2);

    // === D-flat ===
    translate([shaft_flat/2, -shaft_bore/2, -0.1])
        cube([shaft_bore, shaft_bore, total_width + 0.2]);

    // === Set screw (radial, at midpoint) ===
    translate([0, 0, total_width/2])
        rotate([0, 90, 0])
        cylinder(d=setscrew_d, h=hub_od);

    // === Cable cross-hole (radial through core) ===
    translate([0, 0, hole_z])
        rotate([0, 90, 0])
        cylinder(d=cable_hole_d, h=core_od);

    // === Ferrule countersink (exit side, flush recess) ===
    // On the far side of the core so ferrule sits below the winding surface
    translate([-core_od/2, 0, hole_z])
        rotate([0, 90, 0])
        cylinder(d=ferrule_d + 0.5, h=2);
}

// =====================================================================
// PRINT & ASSEMBLY INSTRUCTIONS
// =====================================================================
//
// WHAT THIS PART DOES:
//   Cable winch spool that mounts directly on the NEMA17 motor shaft.
//   A shift cable threads through a radial cross-hole in the core
//   and is secured with a crimp ferrule on the exit side. As the
//   motor turns, cable winds on the core to raise the washer head.
//   Reversing unwinds and gravity lowers.
//
//   Single-layer winding: 10mm core width holds ~8 wraps of 1.2mm
//   cable = ~503mm capacity (206mm travel needed, plenty of margin).
//
// CABLE: Universal bicycle shift cable
//   - 1.2mm braided steel wire
//
// PRINT SETTINGS:
//   Orientation: One flange FLAT ON BED (spool standing up)
//   Material:    PETG or ABS
//   Infill:      80% minimum
//   Layer height: 0.15mm (tight shaft bore tolerance)
//   Supports:    NO
//   Walls:       4 perimeters
//   Top/bottom:  5 layers
//
// HARDWARE NEEDED:
//   - 1x M3 x 6mm set screw (locks spool on shaft)
//   - 1x universal shift cable (~500mm)
//   - 1x 1.5mm aluminum crimp ferrule
//
// ASSEMBLY:
//   1. Thread cable through the radial cross-hole from the winding
//      side, pull ~15mm through the exit side.
//   2. Slide crimp ferrule onto the exit end, crush with pliers.
//      The ferrule seats in the countersink flush with the core.
//   3. Pull cable snug from the winding side.
//   4. Slide spool onto motor shaft (D-flat aligns).
//   5. Tighten set screw.
//   6. Wind 2-3 turns by hand in the direction that raises head.
//   7. Route cable down through motor mount cable fairlead
//      to washer head cable anchor.
// =====================================================================

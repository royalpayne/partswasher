// Parts Washer - Top Motor Mount (Direct Drive, Spool Centered Over Tube)
// Spool centered directly above tube for straight cable drop.
// Motor offset to one side, 625ZZ bearing support on the other.
// Hollow plug for wire routing through center tube.

// === PARAMETERS ===

// Center tube
tube_id = 25.0;
tube_od = 31.51;

// Hollow plug (wires pass through center)
plug_od = 25.2;           // Press fit into 25mm bore (+0.2mm interference)
plug_id = 15.0;           // Center bore for wires
plug_length = 50.0;       // Deep press fit into tube

// Tube extension (extends shaft above tube, adds washer head travel range)
tube_ext = 50.0;          // Extension length above tube top

// Wire routing gap
wire_gap = 12.0;          // Wires exit sideways through this gap

// Set screws to lock plug
setscrew_d = 3.2;
setscrew_h = 10.0;

// Spool dimensions (must match cable_spool.scad)
spool_total_width = 15.0;
spool_clearance = 2.0;    // Gap each side between spool and wall

// Platform
platform_width = 50.0;
platform_depth = 50.0;
platform_thick = 5.0;

// Frame walls
wall_height = 50.0;
wall_thick = 5.0;

// Wall X positions (spool centered at x=0, directly over tube)
motor_wall_inner = -(spool_total_width/2 + spool_clearance);    // -9.5
motor_wall_outer = motor_wall_inner - wall_thick;                // -14.5
bearing_wall_inner = spool_total_width/2 + spool_clearance;     // +9.5
bearing_wall_outer = bearing_wall_inner + wall_thick;            // +14.5

// NEMA17 motor
nema17_size = 42.3;
nema17_hole_spacing = 31.0;
nema17_pilot_od = 22.2;
nema17_bolt = 3.2;

// 625ZZ bearing (5mm bore, 16mm OD, 5mm wide)
bearing_od = 16.0;
bearing_width = 5.0;
bearing_boss_od = bearing_od + 6;    // Boss around bearing pocket
bearing_boss_len = bearing_width + 3; // Pocket depth + 3mm backing

// Platform corner radius (matches motor_cover.scad shell contour)
corner_r = 8.0;

// Cable guide (exits platform alongside tube, not through center)
cable_guide_d = 4.0;
cable_guide_y = -(tube_od/2 + 1.0);  // Just outside tube edge

// Cable fairlead (raised guide tube with chamfer to prevent fraying)
fairlead_od = 10.0;          // Outer diameter of guide tube
fairlead_height = 10.0;      // Height above platform
fairlead_chamfer = 3.0;      // Chamfer radius at top opening

// Support skirt (partial cylinder bridging wire gap, much stronger than legs)
skirt_od = tube_od + 12;      // Match flange diameter
skirt_id = plug_od + 2;       // 26.6mm inner clearance for wire bending
wire_exit_angle = 90;         // Degrees of opening for wires to exit

$fn = 80;

// === CALCULATED ===
plat_z = plug_length + tube_ext + 5.0 + wire_gap;
wall_base_z = plat_z + platform_thick;
shaft_z = wall_base_z + wall_height / 2;

// === MODULES ===

module hollow_plug() {
    difference() {
        cylinder(d=plug_od, h=plug_length);
        cylinder(d=plug_id, h=plug_length);
        for (angle = [0, 120])
            rotate([0, 0, angle])
            translate([0, 0, setscrew_h])
                rotate([0, 90, 0])
                cylinder(d=setscrew_d, h=plug_od, center=true);
    }
}

module tube_extension() {
    // Extends the shaft tube upward, matching tube OD for washer head travel.
    // Hollow bore continues wire routing from plug.
    translate([0, 0, plug_length])
    difference() {
        cylinder(d=tube_od, h=tube_ext);
        cylinder(d=plug_id, h=tube_ext);
    }
}

module flange() {
    translate([0, 0, plug_length + tube_ext])
    difference() {
        cylinder(d=tube_od + 12, h=5.0);
        cylinder(d=plug_id, h=5.0);
    }
}

module support_skirt() {
    // 270° partial cylinder bridging the wire gap from flange to platform.
    // 90° opening allows wires to exit sideways. Much stronger than legs.
    flange_top = plug_length + tube_ext + 5.0;

    translate([0, 0, flange_top])
    difference() {
        cylinder(d=skirt_od, h=wire_gap);
        cylinder(d=skirt_id, h=wire_gap);
        // Wire exit slot: 90° opening centered on +X direction
        rotate([0, 0, -wire_exit_angle/2])
        translate([0, 0, -0.5])
            cube([skirt_od, skirt_od, wire_gap + 1]);
    }
}

module platform() {
    translate([0, 0, plat_z])
    difference() {
        // Rounded rectangle matching cover contour
        hull() {
            for (x = [-platform_width/2 + corner_r, platform_width/2 - corner_r])
                for (y = [-platform_depth/2 + corner_r, platform_depth/2 - corner_r])
                    translate([x, y, 0])
                        cylinder(r=corner_r, h=platform_thick);
        }
        // Cable guide hole (alongside tube edge, not center)
        translate([0, cable_guide_y, 0])
            cylinder(d=cable_guide_d, h=platform_thick);
        // Wire access opening (center)
        cylinder(d=plug_id + 2, h=platform_thick);
    }
}

module cable_fairlead() {
    // Raised guide tube on top of platform to prevent cable fraying.
    // Smooth chamfered top opening guides cable from spool angle
    // into vertical drop alongside tube.
    translate([0, cable_guide_y, plat_z + platform_thick])
    difference() {
        union() {
            // Main tube
            cylinder(d=fairlead_od, h=fairlead_height);
            // Chamfered funnel at top (guides cable in from spool angle)
            translate([0, 0, fairlead_height - fairlead_chamfer])
                cylinder(d1=fairlead_od, d2=fairlead_od + fairlead_chamfer*2,
                         h=fairlead_chamfer);
        }
        // Cable bore through entire height
        cylinder(d=cable_guide_d, h=fairlead_height + fairlead_chamfer);
        // Chamfered inner opening at top (smooth radius for cable)
        translate([0, 0, fairlead_height - fairlead_chamfer])
            cylinder(d1=cable_guide_d, d2=cable_guide_d + fairlead_chamfer*2,
                     h=fairlead_chamfer + 0.1);
    }
}

module frame_walls() {
    // Motor wall (left side)
    translate([motor_wall_outer, -platform_depth/2, wall_base_z])
        cube([wall_thick, platform_depth, wall_height]);

    // Bearing wall (right side)
    translate([bearing_wall_inner, -platform_depth/2, wall_base_z])
        cube([wall_thick, platform_depth, wall_height]);

    // Bearing boss (protrudes from outside of bearing wall)
    translate([bearing_wall_outer, 0, shaft_z])
        rotate([0, 90, 0])
        cylinder(d=bearing_boss_od, h=bearing_boss_len);
}

module mount_holes() {
    // --- Motor wall ---
    // Pilot hole
    translate([motor_wall_inner + 0.5, 0, shaft_z])
        rotate([0, -90, 0])
        cylinder(d=nema17_pilot_od, h=wall_thick + 2);

    // NEMA17 bolt holes
    for (y = [-1, 1]) for (z = [-1, 1])
        translate([motor_wall_inner + 0.5,
                   y * nema17_hole_spacing/2,
                   shaft_z + z * nema17_hole_spacing/2])
            rotate([0, -90, 0])
            cylinder(d=nema17_bolt, h=wall_thick + 2);

    // --- Bearing wall ---
    // 625ZZ bearing pocket (open from outer face of boss, bearing presses in)
    translate([bearing_wall_outer + bearing_boss_len - bearing_width - 0.2, 0, shaft_z])
        rotate([0, 90, 0])
        cylinder(d=bearing_od + 0.2, h=bearing_width + 0.4);

    // Shaft through-hole (wall + boss)
    translate([bearing_wall_inner - 0.5, 0, shaft_z])
        rotate([0, 90, 0])
        cylinder(d=6.0, h=wall_thick + bearing_boss_len + 2);
}

// === ASSEMBLY ===

difference() {
    union() {
        hollow_plug();
        tube_extension();
        flange();
        support_skirt();
        platform();
        cable_fairlead();
        frame_walls();
    }
    mount_holes();
}

// =====================================================================
// PRINT & ASSEMBLY INSTRUCTIONS
// =====================================================================
//
// WHAT THIS PART DOES:
//   Motor mount with spool centered directly above the center tube.
//   Cable drops straight down alongside the tube - no awkward angles.
//   Motor is offset to one side, 625ZZ bearing supports shaft on the
//   other side.
//
// DESIGN FEATURES:
//   - Hollow plug: press fit into tube bore (25.2mm OD in 25mm bore)
//   - Tube extension: 50mm above tube top, matches tube OD (31.51mm)
//     Extends washer head travel range by 50mm
//   - Wire bore: 15mm through plug and extension for wire routing
//   - Wire gap: 12mm for wires to exit sideways
//   - Support skirt: 270° partial cylinder bridging flange to platform
//     (90° wire exit opening, far stronger than individual legs)
//   - Motor wall (left): NEMA17 bolts to outside face
//   - Bearing wall (right): 625ZZ pocket with boss for shaft support
//   - Cable guide hole: offset to tube edge, cable runs down outside
//   - Spool centered at x=0 directly over tube center
//
// PRINT SETTINGS:
//   Orientation: PLATFORM FLAT ON BED (plug pointing up)
//   Material:    PETG or ABS required (NO PLA - heat nearby)
//   Infill:      60% minimum
//   Layer height: 0.2mm
//   Supports:    YES - tree supports recommended
//   Walls:       4 perimeters
//   Top/bottom:  4 layers
//
// HARDWARE NEEDED:
//   - 1x NEMA17 stepper motor (42mm frame, 5mm D-shaft)
//   - 4x M3 x 16mm socket head cap screw (motor to wall)
//   - 2x M3 x 6mm set screw (lock plug in tube)
//   - 1x 625ZZ bearing (5mm bore, 16mm OD, 5mm wide)
//
// ASSEMBLY:
//   1. Route wires up through center tube FIRST.
//   2. Insert hollow plug, seat flange on tube rim, lock set screws.
//   3. Bolt motor to outside of motor wall (4x M3x16).
//   4. Slide spool onto shaft from the open top/bearing side.
//   5. Tighten spool set screw.
//   6. Press 625ZZ bearing into bearing wall pocket (captures shaft tip).
//   7. Route cable from spool through cable guide hole, down alongside
//      tube to washer head cable anchor.
//
// CRITICAL DIMENSIONS:
//   - Plug OD 25.2mm press fits into 25mm tube bore
//   - Tube extension OD 31.51mm matches tube OD exactly
//   - Tube extension 50mm adds to washer head travel range
//   - Plug/extension ID 15mm must clear your wire bundle
//   - Wire gap 12mm for wires to exit sideways
//   - Motor bolt pattern 31mm matches NEMA17
//   - Bearing pocket 16.2mm fits 625ZZ (16mm OD)
// =====================================================================

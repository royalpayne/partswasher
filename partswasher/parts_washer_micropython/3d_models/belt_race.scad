// Belt Race Segment — 3D Printable
// Spool-profile ring segment with integrated L-bracket mounts
// 8 segments × 45° = full ring around carousel perimeter
// Bolts to carousel plate top surface with M3 machine screws
//
// Print: top flange flat on build plate, brackets point up
// Material: PLA or PETG
// All 8 segments fit on a single 9" × 9" print bed

$fn = 80;

// === Print bed ===
bed_size = 228.6;               // 9 inches in mm

// === Carousel reference (measured 37" circ ≈ 299mm, rounded up) ===
carousel_dia = 300;             // 300mm OD — slight clearance over measured 299mm
carousel_r = carousel_dia / 2;  // 150mm

// === Race dimensions ===
bracket_t = 2;                  // bracket material thickness
race_center_r = carousel_r + bracket_t + 2;  // spool center radius (~169mm)

// === Spool profile ===
spool_groove_w = 5;             // belt groove width
spool_flange_r = 4;             // flange extends beyond groove each side
spool_flange_t = 1.5;           // flange thickness
spool_hub_t = 2;                // groove hub wall thickness (radial)
spool_total_h = spool_flange_t + spool_groove_w + spool_flange_t;  // 8mm

// === Segments ===
num_segments = 8;
seg_arc = 360 / num_segments;   // 45 degrees each

// === Integrated mounting brackets ===
num_brackets_per_seg = 2;       // 2 per segment = 16 total
br_width = 10;                  // bracket tab width (tangential)
br_horizontal = 12;             // horizontal leg inward from spool
br_vertical = 8;                // vertical leg height (plate top to spool bottom)
br_t = 2.5;                     // bracket thickness
br_bolt_d = 3.2;                // M3 clearance
br_bolt_head_d = 5.7;           // M3 socket head counterbore
br_bolt_head_depth = 2.5;       // counterbore depth

// === Layout calculations ===
// Centered segment bounding box (rotated by -seg_arc/2)
_inner_r = race_center_r - spool_flange_r;  // 165mm
_outer_r = race_center_r + spool_flange_r;  // 173mm
_half_arc = seg_arc / 2;                     // 22.5°
_min_x = _inner_r * cos(_half_arc);          // ~152.4mm
_max_x = _outer_r;                           // 173mm at midpoint
_piece_w = _max_x - _min_x;                 // ~20.6mm
_piece_h = 2 * _outer_r * sin(_half_arc);   // ~132.4mm
_z_lift = br_vertical + br_t - spool_flange_t;  // 9mm — lifts brackets above bed

// === Single L-bracket ===
module mounting_bracket() {
    // L-shape: horizontal leg on carousel plate top, vertical leg drops to spool
    union() {
        // Horizontal leg (bolts to plate top)
        cube([br_horizontal, br_width, br_t]);
        // Vertical leg (outer end, extends up into spool body for solid union)
        translate([br_horizontal - br_t, 0, 0])
            cube([br_t, br_width, br_vertical + br_t + 1]);
    }
}

// === Single race segment (origin at ring center, arc from 0° to seg_arc) ===
module race_segment() {
    // --- Spool body ---
    union() {
        // Top flange
        rotate_extrude(angle=seg_arc)
        translate([race_center_r - spool_flange_r, 0, 0])
            square([spool_flange_r * 2, spool_flange_t]);

        // Groove hub (narrow center — belt rides here)
        translate([0, 0, spool_flange_t])
        rotate_extrude(angle=seg_arc)
        translate([race_center_r - spool_hub_t, 0, 0])
            square([spool_hub_t * 2, spool_groove_w]);

        // Bottom flange
        translate([0, 0, spool_flange_t + spool_groove_w])
        rotate_extrude(angle=seg_arc)
        translate([race_center_r - spool_flange_r, 0, 0])
            square([spool_flange_r * 2, spool_flange_t]);
    }

    // --- Integrated L-brackets ---
    for (i = [0 : num_brackets_per_seg - 1]) {
        ba = seg_arc / (num_brackets_per_seg + 1) * (i + 1);
        rotate([0, 0, ba])
        translate([carousel_r - br_horizontal + br_t, -br_width/2,
                   -(br_vertical + br_t - spool_flange_t)])
        difference() {
            mounting_bracket();
            // M3 bolt hole through horizontal leg
            translate([br_horizontal/2 - br_t/2, br_width/2, -0.1])
                cylinder(d=br_bolt_d, h=br_t + 0.2);
            // Counterbore from bottom
            translate([br_horizontal/2 - br_t/2, br_width/2, -0.1])
                cylinder(d=br_bolt_head_d, h=br_bolt_head_depth + 0.1);
        }
    }
}

// === Print-oriented segment (centered, flat on bed) ===
module print_segment() {
    // Lift so brackets clear the bed (top flange on build plate)
    translate([0, 0, _z_lift])
    // Center the arc symmetrically
    rotate([0, 0, -_half_arc])
    race_segment();
}

// === All 8 segments arranged on 9×9" print bed ===
module print_layout() {
    gap = 3;
    pitch = _piece_w + gap;  // ~23.6mm between piece centers

    // 8 segments in a single row — each ~21mm wide × 132mm tall
    // Total X: 8 × 23.6 = 188.8mm  (fits in 228.6mm)
    // Total Y: 132.4mm             (fits in 228.6mm)
    for (i = [0 : num_segments - 1]) {
        translate([-_min_x + gap + i * pitch,
                   _piece_h/2 + gap,
                   0])
        print_segment();
    }

    // Build plate outline (transparent reference)
    %translate([0, 0, -0.1])
        square([bed_size, bed_size]);
}

// ===========================
// DEFAULT VIEW: Print layout
// ===========================
color([0.3, 0.7, 0.9])
print_layout();


// Parts Washer Base - Little Giant (L&R / E. Marshall Co.)
// Watchmaker's 4-station parts washer
//
// COORDINATE SYSTEM: Z-up, natural orientation
//   z=0: table surface (bottom of feet)
//   Feet raise the base above the table
//   Base plate near the bottom, barrel walls go up
//   Carousel sits on rollers inside the barrel, near the top
//   Jars sit on the carousel

$fn = 80;

// Rounded square extrusion — used for square jars
module rounded_square_extrude(size, r, h) {
    linear_extrude(h)
        offset(r=r)
        square([size - 2*r, size - 2*r], center=true);
}

// === Overall dimensions (measured: 37" circumference ≈ 299mm, using 300mm) ===
top_dia = 300;              // barrel OD at rim (measured ~299mm, rounded to 300)
bottom_dia = 282;           // narrower at the base (proportional)
total_height = 89;          // ~3.5" barrel height (not counting feet)
wall_thickness = 2;         // sheet metal
shelf_width = 45;           // flat ring where jars sit
shelf_thickness = 3;        // shelf plate thickness
control_panel_height = 55;  // tapered section height (lower portion)

// === Feet ===
foot_dia_base = 14;         // narrow end (sits on table)
foot_dia_top = 22;          // wide end (attaches to base)
foot_height = 10;
foot_r = 141;               // radius from center — at outer rim edge
num_feet = 4;

// Z reference: feet sit on table at z=0, base starts at z=foot_height
base_z = foot_height;       // bottom of barrel/base plate

// === Center shaft ===
center_hole_dia = 25;       // agitation shaft bore
center_tube_dia = 31.51;    // center tube OD (measured)
center_tube_height = 89;    // full height of tube

// === Station layout (4 stations, 90 deg apart) ===
num_stations = 4;
jar_size = 95.25;           // square jar 3.75" per side
jar_corner_r = 8;           // corner rounding radius
jar_center_r = 82;          // jar center distance from axis (scaled for 300mm)
jar_cant = 45;              // rotate jars 45° so corners point radially
station_angles = [0, 90, 180, 270];  // WASH, RINSE1, RINSE2, HEATER

// === Jar dimensions (needed globally for agitator height calc) ===
jar_height = 165;
jar_wall = 3;
jar_base_r = 12;
jar_body_h = 108;
jar_taper_h = 35;
jar_mouth_h = 10;
jar_mouth_dia = 95.25;
jar_lid_dia = 101.6;
jar_lid_h = 12;

// === Divider walls ===
divider_height = 89;        // full height of basin
divider_thickness = 2;
divider_length = 65;        // radial length of divider (scaled for 300mm)
divider_inner_r = 41;       // start radius (scaled for 300mm)

// === Heater station shroud (station 3 = 270 deg) ===
shroud_dia = jar_size * 1.05;
shroud_height = 140;
shroud_wall = 2;

// === Control panel features ===
toggle_switch_dia = 6;
knob_dia = 25;
knob_height = 15;

// === Bottom plate ===
bottom_plate_thickness = 3;

// === Bottom plate spoke pattern ===
num_spokes = 3;
spoke_width = 40;           // scaled for 300mm
spoke_angles = [0, 120, 240];
center_hub_dia = 65;
spoke_outer_r = 118;        // scaled for 300mm

// === Motor mount (center, from original casting) ===
motor_mount_hole = 22;
motor_bolt_spacing = 31;    // NEMA17 pattern
motor_bolt_dia = 3.2;

// === Carousel plate (derived — needed globally) ===
_carousel_dia = top_dia;                     // 300mm OD
_carousel_r = _carousel_dia / 2;             // 150mm
_carousel_plate_z = base_z + total_height + 5;  // 5mm above barrel rim = 104mm
_carousel_plate_t = 3;
_carousel_top_z = _carousel_plate_z + _carousel_plate_t;  // 107mm

// === Agitator mount (derived — needed globally) ===
agit_plate_dia = 100;            // ~4" aluminum disc
agit_plate_h = 12.7;             // 1/2" thick aluminum plate
agit_plate_r = 4;                // edge rounding radius
agit_shaft_height = (jar_height + 3 + 20) * 2;  // clears jars + carousel + margin
agit_shaft_top = _carousel_top_z + agit_shaft_height;
agit_clamp_h = 76.2;             // 3 inches
agit_clamp_od = center_tube_dia + 12;
agit_clamp_z = agit_shaft_top - agit_clamp_h - 10;
agit_head_z = agit_clamp_z + agit_clamp_h;

// === Cable anchor dimensions (universal shift cable) ===
agit_cable_d = 1.2;              // shift cable wire diameter
agit_barrel_d = 4.0;             // barrel diameter
agit_barrel_h = 4.5;             // barrel height
agit_barrel_clear = 0.3;
agit_anchor_r = center_tube_dia/2 + 1;
agit_anchor_boss_d = 12;
agit_anchor_boss_h = 8;
agit_m3_bolt_d = 3.0;
agit_m3_clear = 0.2;
agit_m3_head_d = 5.5;
agit_m3_head_h = 3.0;
agit_m3_bolt_spread = 10;
agit_m3_insert_od = 4.0;
agit_m3_insert_depth = 4.0;

// ==========================================
// MODULES — all in natural Z-up coordinates
// ==========================================

module oval(length, width) {
    hull() {
        translate([-(length/2 - width/2), 0, 0]) circle(d=width);
        translate([ (length/2 - width/2), 0, 0]) circle(d=width);
    }
}

module tapered_shell() {
    // Outer tapered wall: narrow at bottom, wide at top (shelf level)
    // Sinusoidal concave curve
    taper_steps = 20;
    top_r = top_dia / 2;
    bot_r = bottom_dia / 2;
    difference() {
        for (s = [0 : taper_steps - 1]) {
            t0 = s / taper_steps;
            t1 = (s + 1) / taper_steps;
            e0 = sin(t0 * 90);
            e1 = sin(t1 * 90);
            hull() {
                translate([0, 0, base_z + t0 * control_panel_height])
                    cylinder(d=(bot_r + (top_r - bot_r) * e0) * 2, h=0.1);
                translate([0, 0, base_z + t1 * control_panel_height])
                    cylinder(d=(bot_r + (top_r - bot_r) * e1) * 2, h=0.1);
            }
        }
        for (s = [0 : taper_steps - 1]) {
            t0 = s / taper_steps;
            t1 = (s + 1) / taper_steps;
            e0 = sin(t0 * 90);
            e1 = sin(t1 * 90);
            hull() {
                translate([0, 0, base_z + t0 * control_panel_height - 0.05])
                    cylinder(d=(bot_r - wall_thickness + (top_r - bot_r) * e0) * 2, h=0.1);
                translate([0, 0, base_z + t1 * control_panel_height + 0.05])
                    cylinder(d=(bot_r - wall_thickness + (top_r - bot_r) * e1) * 2, h=0.1);
            }
        }
    }
}

module upper_basin() {
    // Vertical wall from shelf level to top rim
    basin_h = total_height - control_panel_height;
    translate([0, 0, base_z + control_panel_height])
    difference() {
        cylinder(d=top_dia, h=basin_h);
        translate([0, 0, -0.1])
            cylinder(d=top_dia - wall_thickness*2, h=basin_h + 0.2);
    }
}

module shelf_ring() {
    // Flat ring where jars sit (at shelf level)
    translate([0, 0, base_z + control_panel_height])
    difference() {
        cylinder(d=top_dia - wall_thickness*2, h=shelf_thickness);
        translate([0, 0, -0.1])
            cylinder(d=top_dia - shelf_width*2, h=shelf_thickness + 0.2);
        translate([0, 0, -0.1])
            cylinder(d=center_hole_dia, h=shelf_thickness + 0.2);
    }
}

module bottom_plate() {
    // Cast aluminum base plate with 3 radial spokes and 3 kidney cutouts
    translate([0, 0, base_z + total_height - bottom_plate_thickness])
    difference() {
        cylinder(d=bottom_dia, h=bottom_plate_thickness);
        // 3 kidney-shaped cutouts between spokes
        for (i = [0:2]) {
            a = spoke_angles[i] + 60;
            rotate([0, 0, a])
            translate([0, 0, -0.1])
                linear_extrude(bottom_plate_thickness + 0.2)
                hull() {
                    translate([55, 0, 0]) circle(d=50);
                    translate([105, 0, 0]) circle(d=55);
                }
        }
        // Center bore for motor shaft
        translate([0, 0, -0.1])
            cylinder(d=motor_mount_hole, h=bottom_plate_thickness + 0.2);
        // Motor bolt holes
        for (dx = [-1, 1])
            for (dy = [-1, 1])
                translate([dx * motor_bolt_spacing/2, dy * motor_bolt_spacing/2, -0.1])
                    cylinder(d=motor_bolt_dia, h=bottom_plate_thickness + 0.2);
    }
}

module center_tube() {
    translate([0, 0, base_z])
    difference() {
        cylinder(d=center_tube_dia, h=center_tube_height);
        translate([0, 0, -0.1])
            cylinder(d=center_hole_dia, h=center_tube_height + 0.2);
    }
}

module divider_walls() {
    for (i = [0:num_stations-1]) {
        a = station_angles[i] + 45;
        rotate([0, 0, a])
        translate([divider_inner_r + divider_length/2, -divider_thickness/2, base_z])
            cube([divider_length, divider_thickness, divider_height]);
    }
}

module heater_shroud() {
    rotate([0, 0, 270])
    translate([jar_center_r, 0, base_z + control_panel_height + shelf_thickness])
    difference() {
        cylinder(d=shroud_dia + shroud_wall*2, h=shroud_height);
        translate([0, 0, -0.1])
            cylinder(d=shroud_dia, h=shroud_height + 0.2);
    }
}

module control_panel_features() {
    // Toggle switch - left
    rotate([0, 0, -30])
    translate([bottom_dia/2 + 1, 0, base_z + control_panel_height * 0.45])
    rotate([0, 90, 0]) {
        color("Silver") cylinder(d=12, h=3);
        color("Silver") cylinder(d=3, h=12);
    }
    // Speed knob - center
    rotate([0, 0, 0])
    translate([bottom_dia/2 + 1, 0, base_z + control_panel_height * 0.4])
    rotate([0, 90, 0]) {
        color("DimGray") cylinder(d=knob_dia, h=knob_height);
        color("Black") translate([0, 0, knob_height])
            cylinder(d=knob_dia - 4, h=2);
    }
    // Toggle switch - right
    rotate([0, 0, 30])
    translate([bottom_dia/2 + 1, 0, base_z + control_panel_height * 0.45])
    rotate([0, 90, 0]) {
        color("Silver") cylinder(d=12, h=3);
        color("Silver") cylinder(d=3, h=12);
    }
    // Oval badges
    rotate([0, 0, -30])
    translate([bottom_dia/2 + 0.5, 0, base_z + control_panel_height * 0.65])
    rotate([0, 90, 0])
        color("Silver") scale([1, 1.4, 1]) cylinder(d=18, h=1);
    rotate([0, 0, 30])
    translate([bottom_dia/2 + 0.5, 0, base_z + control_panel_height * 0.65])
    rotate([0, 90, 0])
        color("Silver") scale([1, 1.4, 1]) cylinder(d=18, h=1);
}

module glass_jars() {
    jar_h = 100;
    _jar_wall = 3;
    _base_r = 10;
    _body_h = 45;
    _taper_h = 25;
    _mouth_h = 10;
    jar_mouth_dia = 95.25;
    jar_lid_dia = 101.6;
    jar_lid_h = 12;
    for (i = [0:2]) {
        rotate([0, 0, station_angles[i]])
        translate([jar_center_r, 0, base_z + control_panel_height + shelf_thickness])
        rotate([0, 0, jar_cant]) {
            color("LightBlue", 0.3)
            difference() {
                union() {
                    hull() {
                        rounded_square_extrude(jar_size - _base_r*2, jar_corner_r, 0.1);
                        translate([0, 0, _base_r])
                            rounded_square_extrude(jar_size, jar_corner_r, 0.1);
                    }
                    translate([0, 0, _base_r])
                        rounded_square_extrude(jar_size, jar_corner_r, _body_h);
                    translate([0, 0, _base_r + _body_h])
                        hull() {
                            linear_extrude(0.1)
                                offset(r=jar_corner_r)
                                square([jar_size - 2*jar_corner_r, jar_size - 2*jar_corner_r], center=true);
                            translate([0, 0, _taper_h])
                                cylinder(d=jar_mouth_dia, h=0.1);
                        }
                    translate([0, 0, _base_r + _body_h + _taper_h])
                        cylinder(d=jar_mouth_dia, h=_mouth_h);
                }
                translate([0, 0, _jar_wall])
                union() {
                    hull() {
                        rounded_square_extrude(jar_size - _base_r*2 - _jar_wall*2, jar_corner_r, 0.1);
                        translate([0, 0, _base_r])
                            rounded_square_extrude(jar_size - _jar_wall*2, jar_corner_r, 0.1);
                    }
                    translate([0, 0, _base_r])
                        rounded_square_extrude(jar_size - _jar_wall*2, jar_corner_r, _body_h);
                    translate([0, 0, _base_r + _body_h])
                        hull() {
                            linear_extrude(0.1)
                                offset(r=jar_corner_r)
                                square([jar_size - _jar_wall*2 - 2*jar_corner_r, jar_size - _jar_wall*2 - 2*jar_corner_r], center=true);
                            translate([0, 0, _taper_h])
                                cylinder(d=jar_mouth_dia - _jar_wall*2, h=0.1);
                        }
                    translate([0, 0, _base_r + _body_h + _taper_h])
                        cylinder(d=jar_mouth_dia - _jar_wall*2, h=_mouth_h + 1);
                }
            }
            color("DimGray")
            translate([0, 0, _base_r + _body_h + _taper_h + _mouth_h])
                cylinder(d=jar_lid_dia, h=jar_lid_h);
        }
    }
}

module center_shaft() {
    // Center tube extends from base up to agitator shaft top
    // Matches assembly_view.scad: tube_od=31.51, tube_id=25
    color("Silver")
    translate([0, 0, base_z])
    difference() {
        cylinder(d=center_tube_dia, h=agit_shaft_top - base_z);
        translate([0, 0, -0.1])
            cylinder(d=center_hole_dia, h=agit_shaft_top - base_z + 0.2);
    }
}

// ==========================================
// Z-AXIS CABLE WINCH + AGITATOR ASSEMBLY
// (sits on top of center tube)
// ==========================================

// Z-axis dimensions (from assembly_view.scad, adapted to base coords)
// Winch sits on top of extended shaft, above agitator
z_tube_top = agit_shaft_top;   // top of extended shaft

// Motor mount geometry
z_plug_length = 50;
z_tube_ext = 50;            // extension above tube top
z_flange_thick = 5;
z_wire_gap = 12;
z_platform_thick = 5;
z_platform_size = 50;
z_wall_height = 50;
z_wall_thick = 5;

// Spool dimensions
z_spool_flange_od = 32;
z_spool_core_od = 20;
z_spool_width = 15;
z_spool_clearance = 2;

// Wall positions (spool centered at x=0)
z_motor_wall_inner = -(z_spool_width/2 + z_spool_clearance);   // -9.5
z_motor_wall_outer = z_motor_wall_inner - z_wall_thick;          // -14.5
z_bearing_wall_inner = z_spool_width/2 + z_spool_clearance;     // +9.5
z_bearing_wall_outer = z_bearing_wall_inner + z_wall_thick;      // +14.5

// Calculated Z positions (absolute)
z_flange_top = z_tube_top + z_tube_ext;
z_platform = z_flange_top + z_wire_gap;
z_wall_base = z_platform + z_platform_thick;
z_shaft = z_wall_base + z_wall_height/2;

// NEMA17 motor
z_n17_size = 42.3;
z_n17_length = 40;
z_n17_shaft_len = 24;

// 625ZZ bearing
z_brg_od = 16;
z_brg_boss_od = z_brg_od + 6;
z_brg_boss_len = 8;

// Cable
z_cable_d = 1.2;                // shift cable wire diameter
z_cable_guide_y = -(center_tube_dia/2 + 1);

// Agitator mount dimensions (vars defined at top of file)

module z_motor_mount() {
    color([0.2, 0.55, 0.85]) {
        // Hollow plug (press fit into tube bore)
        translate([0, 0, z_tube_top - z_plug_length])
        difference() {
            cylinder(d=center_hole_dia + 0.2, h=z_plug_length);
            cylinder(d=15, h=z_plug_length);
        }

        // Tube extension
        translate([0, 0, z_tube_top])
        difference() {
            cylinder(d=center_tube_dia, h=z_tube_ext);
            cylinder(d=15, h=z_tube_ext);
        }

        // Flange
        translate([0, 0, z_flange_top - z_flange_thick])
        difference() {
            cylinder(d=center_tube_dia + 12, h=z_flange_thick);
            cylinder(d=15, h=z_flange_thick);
        }

        // Support skirt (270° partial, 90° wire exit on +X)
        translate([0, 0, z_flange_top])
        difference() {
            cylinder(d=center_tube_dia + 12, h=z_wire_gap);
            cylinder(d=center_hole_dia + 2, h=z_wire_gap);
            rotate([0, 0, -45])
            translate([0, 0, -0.5])
                cube([center_tube_dia + 12, center_tube_dia + 12, z_wire_gap + 1]);
        }

        // Platform
        translate([0, 0, z_platform])
        hull() {
            for (x = [-z_platform_size/2 + 8, z_platform_size/2 - 8])
                for (y = [-z_platform_size/2 + 8, z_platform_size/2 - 8])
                    translate([x, y, 0])
                        cylinder(r=8, h=z_platform_thick);
        }

        // Cable fairlead
        translate([0, z_cable_guide_y, z_platform + z_platform_thick])
            cylinder(d=10, h=10);
        translate([0, z_cable_guide_y, z_platform + z_platform_thick + 7])
            cylinder(d1=10, d2=16, h=3);

        // Motor wall (left)
        translate([z_motor_wall_outer, -z_platform_size/2, z_wall_base])
            cube([z_wall_thick, z_platform_size, z_wall_height]);

        // Bearing wall (right)
        translate([z_bearing_wall_inner, -z_platform_size/2, z_wall_base])
            cube([z_wall_thick, z_platform_size, z_wall_height]);

        // Bearing boss
        translate([z_bearing_wall_outer, 0, z_shaft])
            rotate([0, 90, 0])
            cylinder(d=z_brg_boss_od, h=z_brg_boss_len);
    }
}

module z_nema17() {
    // Motor body on outside of motor wall, shaft pointing right
    color([0.15, 0.15, 0.15])
    translate([z_motor_wall_outer, 0, z_shaft])
    rotate([0, -90, 0])
    translate([-z_n17_size/2, -z_n17_size/2, 0])
        cube([z_n17_size, z_n17_size, z_n17_length]);

    // Shaft
    color("Silver")
    translate([z_motor_wall_outer, 0, z_shaft])
    rotate([0, 90, 0])
        cylinder(d=5, h=z_n17_shaft_len);
}

module z_cable_spool() {
    color([0.9, 0.6, 0.1])
    translate([-z_spool_width/2, 0, z_shaft])
    rotate([0, 90, 0]) {
        cylinder(d=z_spool_flange_od, h=2.5);
        translate([0, 0, 2.5])
            cylinder(d=z_spool_core_od, h=10);
        translate([0, 0, 12.5])
            cylinder(d=z_spool_flange_od, h=2.5);
    }
}

module z_bearing() {
    color([0.7, 0.7, 0.7])
    translate([z_bearing_wall_outer, 0, z_shaft])
    rotate([0, 90, 0])
    difference() {
        cylinder(d=z_brg_od, h=5);
        cylinder(d=5, h=5);
    }
}

module z_cable() {
    z_anchor = agit_head_z;  // cable anchor is at top of agitator sleeve
    z_fairlead_top = z_platform + z_platform_thick + 10;

    color([0.3, 0.3, 0.3]) {
        // Spool to fairlead
        hull() {
            translate([0, 0, z_shaft - z_spool_core_od/2])
                sphere(d=z_cable_d);
            translate([0, z_cable_guide_y, z_fairlead_top])
                sphere(d=z_cable_d);
        }
        // Fairlead down to head anchor
        translate([0, z_cable_guide_y, z_anchor])
            cylinder(d=z_cable_d, h=z_fairlead_top - z_anchor);
    }
}

// ==========================================
// AGITATOR MOUNT — sleeve + contoured arm + rounded plate
// ==========================================
module agitator_mount() {
    color([0.25, 0.25, 0.27])  // Dark ABS plastic
    rotate([0, 0, station_angles[0]])
    difference() {
        union() {
            // --- Sleeve collar (slides on shaft) ---
            rotate([0, 0, -station_angles[0]])
            translate([0, 0, agit_clamp_z])
                cylinder(d=agit_clamp_od, h=agit_clamp_h);

            // --- Smooth flowing arm: multiple hull stages ---
            // Stage 1: collar top widens into arm root
            hull() {
                translate([0, 0, agit_head_z - 10])
                    scale([1.2, 0.8, 1])
                    cylinder(d=agit_clamp_od, h=10);
                translate([jar_center_r * 0.3, 0, agit_head_z - 8])
                    scale([1, 0.6, 1])
                    cylinder(d=agit_clamp_od + 5, h=8);
            }
            // Stage 2: arm root flows outward
            hull() {
                translate([jar_center_r * 0.3, 0, agit_head_z - 8])
                    scale([1, 0.6, 1])
                    cylinder(d=agit_clamp_od + 5, h=8);
                translate([jar_center_r * 0.65, 0, agit_head_z - 5])
                    scale([1, 0.7, 1])
                    cylinder(d=45, h=5);
            }
            // Stage 3: arm merges into plate underside
            hull() {
                translate([jar_center_r * 0.65, 0, agit_head_z - 5])
                    scale([1, 0.7, 1])
                    cylinder(d=45, h=5);
                translate([jar_center_r, 0, agit_head_z - 3])
                    cylinder(d=agit_plate_dia - 5, h=3);
            }

            // --- Rounded motor plate ---
            translate([jar_center_r, 0, agit_head_z]) {
                // Flat center disc
                cylinder(d=agit_plate_dia - agit_plate_r*2, h=agit_plate_h);
                // Rounded outer edge ring (torus)
                translate([0, 0, agit_plate_r])
                    rotate_extrude()
                    translate([agit_plate_dia/2 - agit_plate_r, 0, 0])
                        circle(r=agit_plate_r);
                // Fill between torus and center
                translate([0, 0, agit_plate_r])
                    cylinder(d=agit_plate_dia - agit_plate_r*2, h=agit_plate_h - agit_plate_r);
                // Top rounded edge
                translate([0, 0, agit_plate_h - agit_plate_r])
                    rotate_extrude()
                    translate([agit_plate_dia/2 - agit_plate_r, 0, 0])
                        circle(r=agit_plate_r);
                // Fill top
                cylinder(d=agit_plate_dia, h=agit_plate_h - agit_plate_r);
            }

            // --- Lower support sweep (underside curve) ---
            hull() {
                translate([0, 0, agit_clamp_z + agit_clamp_h * 0.35])
                    scale([1, 0.7, 1])
                    cylinder(d=agit_clamp_od + 2, h=5);
                translate([jar_center_r * 0.35, 0, agit_head_z - 15])
                    scale([1, 0.5, 1])
                    cylinder(d=agit_clamp_od - 5, h=5);
            }
            hull() {
                translate([jar_center_r * 0.35, 0, agit_head_z - 15])
                    scale([1, 0.5, 1])
                    cylinder(d=agit_clamp_od - 5, h=5);
                translate([jar_center_r * 0.7, 0, agit_head_z - 8])
                    scale([1, 0.6, 1])
                    cylinder(d=30, h=4);
            }
        }

        // --- Bore out sleeve center ---
        rotate([0, 0, -station_angles[0]])
        translate([0, 0, agit_clamp_z - 0.1])
            cylinder(d=center_tube_dia + 0.5, h=agit_clamp_h + 15);

        // --- Plate center bore (agitation shaft) ---
        translate([jar_center_r, 0, agit_head_z - 0.1])
            cylinder(d=10, h=agit_plate_h + 0.2);

        // --- M3 heat-set insert pockets for cable anchor ---
        rotate([0, 0, -station_angles[0]])
        translate([agit_anchor_r, 0, 0]) {
            translate([0, agit_m3_bolt_spread, agit_head_z - agit_m3_insert_depth])
                cylinder(d=agit_m3_insert_od, h=agit_m3_insert_depth + 0.1);
            translate([0, -agit_m3_bolt_spread, agit_head_z - agit_m3_insert_depth])
                cylinder(d=agit_m3_insert_od, h=agit_m3_insert_depth + 0.1);
        }
    }
}

// ==========================================
// CABLE ANCHOR — brake cable barrel pocket on agitator sleeve top
// ==========================================
module agit_cable_anchor() {
    color([0.25, 0.25, 0.27])
    translate([agit_anchor_r, 0, agit_head_z])
    difference() {
        union() {
            // Central barrel boss
            cylinder(d1=agit_anchor_boss_d + 1, d2=agit_anchor_boss_d, h=agit_anchor_boss_h);
            // +Y flange
            hull() {
                cylinder(d=agit_anchor_boss_d, h=0.5);
                translate([0, agit_m3_bolt_spread, 0])
                    cylinder(d=agit_m3_head_d + 4, h=0.5);
            }
            hull() {
                cylinder(d=agit_anchor_boss_d, h=agit_anchor_boss_h * 0.4);
                translate([0, agit_m3_bolt_spread, 0])
                    cylinder(d=agit_m3_head_d + 3, h=agit_anchor_boss_h * 0.35);
            }
            // -Y flange
            hull() {
                cylinder(d=agit_anchor_boss_d, h=0.5);
                translate([0, -agit_m3_bolt_spread, 0])
                    cylinder(d=agit_m3_head_d + 4, h=0.5);
            }
            hull() {
                cylinder(d=agit_anchor_boss_d, h=agit_anchor_boss_h * 0.4);
                translate([0, -agit_m3_bolt_spread, 0])
                    cylinder(d=agit_m3_head_d + 3, h=agit_anchor_boss_h * 0.35);
            }
            // Base flange connecting everything
            hull() {
                translate([0, agit_m3_bolt_spread, 0])
                    cylinder(d=agit_m3_head_d + 4, h=1.5);
                cylinder(d=agit_anchor_boss_d + 1, h=1.5);
                translate([0, -agit_m3_bolt_spread, 0])
                    cylinder(d=agit_m3_head_d + 4, h=1.5);
            }
        }
        // Barrel pocket
        translate([0, 0, agit_anchor_boss_h - agit_barrel_h - 0.5])
            cylinder(d=agit_barrel_d + agit_barrel_clear, h=agit_barrel_h + 0.6);
        // Cable exit hole
        translate([0, 0, -0.1])
            cylinder(d=agit_cable_d + 0.5, h=agit_anchor_boss_h + 0.2);
        // M3 through-holes +Y
        translate([0, agit_m3_bolt_spread, -0.1])
            cylinder(d=agit_m3_bolt_d + agit_m3_clear, h=agit_anchor_boss_h * 0.4 + 0.2);
        translate([0, agit_m3_bolt_spread, agit_anchor_boss_h * 0.35 - agit_m3_head_h])
            cylinder(d=agit_m3_head_d + agit_m3_clear, h=agit_m3_head_h + 0.1);
        // M3 through-holes -Y
        translate([0, -agit_m3_bolt_spread, -0.1])
            cylinder(d=agit_m3_bolt_d + agit_m3_clear, h=agit_anchor_boss_h * 0.4 + 0.2);
        translate([0, -agit_m3_bolt_spread, agit_anchor_boss_h * 0.35 - agit_m3_head_h])
            cylinder(d=agit_m3_head_d + agit_m3_clear, h=agit_m3_head_h + 0.1);
    }
}

// ==========================================
// NEMA23 + RATTMMOTOR BRACKET on agitator plate
// ==========================================
// RATTMMOTOR NEMA23 Mount Bracket dimensions
n23_flange_sq = 54.7;
n23_flange_h = 5;
n23_body_sq = 47;
n23_body_h = 31.77;
n23_bolt_spacing = 47;
n23_bolt_d = 5.5;
n23_pilot_d = 42;
n23_bore_d = 29;
n23_bottom_cbore_d = 33;
n23_bottom_cbore_h = 5;
n23_front_bore_d = 29;
n23_total_h = n23_body_h + n23_flange_h;  // 36.77mm

// NEMA23 Motor (YEJMKJ spec)
nema23_face = 56.3;
nema23_body_len = 40.4;
nema23_bolt_sp = 47.14;
nema23_mpilot_d = 38.1;
nema23_mpilot_h = 1.6;
nema23_shaft_d = 8.0;
nema23_shaft_len = 21;
nema23_connector_len = 18;

module agitator_nema23() {
    rotate([0, 0, station_angles[0]])
    translate([jar_center_r, 0, agit_head_z + agit_plate_h]) {
        // RATTMMOTOR bracket
        color([0.75, 0.75, 0.78])
        difference() {
            union() {
                translate([-n23_flange_sq/2, -n23_flange_sq/2, n23_body_h])
                    cube([n23_flange_sq, n23_flange_sq, n23_flange_h]);
                translate([-n23_body_sq/2, -n23_body_sq/2, 0])
                    cube([n23_body_sq, n23_body_sq, n23_body_h]);
            }
            cylinder(d=n23_bore_d, h=n23_total_h);
            translate([0, 0, n23_body_h])
                cylinder(d=n23_pilot_d, h=n23_flange_h);
            translate([0, 0, -0.1])
                cylinder(d=n23_bottom_cbore_d, h=n23_bottom_cbore_h + 0.1);
            translate([0, -n23_body_sq/2 - 0.1, n23_body_h/2])
                rotate([-90, 0, 0])
                cylinder(d=n23_front_bore_d, h=n23_body_sq + 0.2);
            for (x = [-1, 1]) for (y = [-1, 1])
                translate([x * n23_bolt_spacing/2, y * n23_bolt_spacing/2, n23_body_h])
                    cylinder(d=n23_bolt_d, h=n23_flange_h + 0.1);
            for (x = [-1, 1]) for (y = [-1, 1])
                translate([x * n23_bolt_spacing/2, y * n23_bolt_spacing/2, -0.1])
                    cylinder(d=n23_bolt_d, h=n23_body_h + 0.2);
        }

        // NEMA23 motor on top
        color([0.15, 0.15, 0.15])
        translate([0, 0, n23_total_h]) {
            cylinder(d=nema23_mpilot_d, h=nema23_mpilot_h);
            translate([-nema23_face/2, -nema23_face/2, nema23_mpilot_h])
                cube([nema23_face, nema23_face, nema23_body_len]);
            translate([0, 0, nema23_mpilot_h + nema23_body_len])
                cylinder(d=nema23_face - 8, h=nema23_connector_len);
        }

        // Motor shaft (extends down through bracket)
        color("Silver")
        translate([0, 0, n23_total_h - nema23_shaft_len])
            cylinder(d=nema23_shaft_d, h=nema23_shaft_len);
    }
}

module z_motor_cover() {
    z_shell_thick = 2;
    z_clearance = 2;
    z_corner_r = 8;
    z_roof_extra = 5;

    z_env_left = z_motor_wall_outer - z_n17_length - z_clearance;
    z_env_right = z_bearing_wall_outer + z_brg_boss_len + z_clearance;
    z_env_front = -(z_platform_size/2 + z_clearance);
    z_env_back = z_platform_size/2 + z_clearance;
    z_env_height = z_wall_height + z_roof_extra;

    zx1 = z_env_left + z_corner_r;
    zx2 = z_env_right - z_corner_r;
    zy1 = z_env_front + z_corner_r;
    zy2 = z_env_back - z_corner_r;
    zh = z_env_height - z_corner_r;

    color([0.3, 0.75, 0.35, 0.25])
    translate([0, 0, z_wall_base])
    difference() {
        hull() {
            for (x = [zx1, zx2]) for (y = [zy1, zy2]) {
                translate([x, y, 0]) cylinder(r=z_corner_r, h=0.1);
                translate([x, y, zh]) sphere(r=z_corner_r);
            }
        }
        hull() {
            for (x = [zx1 + z_shell_thick, zx2 - z_shell_thick])
                for (y = [zy1 + z_shell_thick, zy2 - z_shell_thick]) {
                    translate([x, y, 0]) cylinder(r=z_corner_r - z_shell_thick, h=0.1);
                    translate([x, y, zh]) sphere(r=z_corner_r - z_shell_thick);
                }
        }
        // Open bottom
        translate([z_env_left - 1, z_env_front - 1, -z_corner_r - 1])
            cube([z_env_right - z_env_left + 2, z_env_back - z_env_front + 2, z_corner_r + 1]);
    }
}

module z_axis_assembly() {
    // Rotated 90° so spool axis is perpendicular to agitator motor
    rotate([0, 0, 90]) {
        z_motor_mount();
        z_nema17();
        z_cable_spool();
        z_bearing();
        z_cable();
        z_motor_cover();
    }
}

module tapered_feet() {
    color("Black")
    for (i = [0:num_feet-1])
        rotate([0, 0, i * 360/num_feet + 45])
        translate([foot_r, 0, 0])
            cylinder(d1=foot_dia_base, d2=foot_dia_top, h=foot_height);
}

module casting_details() {
    // Raised features on the cast aluminum base plate (top side, inside barrel)
    // In natural coords: base plate top surface is at base_z + total_height
    bp_top = base_z + total_height;

    // --- Raised center hub / motor boss ---
    hub_h = 10;
    color("Silver")
    translate([0, 0, bp_top])
    difference() {
        // Hub extends DOWN into barrel from base plate
        translate([0, 0, -hub_h])
            cylinder(d=center_hub_dia, h=hub_h);
        translate([0, 0, -hub_h - 0.1])
            cylinder(d=motor_mount_hole, h=hub_h + 0.2);
        for (dx = [-1, 1])
            for (dy = [-1, 1])
                translate([dx * motor_bolt_spacing/2, dy * motor_bolt_spacing/2, -hub_h - 0.1])
                    cylinder(d=motor_bolt_dia, h=hub_h + 0.2);
    }

    // --- Spoke reinforcement ribs (hanging down from base plate) ---
    rib_w = 14;
    rib_h = 7;
    rib_inner_r = center_hub_dia/2;
    rib_outer_r = spoke_outer_r - 5;
    color("Silver")
    for (i = [0:2]) {
        rotate([0, 0, spoke_angles[i]])
        translate([0, 0, bp_top])
        hull() {
            translate([rib_inner_r, -rib_w/2, -rib_h])
                cube([1, rib_w, rib_h]);
            translate([rib_outer_r, -rib_w*0.5/2, -rib_h * 0.4])
                cube([1, rib_w*0.5, rib_h * 0.4]);
        }
    }

    // --- Gussets where spokes meet center hub ---
    gusset_h = 8;
    color("Silver")
    for (i = [0:2]) {
        for (side = [-1, 1]) {
            rotate([0, 0, spoke_angles[i] + side * 20])
            translate([center_hub_dia/2 - 3, -6, bp_top - gusset_h])
            hull() {
                cube([3, 12, gusset_h]);
                translate([15, side > 0 ? 4 : -4, gusset_h - 1])
                    cube([2, 4, 1]);
            }
        }
    }

    // --- Foot mounting bosses (extend down from base plate inside barrel) ---
    foot_boss_dia = 30;
    foot_bolt_dia = 6;
    foot_boss_h = total_height - bottom_plate_thickness;
    color("Silver")
    intersection() {
        // Clip to barrel interior envelope
        union() {
            hull() {
                translate([0, 0, base_z])
                    cylinder(d=bottom_dia, h=0.1);
                translate([0, 0, base_z + control_panel_height])
                    cylinder(d=top_dia, h=0.1);
            }
            translate([0, 0, base_z + control_panel_height])
                cylinder(d=top_dia, h=total_height - control_panel_height);
        }
        // The 4 boss cylinders extending down from base plate
        for (i = [0:num_feet-1])
            rotate([0, 0, i * 360/num_feet + 45])
            translate([foot_r, 0, base_z])
            difference() {
                cylinder(d=foot_boss_dia, h=foot_boss_h);
                translate([0, 0, -0.1])
                    cylinder(d=foot_bolt_dia, h=foot_boss_h + 0.2);
            }
    }

    // --- Component mounting pads (inside barrel, on spokes) ---
    pad_h = 5;
    color("Silver") {
        rotate([0, 0, spoke_angles[0]])
        translate([70, -14, bp_top - pad_h])
            cube([22, 12, pad_h]);
        rotate([0, 0, spoke_angles[0]])
        translate([70, 3, bp_top - pad_h])
            cube([22, 12, pad_h]);
        rotate([0, 0, spoke_angles[1]])
        translate([55, -18, bp_top - pad_h])
            cube([35, 36, pad_h]);
        rotate([0, 0, spoke_angles[2]])
        translate([65, -12, bp_top - pad_h])
            cube([28, 24, pad_h]);
    }

    // --- Outer rim lip (inside, at top) ---
    rim_lip_h = 6;
    rim_lip_w = 8;
    color("Silver")
    translate([0, 0, bp_top - rim_lip_h])
    difference() {
        cylinder(d=bottom_dia, h=rim_lip_h);
        translate([0, 0, -0.1])
            cylinder(d=bottom_dia - rim_lip_w*2, h=rim_lip_h + 0.2);
        for (i = [0:2]) {
            a = spoke_angles[i] + 60;
            rotate([0, 0, a])
            translate([0, 0, -0.1])
                linear_extrude(rim_lip_h + 0.2)
                hull() {
                    translate([55, 0, 0]) circle(d=50);
                    translate([105, 0, 0]) circle(d=55);
                }
        }
    }
}

module roller_supports() {
    // Carousel roller/wheel supports — cast into the spoke ends
    // Rollers sit inside the barrel, below the base plate
    roller_r = 130;
    pillar_w = 20;
    pillar_l = 12;
    pillar_h = 15;
    wheel_dia = 18;
    wheel_w = 6;
    axle_h = 10;
    slot_w = 8;

    bp_top = base_z + total_height;

    for (i = [0:2]) {
        rotate([0, 0, spoke_angles[i]])
        translate([roller_r, 0, bp_top - bottom_plate_thickness - pillar_h]) {
            // Cast pillar (hanging down from base plate)
            color("DimGray")
            difference() {
                translate([-pillar_l/2, -pillar_w/2, 0])
                    cube([pillar_l, pillar_w, pillar_h]);
                // Slot for wheel
                translate([-slot_w/2, -pillar_w/2 - 0.1, pillar_h - axle_h - wheel_dia/2])
                    cube([slot_w, pillar_w + 0.2, wheel_dia]);
            }
            // Metal roller wheel
            color("Silver")
            translate([0, 0, pillar_h - axle_h])
            rotate([0, 90, 0])
                cylinder(d=wheel_dia, h=wheel_w, center=true);
            // Axle pin
            color("DimGray")
            translate([0, 0, pillar_h - axle_h])
            rotate([0, 90, 0])
                cylinder(d=3, h=pillar_w + 2, center=true);
        }
    }
}

module carousel_plate() {
    // Rotating platform that sits on the 3 roller wheels
    carousel_dia = top_dia;  // same OD as barrel exterior (300mm)
    carousel_thickness = 3;
    // Roller wheel tops are at: bp_top - bottom_plate_thickness - pillar_h + (pillar_h - axle_h) + wheel_dia/2
    // = bp_top - bottom_plate_thickness - axle_h + wheel_dia/2
    // = base_z + total_height - 3 - 10 + 9 = base_z + total_height - 4
    carousel_z = base_z + total_height + 5;  // 5mm above barrel rim
    station_hole_dia = 78;
    center_bore = 30;
    color("LightGray")
    translate([0, 0, carousel_z])
    difference() {
        // Main plate (no gear ring — driven by exterior friction wheel)
        cylinder(d=carousel_dia, h=carousel_thickness);
        // 4 station openings
        for (i = [0:3]) {
            rotate([0, 0, station_angles[i]])
            translate([jar_center_r, 0, -0.1])
                cylinder(d=station_hole_dia, h=carousel_thickness + 0.2);
        }
        // Center bore
        translate([0, 0, -0.1])
            cylinder(d=center_bore, h=carousel_thickness + 0.2);
    }
}

// ==========================================
// BELT DRIVE — GT2 belt in 3D-printed segmented race
// around carousel perimeter, motor + pulley outside barrel
// ==========================================

// --- Pancake NEMA17 dimensions ---
pn17_face = 42.3;
pn17_body_len = 24;
pn17_pilot_d = 22;
pn17_pilot_h = 2;
pn17_shaft_d = 5;
pn17_shaft_len = 24;
pn17_bolt_spacing = 31;
pn17_bolt_d = 3.2;

// --- GT2 belt ---
belt_w = 6;                     // belt width
belt_t = 1.5;                   // belt thickness

// --- Carousel reference (vars defined at top of file) ---

// --- Belt race (3D printed, segmented) ---
// U-channel bolted to carousel plate underside at the rim
// Belt rides in the channel groove
race_num_segments = 8;          // 8 x 45-degree arc segments
race_groove_w = 5;              // 5mm wide spool groove for belt
race_wall_t = 2;                // groove hub wall thickness
race_flange_h = 1.5;            // spool flange thickness
race_total_h = race_flange_h + race_groove_w + race_flange_h;  // 8mm
race_mount_tab_w = 12;          // radial width of mounting tab (bolts to plate)
race_bolt_d = 3.2;              // M3 clearance
race_bolt_head_d = 5.7;         // M3 socket head

// Race hangs below carousel plate edge
// Top of race = carousel plate bottom
race_top_z = _carousel_plate_z;
race_inner_r = _carousel_r - race_wall_t;    // inner flange
race_outer_r = _carousel_r + race_wall_t;    // outer flange
race_groove_r = _carousel_r;                  // belt center radius

// Motor placement
dw_angle = 45;                  // between stations
dw_barrel_outer_r = top_dia / 2;  // 150mm

// --- Motor pulley ---
pulley_dia = 20;                // GT2 20T pulley on motor shaft
pulley_h = 8;                   // pulley height (flanged)
pulley_groove_dia = 16;         // pitch diameter

// Motor position: outside barrel, shaft vertical, pulley at belt race height
// Belt slot in barrel wall lets belt pass from race to pulley
dw_motor_r = dw_barrel_outer_r + pn17_face/2 + 5;  // motor center outside barrel

// --- Belt race segments ---
// Each segment is an arc with:
//   - Flat mounting tab on top (bolts to carousel plate underside)
//   - U-channel below (two flanges with groove between for belt)
//   - 2x M3 bolts per segment

module belt_race_segment(arc_deg) {
    // One segment of the belt race — spool profile
    // Two thin flanges (top and bottom) with a narrow groove between
    // Like a cable spool: wide flanges, narrow center
    seg_r = _carousel_r + br_leg_t + 2;  // outside the bracket vertical legs
    spool_flange_r = 4;         // flange extends 4mm beyond groove on each side
    spool_flange_t = 1.5;       // flange thickness (top and bottom)

    difference() {
        union() {
            // Top flange (wide disc, bolts to carousel plate)
            translate([0, 0, -spool_flange_t])
            rotate_extrude(angle=arc_deg, $fn=120)
            translate([seg_r - spool_flange_r, 0, 0])
                square([spool_flange_r * 2, spool_flange_t]);

            // Center groove hub (narrow, belt rides here)
            translate([0, 0, -spool_flange_t - race_groove_w])
            rotate_extrude(angle=arc_deg, $fn=120)
            translate([seg_r - race_wall_t, 0, 0])
                square([race_wall_t * 2, race_groove_w]);

            // Bottom flange (wide disc, keeps belt from falling off)
            translate([0, 0, -spool_flange_t - race_groove_w - spool_flange_t])
            rotate_extrude(angle=arc_deg, $fn=120)
            translate([seg_r - spool_flange_r, 0, 0])
                square([spool_flange_r * 2, spool_flange_t]);
        }

        // M3 bolt holes through top flange into carousel plate
        for (a = [arc_deg * 0.25, arc_deg * 0.75])
            rotate([0, 0, a])
            translate([seg_r, 0, -spool_flange_t - race_groove_w - spool_flange_t - 0.1])
                cylinder(d=race_bolt_d, h=spool_flange_t*2 + race_groove_w + 0.2);
    }
}

// --- L-brackets to mount race segments to carousel plate ---
// Small L-shaped brackets: vertical leg bolts to spool top flange,
// horizontal leg bolts to carousel plate underside
// 2 brackets per segment (at bolt positions)
br_leg_h = 8;                   // vertical leg height (gap from spool top to plate)
br_leg_w = 10;                  // bracket width (tangential)
br_leg_t = 2;                   // material thickness
br_bolt_d = 3.2;               // M3 clearance

module race_bracket() {
    // L-bracket: horizontal leg on top of carousel plate with M3 bolt holes,
    // vertical leg drops down outside carousel rim edge.
    // Race segments bolt to the vertical leg.
    difference() {
        union() {
            // Horizontal leg (sits on carousel plate top, bolted down)
            translate([-br_leg_t * 2, -br_leg_w/2, 0])
                cube([br_leg_t * 3, br_leg_w, br_leg_t]);
            // Vertical leg (drops down from outer edge of horizontal leg)
            translate([br_leg_t/2, -br_leg_w/2, -br_leg_h])
                cube([br_leg_t, br_leg_w, br_leg_h + br_leg_t]);
        }
        // Bolt hole through horizontal leg (down into carousel plate)
        translate([-br_leg_t/2, 0, -0.1])
            cylinder(d=br_bolt_d, h=br_leg_t + 0.2);
        // Bolt hole through vertical leg (race bolts from outside)
        translate([br_leg_t/2 - 0.1, 0, -br_leg_h/2])
            rotate([0, 90, 0])
            cylinder(d=br_bolt_d, h=br_leg_t + 0.2);
    }
}

module belt_race_assembly() {
    seg_arc = 360 / race_num_segments;  // 45 degrees each

    // L-brackets: horizontal leg on carousel plate top, vertical leg drops down outside edge
    // 2 per segment
    color("Silver")
    for (i = [0 : race_num_segments - 1]) {
        seg_start = i * seg_arc;
        for (a = [seg_arc * 0.25, seg_arc * 0.75])
            rotate([0, 0, seg_start + a])
            translate([_carousel_r, 0, _carousel_plate_z + _carousel_plate_t])
                race_bracket();
    }

    // Spool race segments — bolted to bracket vertical legs, hanging below plate
    color([0.3, 0.7, 0.9])  // light blue = 3D printed
    translate([0, 0, _carousel_plate_z + _carousel_plate_t])
    for (i = [0 : race_num_segments - 1])
        rotate([0, 0, i * seg_arc])
        belt_race_segment(seg_arc);
}

module belt_and_motor() {
    // --- Belt race on carousel ---
    belt_race_assembly();

    // --- Belt (simplified as a thin ring in the groove) ---
    color("DimGray")
    translate([0, 0, _carousel_plate_z - race_total_h + race_flange_h])
    difference() {
        cylinder(r=_carousel_r + belt_t/2, h=belt_w);
        translate([0, 0, -0.1])
            cylinder(r=_carousel_r - belt_t/2, h=belt_w + 0.2);
    }

    // --- Motor + pulley (outside barrel at dw_angle) ---
    rotate([0, 0, dw_angle]) {

        // Belt groove center Z
        _belt_z = _carousel_plate_z - race_total_h + race_flange_h + belt_w/2;

        // --- Pancake NEMA17 (vertical, shaft up, outside barrel) ---
        color([0.15, 0.15, 0.15])
        translate([dw_motor_r, 0, 0]) {
            // Motor body — bottom at a height so shaft reaches belt level
            translate([-pn17_face/2, -pn17_face/2,
                       _belt_z - pn17_shaft_len - pn17_pilot_h - pn17_body_len])
                cube([pn17_face, pn17_face, pn17_body_len]);
            // Pilot boss
            translate([0, 0, _belt_z - pn17_shaft_len - pn17_pilot_h])
                cylinder(d=pn17_pilot_d, h=pn17_pilot_h);
        }

        // --- Motor shaft ---
        color("Silver")
        translate([dw_motor_r, 0, _belt_z - pn17_shaft_len])
            cylinder(d=pn17_shaft_d, h=pn17_shaft_len);

        // --- Motor pulley (at belt height) ---
        color("Gold")
        translate([dw_motor_r, 0, _belt_z - pulley_h/2])
            cylinder(d=pulley_dia, h=pulley_h);

        // --- Belt run from race to pulley (simplified) ---
        // Two tangent lines from carousel race to motor pulley
        color("DimGray", 0.5)
        translate([0, 0, _belt_z - belt_w/2])
        linear_extrude(belt_w)
        difference() {
            hull() {
                circle(r=_carousel_r + belt_t);
                translate([dw_motor_r, 0])
                    circle(d=pulley_dia + belt_t*2);
            }
            hull() {
                circle(r=_carousel_r - 0.5);
                translate([dw_motor_r, 0])
                    circle(d=pulley_dia - 1);
            }
        }

        // --- Wall slot (where belt passes through barrel wall) ---
        color("Red", 0.15)
        translate([dw_barrel_outer_r - wall_thickness - 1,
                   -pulley_dia - 5,
                   _belt_z - belt_w/2 - 2])
            cube([wall_thickness + 2, pulley_dia*2 + 10, belt_w + 4]);

        // --- Rotation motor bracket (barrel-conforming saddle) ---
        // Curved saddle wraps barrel exterior, platform extends outward
        _rmb_saddle_thick = 4;
        _rmb_saddle_height = 65;
        _rmb_platform_thick = 5;
        _rmb_platform_len = 70;
        _rmb_platform_w = 55;
        _rmb_motor_plate_thick = 5;
        _rmb_motor_plate_w = pn17_face + 10;
        _rmb_motor_plate_l = pn17_face + 10;
        _rmb_motor_bottom = _belt_z - pn17_shaft_len - pn17_pilot_h - pn17_body_len;
        // Position saddle so platform+motor plate top aligns with motor bottom
        _rmb_platform_z_offset = 5;
        _rmb_saddle_bottom_z = _rmb_motor_bottom - _rmb_motor_plate_thick - _rmb_platform_thick - _rmb_platform_z_offset;
        _rmb_barrel_r = top_dia / 2;

        // Curved saddle shell (60° arc on barrel surface)
        color([0.6, 0.6, 0.65])
        translate([0, 0, _rmb_saddle_bottom_z])
        rotate([0, 0, -30])  // center 60° arc on motor position
        rotate_extrude(angle=60, $fn=120)
        translate([_rmb_barrel_r, 0, 0])
            square([_rmb_saddle_thick, _rmb_saddle_height]);

        // Motor platform (flat shelf extending outward from barrel)
        color([0.6, 0.6, 0.65])
        translate([_rmb_barrel_r, -_rmb_platform_w/2,
                   _rmb_saddle_bottom_z + _rmb_platform_z_offset])
            cube([_rmb_platform_len, _rmb_platform_w, _rmb_platform_thick]);

        // Gusset ribs (support platform from saddle)
        color([0.6, 0.6, 0.65])
        for (side = [-1, 1])
        translate([0, 0, _rmb_saddle_bottom_z + _rmb_platform_z_offset])
        hull() {
            translate([_rmb_barrel_r, side * (_rmb_platform_w/2 - 2), 0])
                cube([_rmb_saddle_thick, 4, 40]);
            translate([_rmb_barrel_r + _rmb_platform_len - 10,
                       side * (_rmb_platform_w/2 - 2), 0])
                cube([10, 4, _rmb_platform_thick]);
        }

        // Motor plate (slides on platform for tension)
        color([0.3, 0.7, 0.9])
        translate([_rmb_barrel_r + 15 + 10 - _rmb_motor_plate_l/2,
                   -_rmb_motor_plate_w/2,
                   _rmb_saddle_bottom_z + _rmb_platform_z_offset + _rmb_platform_thick])
            cube([_rmb_motor_plate_l, _rmb_motor_plate_w, _rmb_motor_plate_thick]);
    }
}

module exterior_drive() {
    belt_and_motor();
}

// ==========================================
// ASSEMBLY — natural Z-up orientation
// ==========================================

// Feet
tapered_feet();

// Base structure
color("DimGray") {
    tapered_shell();
    upper_basin();
    shelf_ring();
    bottom_plate();
}

// Cast aluminum interior details
casting_details();

// Roller wheel supports
roller_supports();

// Carousel plate (rotates on rollers)
carousel_plate();

// Exterior drive motor + wheel
exterior_drive();

// Center shaft + agitator mount + NEMA23 + Z-axis winch
center_shaft();
agitator_mount();
agit_cable_anchor();
agitator_nema23();
z_axis_assembly();

// Uncomment to show accessories:
// color("Black") heater_shroud();
// control_panel_features();
// glass_jars();

// ==========================================
// CAROUSEL TOP — jars and brackets
// (on top of carousel plate)
// ==========================================

// Jar brackets and jars sit on top of carousel plate
_carousel_z = _carousel_plate_z;
_carousel_h = _carousel_plate_t;

// 3 jar brackets — corner cradles
bracket_h = 25;
bracket_wall = 2;
bracket_z = _carousel_z + _carousel_h;
bracket_lip = 20;
bracket_gap = 1;

color("LightGray")
for (i = [0:2]) {
    rotate([0, 0, station_angles[i]])
    translate([jar_center_r, 0, bracket_z])
    rotate([0, 0, jar_cant]) {
        for (ca = [0, 180])
            rotate([0, 0, ca])
            translate([jar_size/2 + bracket_gap, jar_size/2 + bracket_gap, 0]) {
                translate([0, -bracket_lip, 0])
                    cube([bracket_wall, bracket_lip, bracket_h]);
                translate([-bracket_lip, 0, 0])
                    cube([bracket_lip, bracket_wall, bracket_h]);
                cylinder(r=bracket_wall, h=bracket_h);
                // Mounting ear +X
                translate([0, -bracket_lip, 0])
                difference() {
                    hull() {
                        cube([bracket_wall, bracket_wall, bracket_h]);
                        translate([bracket_wall + 4, bracket_wall/2, 0])
                            cylinder(d=8, h=bracket_h);
                    }
                    translate([bracket_wall + 4, bracket_wall/2, -0.1])
                        cylinder(d=3.2, h=bracket_h + 0.2);
                    translate([bracket_wall + 4, bracket_wall/2, bracket_h - 3])
                        cylinder(d=5.7, h=3.1);
                }
                // Mounting ear +Y
                translate([-bracket_lip, 0, 0])
                difference() {
                    hull() {
                        cube([bracket_wall, bracket_wall, bracket_h]);
                        translate([bracket_wall/2, bracket_wall + 4, 0])
                            cylinder(d=8, h=bracket_h);
                    }
                    translate([bracket_wall/2, bracket_wall + 4, -0.1])
                        cylinder(d=3.2, h=bracket_h + 0.2);
                    translate([bracket_wall/2, bracket_wall + 4, bracket_h - 3])
                        cylinder(d=5.7, h=3.1);
                }
            }
    }
}

// Glass jars in 3 stations (jar dimensions defined at top of file)

for (i = [0:2]) {
    rotate([0, 0, station_angles[i]])
    translate([jar_center_r, 0, bracket_z])
    rotate([0, 0, jar_cant]) {
        color("LightBlue", 0.3)
        difference() {
            union() {
                hull() {
                    rounded_square_extrude(jar_size - jar_base_r*2, jar_corner_r, 0.1);
                    translate([0, 0, jar_base_r])
                        rounded_square_extrude(jar_size, jar_corner_r, 0.1);
                }
                translate([0, 0, jar_base_r])
                    rounded_square_extrude(jar_size, jar_corner_r, jar_body_h);
                translate([0, 0, jar_base_r + jar_body_h])
                hull() {
                    linear_extrude(0.1)
                        offset(r=jar_corner_r)
                        square([jar_size - 2*jar_corner_r, jar_size - 2*jar_corner_r], center=true);
                    translate([0, 0, jar_taper_h])
                        cylinder(d=jar_mouth_dia, h=0.1);
                }
                translate([0, 0, jar_base_r + jar_body_h + jar_taper_h])
                    cylinder(d=jar_mouth_dia, h=jar_mouth_h);
            }
            translate([0, 0, jar_wall])
            union() {
                hull() {
                    rounded_square_extrude(jar_size - jar_base_r*2 - jar_wall*2, jar_corner_r, 0.1);
                    translate([0, 0, jar_base_r])
                        rounded_square_extrude(jar_size - jar_wall*2, jar_corner_r, 0.1);
                }
                translate([0, 0, jar_base_r])
                    rounded_square_extrude(jar_size - jar_wall*2, jar_corner_r, jar_body_h);
                translate([0, 0, jar_base_r + jar_body_h])
                hull() {
                    linear_extrude(0.1)
                        offset(r=jar_corner_r)
                        square([jar_size - jar_wall*2 - 2*jar_corner_r, jar_size - jar_wall*2 - 2*jar_corner_r], center=true);
                    translate([0, 0, jar_taper_h])
                        cylinder(d=jar_mouth_dia - jar_wall*2, h=0.1);
                }
                translate([0, 0, jar_base_r + jar_body_h + jar_taper_h])
                    cylinder(d=jar_mouth_dia - jar_wall*2, h=jar_mouth_h + 1);
            }
        }
        // Screw lid
        color("DimGray")
        translate([0, 0, jar_base_r + jar_body_h + jar_taper_h + jar_mouth_h])
            cylinder(d=jar_lid_dia, h=jar_lid_h);
    }
}

// Heater shroud at station 3 (270 deg)
color("DimGray")
rotate([0, 0, station_angles[3]])
translate([jar_center_r, 0, bracket_z])
difference() {
    cylinder(d=shroud_dia + shroud_wall*2, h=shroud_height);
    translate([0, 0, -0.1])
        cylinder(d=shroud_dia, h=shroud_height + 0.2);
    // Continuous inner lip/flange at base
    translate([0, 0, -0.1])
    difference() {
        cylinder(d=shroud_dia + shroud_wall*2 + 0.2, h=5);
        translate([0, 0, -0.1])
            cylinder(d=shroud_dia - 6, h=5.2);
    }
}

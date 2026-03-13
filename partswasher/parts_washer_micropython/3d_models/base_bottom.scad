// Parts Washer Base - Little Giant (L&R / E. Marshall Co.)
// Watchmaker's 4-station parts washer
// Modeled from photos: bottom view, depth measurement, front & side exterior
//
// Two-tier design:
//   - Upper shelf ring where 4 jar stations sit
//   - Tapered/angled side wall down to narrower bottom
//   - Control panel on front face
//   - Center shaft hole for agitation motor
//   - 4 station bays with divider walls
//   - Heater station has tall cylindrical shroud

$fn = 80;

// === Overall dimensions ===
top_dia = 330;              // ~13" outer diameter at shelf level
bottom_dia = 310;           // reduced taper — closer to top_dia for jar clearance
total_height = 89;          // ~3.5" from depth photo
wall_thickness = 2;         // sheet metal
shelf_width = 50;           // flat ring where jars sit
shelf_thickness = 3;        // shelf plate thickness
shelf_z = 55;               // shelf height from bottom (control panel below)
control_panel_height = 55;  // tapered section below shelf

// === Center shaft ===
center_hole_dia = 25;       // agitation shaft bore
center_tube_dia = 32;       // center tube OD
center_tube_height = 89;    // full height

// === Station layout (4 stations, 90 deg apart) ===
num_stations = 4;
jar_dia = 121;              // mason jar 4.75" (120.65mm)
jar_center_r = 90;          // far enough that 45°-rotated jars don't overlap adjacent stations
station_angles = [0, 90, 180, 270];  // WASH, RINSE1, RINSE2, HEATER

// === Divider walls ===
divider_height = 89;        // full height of basin
divider_thickness = 2;
divider_length = 75;        // radial length of divider
divider_inner_r = 45;       // start radius

// === Heater station shroud (station 3 = 270 deg) ===
shroud_dia = 121;           // cylindrical shroud inner dia — matches jar diameter
shroud_height = 140;        // 5.5 inches
shroud_wall = 2;

// === Control panel features ===
// Front face (0 degrees) - visible in exterior photos
toggle_switch_dia = 6;
knob_dia = 25;
knob_height = 15;

// === Bottom plate ===
bottom_plate_thickness = 3;

// === Tapered plastic feet ===
foot_dia_base = 14;         // narrow end (sits on table)
foot_dia_top = 22;          // wide end (attaches to base)
foot_height = 10;
foot_r = 155;               // radius from center — at outer rim edge
num_feet = 4;

// === Bottom plate spoke pattern (from bottom photo) ===
// Cast aluminum base has 3 wide radial spokes with 3 large
// kidney-shaped cutouts between them
num_spokes = 3;
spoke_width = 45;            // width of each radial spoke
spoke_angles = [0, 120, 240]; // 3 spokes at 120 deg apart
center_hub_dia = 65;         // central hub around shaft bore
spoke_outer_r = 130;         // spoke extends to near rim

// === Motor mount (bottom, from photo) ===
motor_mount_hole = 22;
motor_bolt_spacing = 31;    // NEMA17 pattern
motor_bolt_dia = 3.2;

// ==========================================
// MODULES
// ==========================================

module oval(length, width) {
    hull() {
        translate([-(length/2 - width/2), 0, 0]) circle(d=width);
        translate([ (length/2 - width/2), 0, 0]) circle(d=width);
    }
}

module tapered_shell() {
    // Outer tapered wall: wide at top (shelf), narrow at bottom
    difference() {
        hull() {
            translate([0, 0, control_panel_height])
                cylinder(d=top_dia, h=0.1);
            translate([0, 0, 0])
                cylinder(d=bottom_dia, h=0.1);
        }
        hull() {
            translate([0, 0, control_panel_height])
                cylinder(d=top_dia - wall_thickness*2, h=0.1);
            translate([0, 0, -0.1])
                cylinder(d=bottom_dia - wall_thickness*2, h=0.1);
        }
    }
}

module upper_basin() {
    // Vertical wall from shelf to top rim
    basin_h = total_height - control_panel_height;
    translate([0, 0, control_panel_height])
    difference() {
        cylinder(d=top_dia, h=basin_h);
        translate([0, 0, -0.1])
            cylinder(d=top_dia - wall_thickness*2, h=basin_h + 0.2);
    }
}

module shelf_ring() {
    // Flat ring where jars sit
    translate([0, 0, control_panel_height])
    difference() {
        cylinder(d=top_dia - wall_thickness*2, h=shelf_thickness);
        translate([0, 0, -0.1])
            cylinder(d=top_dia - shelf_width*2, h=shelf_thickness + 0.2);
        // Center hole
        translate([0, 0, -0.1])
            cylinder(d=center_hole_dia, h=shelf_thickness + 0.2);
    }
}

module bottom_plate() {
    // Cast aluminum base plate with 3 radial spokes and 3 large cutouts
    // The spokes radiate from a central hub to the outer rim
    difference() {
        // Full disc
        cylinder(d=bottom_dia, h=bottom_plate_thickness);

        // 3 large kidney-shaped cutouts between spokes
        for (i = [0:2]) {
            a = spoke_angles[i] + 60;  // midway between spokes
            rotate([0, 0, a])
            translate([0, 0, -0.1])
                linear_extrude(bottom_plate_thickness + 0.2)
                // Kidney shape: two overlapping circles at different radii
                hull() {
                    translate([55, 0, 0]) circle(d=50);
                    translate([105, 0, 0]) circle(d=55);
                }
        }

        // Center bore for motor shaft
        translate([0, 0, -0.1])
            cylinder(d=motor_mount_hole, h=bottom_plate_thickness + 0.2);

        // Motor bolt holes (NEMA17 pattern)
        for (dx = [-1, 1])
            for (dy = [-1, 1])
                translate([dx * motor_bolt_spacing/2, dy * motor_bolt_spacing/2, -0.1])
                    cylinder(d=motor_bolt_dia, h=bottom_plate_thickness + 0.2);
    }
}

module center_tube() {
    difference() {
        cylinder(d=center_tube_dia, h=center_tube_height);
        translate([0, 0, -0.1])
            cylinder(d=center_hole_dia, h=center_tube_height + 0.2);
    }
}

module divider_walls() {
    // 4 radial divider walls between stations
    for (i = [0:num_stations-1]) {
        a = station_angles[i] + 45;  // halfway between stations
        rotate([0, 0, a])
        translate([divider_inner_r + divider_length/2, -divider_thickness/2, 0])
            cube([divider_length, divider_thickness, divider_height]);
    }
}

module heater_shroud() {
    // Tall cylindrical shroud at heater station (270 deg)
    rotate([0, 0, 270])
    translate([jar_center_r, 0, control_panel_height + shelf_thickness])
    difference() {
        cylinder(d=shroud_dia + shroud_wall*2, h=shroud_height);
        translate([0, 0, -0.1])
            cylinder(d=shroud_dia, h=shroud_height + 0.2);
    }
}

module control_panel_features() {
    // Toggle switch - left (ONE WAY / OFF)
    rotate([0, 0, -30])
    translate([bottom_dia/2 + 1, 0, control_panel_height * 0.45])
    rotate([0, 90, 0]) {
        color("Silver") cylinder(d=12, h=3);  // base plate
        color("Silver") cylinder(d=3, h=12);  // toggle lever
    }

    // Speed knob - center
    rotate([0, 0, 0])
    translate([bottom_dia/2 + 1, 0, control_panel_height * 0.4])
    rotate([0, 90, 0]) {
        color("DimGray") cylinder(d=knob_dia, h=knob_height);
        color("Black") translate([0, 0, knob_height])
            cylinder(d=knob_dia - 4, h=2);
    }

    // Toggle switch - right (HEATER ON/OFF)
    rotate([0, 0, 30])
    translate([bottom_dia/2 + 1, 0, control_panel_height * 0.45])
    rotate([0, 90, 0]) {
        color("Silver") cylinder(d=12, h=3);
        color("Silver") cylinder(d=3, h=12);
    }

    // Oval badges / labels (decorative)
    rotate([0, 0, -30])
    translate([bottom_dia/2 + 0.5, 0, control_panel_height * 0.65])
    rotate([0, 90, 0])
        color("Silver") scale([1, 1.4, 1]) cylinder(d=18, h=1);

    rotate([0, 0, 30])
    translate([bottom_dia/2 + 0.5, 0, control_panel_height * 0.65])
    rotate([0, 90, 0])
        color("Silver") scale([1, 1.4, 1]) cylinder(d=18, h=1);
}

module glass_jars() {
    // Simplified glass jars in 3 stations (not heater)
    jar_height = 100;
    jar_wall = 3;
    for (i = [0:2]) {
        rotate([0, 0, station_angles[i]])
        translate([jar_center_r, 0, control_panel_height + shelf_thickness]) {
            color("LightBlue", 0.3)
            difference() {
                cylinder(d=jar_dia, h=jar_height);
                translate([0, 0, 3])
                    cylinder(d=jar_dia - jar_wall*2, h=jar_height);
            }
            // Black lid
            color("DimGray")
            translate([0, 0, jar_height])
                cylinder(d=jar_dia + 4, h=8);
        }
    }
}

module center_shaft() {
    // Agitation shaft from motor head
    shaft_dia = 10;
    shaft_height = 200;
    color("Silver")
    translate([0, 0, 0])
        cylinder(d=shaft_dia, h=shaft_height);
}

module tapered_feet() {
    // Round tapered hard plastic feet
    color("Black")
    for (i = [0:num_feet-1])
        rotate([0, 0, i * 360/num_feet + 45])
        translate([foot_r, 0, -foot_height])
            cylinder(d1=foot_dia_base, d2=foot_dia_top, h=foot_height);
}

module carousel_plate() {
    // Rotating platform that sits on the 3 roller wheels
    // Has 4 station openings for jars and a center hole for agitation shaft
    carousel_dia = 250;         // fits inside the base, rides on rollers
    carousel_thickness = 3;     // stamped sheet metal
    carousel_z = bottom_plate_thickness + 12;  // sits on top of roller wheels (axle_h + wheel radius)
    station_hole_dia = 78;      // opening for jar/basket to pass through
    center_bore = 30;           // center hole for shaft and bearing
    // Outer gear ring for belt drive
    gear_ring_h = 8;
    gear_ring_w = 6;

    color("LightGray")
    translate([0, 0, carousel_z])
    difference() {
        union() {
            // Main plate
            cylinder(d=carousel_dia, h=carousel_thickness);
            // Outer gear/belt ring (raised lip around perimeter)
            difference() {
                cylinder(d=carousel_dia, h=carousel_thickness + gear_ring_h);
                translate([0, 0, -0.1])
                    cylinder(d=carousel_dia - gear_ring_w*2, h=carousel_thickness + gear_ring_h + 0.2);
            }
        }

        // 4 station openings at 90 deg intervals
        for (i = [0:3]) {
            rotate([0, 0, station_angles[i]])
            translate([jar_center_r, 0, -0.1])
                cylinder(d=station_hole_dia, h=carousel_thickness + gear_ring_h + 0.2);
        }

        // Center bore for agitation shaft
        translate([0, 0, -0.1])
            cylinder(d=center_bore, h=carousel_thickness + gear_ring_h + 0.2);
    }

    // 4 radial divider walls between stations (welded to plate)
    color("LightGray")
    translate([0, 0, carousel_z + carousel_thickness])
    for (i = [0:3]) {
        a = station_angles[i] + 45;  // halfway between stations
        rotate([0, 0, a])
        translate([divider_inner_r, -divider_thickness/2, 0])
            cube([divider_length, divider_thickness, divider_height - carousel_z - carousel_thickness]);
    }
}

module roller_supports() {
    // Carousel roller/wheel supports — cast into the spoke ends
    // Each spoke has a raised pillar with an axle and small metal wheel
    roller_r = 130;             // radius from center — at spoke outer edge near rim
    pillar_w = 20;              // width of cast pillar
    pillar_l = 12;              // depth (radial)
    pillar_h = 15;              // height above bottom plate
    wheel_dia = 18;             // small metal roller wheel
    wheel_w = 6;
    axle_h = 10;                // wheel center height above base
    slot_w = 8;                 // slot in pillar for wheel

    for (i = [0:2]) {
        rotate([0, 0, spoke_angles[i]])
        translate([roller_r, 0, bottom_plate_thickness]) {
            // Cast pillar (integral with spoke)
            color("DimGray")
            difference() {
                translate([-pillar_l/2, -pillar_w/2, 0])
                    cube([pillar_l, pillar_w, pillar_h]);
                // Slot for wheel (radial slot so wheel fits)
                translate([-slot_w/2, -pillar_w/2 - 0.1, axle_h - wheel_dia/2])
                    cube([slot_w, pillar_w + 0.2, wheel_dia]);
            }
            // Metal roller wheel — axle points radially (toward center)
            // so wheel spins tangentially for carousel rotation
            color("Silver")
            translate([0, 0, axle_h])
            rotate([0, 90, 0])
                cylinder(d=wheel_dia, h=wheel_w, center=true);
            // Axle pin
            color("DimGray")
            translate([0, 0, axle_h])
            rotate([0, 90, 0])
                cylinder(d=3, h=pillar_w + 2, center=true);
        }
    }
}

module casting_details() {
    // All raised features on the cast aluminum bottom plate
    // (visible from underside when flipped)
    // Using lighter "Silver" color so details stand out from base

    // --- Raised center hub / motor boss ---
    // Thick ring around the shaft bore, raised ~10mm above plate
    hub_h = 10;
    color("Silver")
    translate([0, 0, bottom_plate_thickness])
    difference() {
        cylinder(d=center_hub_dia, h=hub_h);
        translate([0, 0, -0.1])
            cylinder(d=motor_mount_hole, h=hub_h + 0.2);
        // Motor bolt holes through hub
        for (dx = [-1, 1])
            for (dy = [-1, 1])
                translate([dx * motor_bolt_spacing/2, dy * motor_bolt_spacing/2, -0.1])
                    cylinder(d=motor_bolt_dia, h=hub_h + 0.2);
    }

    // --- Spoke reinforcement ribs ---
    // Raised ridge running along center of each spoke
    rib_w = 14;
    rib_h = 7;
    rib_inner_r = center_hub_dia/2;
    rib_outer_r = spoke_outer_r - 5;
    color("Silver")
    for (i = [0:2]) {
        rotate([0, 0, spoke_angles[i]])
        translate([0, 0, bottom_plate_thickness])
        // Tapered rib: wider at hub, narrower at rim
        hull() {
            translate([rib_inner_r, -rib_w/2, 0])
                cube([1, rib_w, rib_h]);
            translate([rib_outer_r, -rib_w*0.5/2, 0])
                cube([1, rib_w*0.5, rib_h * 0.4]);
        }
    }

    // --- Gussets where spokes meet center hub ---
    // Triangular fillets for strength
    gusset_h = 8;
    color("Silver")
    for (i = [0:2]) {
        for (side = [-1, 1]) {
            rotate([0, 0, spoke_angles[i] + side * 20])
            translate([center_hub_dia/2 - 3, -6, bottom_plate_thickness])
            hull() {
                cube([3, 12, gusset_h]);
                translate([15, side > 0 ? 4 : -4, 0])
                    cube([2, 4, 1]);
            }
        }
    }

    // --- Foot mounting bosses ---
    // Cylindrical columns from plate to rim, clipped to outer shell profile
    foot_boss_dia = 30;
    foot_bolt_dia = 6;
    foot_boss_h = total_height - bottom_plate_thickness;
    color("Silver")
    intersection() {
        // Clip to outer shell envelope (tapered + upper basin)
        union() {
            hull() {
                translate([0, 0, control_panel_height])
                    cylinder(d=top_dia, h=0.1);
                cylinder(d=bottom_dia, h=0.1);
            }
            translate([0, 0, control_panel_height])
                cylinder(d=top_dia, h=total_height - control_panel_height);
        }
        // The 4 boss cylinders
        for (i = [0:num_feet-1])
            rotate([0, 0, i * 360/num_feet + 45])
            translate([foot_r, 0, bottom_plate_thickness])
            difference() {
                cylinder(d=foot_boss_dia, h=foot_boss_h);
                translate([0, 0, -0.1])
                    cylinder(d=foot_bolt_dia, h=foot_boss_h + 0.2);
            }
    }

    // --- Component mounting pads ---
    // Raised rectangular pads on spokes for electrical components
    pad_h = 5;
    color("Silver") {
        // Two toggle switch mounts (on spoke 0)
        rotate([0, 0, spoke_angles[0]])
        translate([70, -14, bottom_plate_thickness])
            cube([22, 12, pad_h]);
        rotate([0, 0, spoke_angles[0]])
        translate([70, 3, bottom_plate_thickness])
            cube([22, 12, pad_h]);

        // Transformer/capacitor mount (on spoke 1)
        rotate([0, 0, spoke_angles[1]])
        translate([55, -18, bottom_plate_thickness])
            cube([35, 36, pad_h]);

        // Motor capacitor mount (on spoke 2)
        rotate([0, 0, spoke_angles[2]])
        translate([65, -12, bottom_plate_thickness])
            cube([28, 24, pad_h]);
    }

    // --- Outer rim lip ---
    // Thickened edge where bottom plate meets tapered shell wall
    rim_lip_h = 6;
    rim_lip_w = 8;
    color("Silver")
    translate([0, 0, bottom_plate_thickness])
    difference() {
        cylinder(d=bottom_dia, h=rim_lip_h);
        translate([0, 0, -0.1])
            cylinder(d=bottom_dia - rim_lip_w*2, h=rim_lip_h + 0.2);
        // Cut away where the 3 openings are
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

// ==========================================
// ASSEMBLY (flipped — bottom plate on top, rim below)
// ==========================================

// Flip entire model 180 deg around X axis, then shift up so
// the rim sits at z=0 and the bottom plate faces up
translate([0, 0, total_height])
rotate([180, 0, 0]) {

    color("DimGray") {
        tapered_shell();
        upper_basin();
        shelf_ring();
        bottom_plate();
        center_tube();
        // divider_walls();
    }

    // Cast aluminum details: hub boss, ribs, foot bosses, mount pads, rim lip
    casting_details();

    // Roller wheel supports cast into spoke ends
    roller_supports();

    // Uncomment to show accessories:
    // color("Black") heater_shroud();
    // control_panel_features();
    // glass_jars();
    // center_shaft();

} // end flip

// Carousel plate + jars — on TOP of the flipped base
// After flip: bottom plate is at z=total_height, rim at z=0
// The shelf ring (where carousel sits) is at z = total_height - control_panel_height
// in flipped coords. Place carousel just above the top surface.
carousel_top_z = total_height + 1;  // just above the bottom plate surface
carousel_h = 3;
gear_ring_h = 8;

color("LightGray")
translate([0, 0, carousel_top_z])
difference() {
    union() {
        // Main plate
        cylinder(d=bottom_dia, h=carousel_h);
        // Gear/belt ring hangs below the plate
        translate([0, 0, -gear_ring_h])
        difference() {
            cylinder(d=bottom_dia, h=gear_ring_h);
            translate([0, 0, -0.1])
                cylinder(d=bottom_dia - 12, h=gear_ring_h + 0.2);
        }
    }
    // Heater station cutout only (station 3 = 270 deg)
    rotate([0, 0, station_angles[3]])
    translate([jar_center_r, 0, -gear_ring_h - 0.1])
        cylinder(d=78, h=carousel_h + gear_ring_h + 0.2);
    // Center bore
    translate([0, 0, -gear_ring_h - 0.1])
        cylinder(d=30, h=carousel_h + gear_ring_h + 0.2);
}

// 3 jar brackets — arc-shaped cradles around base of each jar (not heater)
bracket_h = 25;             // bracket wall height
bracket_wall = 2;           // bracket thickness
bracket_arc = 120;          // degrees of arc on each side of jar center
bracket_z = carousel_top_z + carousel_h;  // directly on top of plate
leg_w = 10;                 // mounting leg width
leg_t = bracket_wall;       // leg thickness (same as bracket wall)
leg_h = 0;                  // no gap — bracket sits on plate
color("LightGray")
for (i = [0:2]) {
    rotate([0, 0, station_angles[i]])
    translate([jar_center_r, 0, 0]) {
        // Bracket arcs
        translate([0, 0, bracket_z])
        difference() {
            cylinder(d=jar_dia + bracket_wall*2 + 2, h=bracket_h);
            // Hollow out center
            translate([0, 0, -0.1])
                cylinder(d=jar_dia + 2, h=bracket_h + 0.2);
            // Cut away to leave two opposing arc segments (rotated 180° around jar)
            for (cut_a = [90, 270])
                rotate([0, 0, cut_a + bracket_arc/2])
                translate([0, 0, -0.1])
                    linear_extrude(bracket_h + 0.2)
                    polygon([
                        [0, 0],
                        [jar_dia, 0],
                        [jar_dia * cos(180 - bracket_arc), jar_dia * sin(180 - bracket_arc)],
                    ]);
        }
        // (no legs needed — bracket sits directly on plate)
    }
}

// Glass jars in 3 stations (not heater) — on top of carousel
jar_wall = 3;
jar_height = 165;           // 6.5 inches
for (i = [0:2]) {
    rotate([0, 0, station_angles[i]])
    translate([jar_center_r, 0, carousel_top_z + carousel_h]) {
        color("LightBlue", 0.3)
        difference() {
            cylinder(d=jar_dia, h=jar_height);
            translate([0, 0, 3])
                cylinder(d=jar_dia - jar_wall*2, h=jar_height);
        }
        // Black lid
        color("DimGray")
        translate([0, 0, jar_height])
            cylinder(d=jar_dia + 4, h=8);
    }
}

// Heater shroud at station 3 (270 deg) — sits on carousel at cutout
rotate([0, 0, station_angles[3]])
translate([jar_center_r, 0, carousel_top_z + carousel_h]) {
    color("DarkGray")
    difference() {
        cylinder(d=shroud_dia + shroud_wall*2, h=shroud_height);
        translate([0, 0, -0.1])
            cylinder(d=shroud_dia, h=shroud_height + 0.2);
    }
}

// Center agitation shaft — extends up through jars
color("Silver")
translate([0, 0, carousel_top_z])
    cylinder(d=center_tube_dia - 1, h=(jar_height + carousel_h + 20) * 2);

// Washer head — slides on center shaft, arm extends to basket
head_collar_od = center_tube_dia + 10;  // collar around center tube
head_collar_h = 63.5;                    // collar height
head_arm_dia = 10;                       // arm tube diameter
head_arm_length = jar_center_r - head_collar_od/2 - 5;  // reaches to jar center
basket_dia = jar_dia - 20;              // basket fits inside jar
basket_h = jar_height - 30;            // shorter than jar
basket_wall = 2;
shaft_height = (jar_height + carousel_h + 20) * 2;
shaft_top = carousel_top_z + shaft_height;
head_z = shaft_top - head_collar_h;  // top of shaft

color("OrangeRed")
translate([0, 0, head_z]) {
    // Collar (rides on center tube)
    difference() {
        cylinder(d=head_collar_od, h=head_collar_h);
        translate([0, 0, -0.1])
            cylinder(d=center_tube_dia + 0.5, h=head_collar_h + 0.2);
    }

    // Radial arm — extends from collar to basket position at station 0
    translate([head_collar_od/2 - 2, 0, head_collar_h/2])
        rotate([0, 90, 0])
        cylinder(d=head_arm_dia, h=head_arm_length);

    // Basket (wire mesh cylinder at station 0 position)
    translate([jar_center_r, 0, -20]) {
        color("DimGray")
        difference() {
            cylinder(d=basket_dia, h=basket_h);
            translate([0, 0, basket_wall])
                cylinder(d=basket_dia - basket_wall*2, h=basket_h);
        }
        // Basket bottom (mesh plate)
        color("DimGray")
        cylinder(d=basket_dia, h=basket_wall);
    }
}

// ==========================================
// MOTOR MOUNT ASSEMBLY (at top of center tube)
// ==========================================
// NEMA23 motor mount bracket + NEMA23 motor

// --- NEMA23 Motor Mount Bracket ---
// From dimensioned drawing: right-angle aluminum bracket
bracket_flange = 54.7;       // Top flange square dimension
bracket_bolt_spacing = 47;   // Bolt pattern center-to-center
bracket_bolt_d = 5.5;        // Bolt hole diameter
bracket_pilot_d = 42;        // Top face pilot bore
bracket_bore_d = 29;         // Through bore diameter
bracket_body_h = 31.77;      // Body height below flange
bracket_body_w = 40;         // Body width/depth
bracket_step_h = 5;          // Bottom step/flange height
bracket_step_bore_d = 33;    // Bottom counterbore diameter
bracket_front_bore_d = 29;   // Front face bore
bracket_total_h = bracket_body_h + bracket_step_h;  // ~36.77mm

bracket_z = shaft_top;  // Sits on top of center shaft

// Bracket body (centered on shaft)
color([0.75, 0.75, 0.78])  // Machined aluminum
translate([0, 0, bracket_z]) {
    difference() {
        union() {
            // Top flange plate
            translate([-bracket_flange/2, -bracket_flange/2, bracket_body_h])
                cube([bracket_flange, bracket_flange, bracket_step_h]);

            // Main body block
            translate([-bracket_body_w/2, -bracket_body_w/2, 0])
                cube([bracket_body_w, bracket_body_w, bracket_body_h]);
        }

        // Through bore (vertical, for motor shaft)
        cylinder(d=bracket_bore_d, h=bracket_total_h);

        // Top face pilot bore (shallow recess in flange)
        translate([0, 0, bracket_body_h])
            cylinder(d=bracket_pilot_d, h=bracket_step_h);

        // Bottom counterbore
        translate([0, 0, -0.1])
            cylinder(d=bracket_step_bore_d, h=bracket_step_h + 0.1);

        // Front face bore (for output/coupling access)
        translate([0, -bracket_body_w/2 - 0.1, bracket_body_h/2])
            rotate([-90, 0, 0])
            cylinder(d=bracket_front_bore_d, h=bracket_body_w + 0.2);

        // 4 corner bolt holes (through flange)
        for (x = [-1, 1]) for (y = [-1, 1])
            translate([x * bracket_bolt_spacing/2,
                       y * bracket_bolt_spacing/2,
                       bracket_body_h])
                cylinder(d=bracket_bolt_d, h=bracket_step_h + 0.1);

        // 4 corner bolt holes (through body)
        for (x = [-1, 1]) for (y = [-1, 1])
            translate([x * bracket_bolt_spacing/2,
                       y * bracket_bolt_spacing/2,
                       -0.1])
                cylinder(d=bracket_bolt_d, h=bracket_body_h + 0.2);
    }
}

// --- NEMA23 Motor ---
// Mounted on top of bracket flange, shaft pointing down through bore
nema23_body_dia = 57;        // NEMA23 round body (56.4mm nom)
nema23_body_len = 56;        // Motor body length
nema23_shaft_d = 6.35;       // 1/4" shaft
nema23_shaft_len = 24;       // Shaft protrusion
nema23_pilot_d = 38.1;       // Pilot/register diameter
nema23_pilot_h = 1.6;        // Pilot protrusion

motor_z = bracket_z + bracket_total_h;  // Motor sits on top of flange

// Motor body (dark gray, octagonal approximated as cylinder)
color([0.2, 0.2, 0.2])
translate([0, 0, motor_z]) {
    // Pilot ring
    cylinder(d=nema23_pilot_d, h=nema23_pilot_h);
    // Body
    translate([0, 0, nema23_pilot_h])
        cylinder(d=nema23_body_dia, h=nema23_body_len, $fn=8);
    // Rear cap
    translate([0, 0, nema23_pilot_h + nema23_body_len])
        cylinder(d=nema23_body_dia - 4, h=3);
}

// Motor shaft (extends down through bracket bore)
color("Silver")
translate([0, 0, motor_z - nema23_shaft_len])
    cylinder(d=nema23_shaft_d, h=nema23_shaft_len);

// ==========================================
// Z-AXIS CABLE WINCH ASSEMBLY (at top of center tube)
// ==========================================
// From top_motor_mount.scad, cable_spool.scad, motor_cover.scad
// NEMA17 motor drives cable spool to raise/lower washer head

// Mount geometry
z_plug_len = 50;
z_tube_ext = 50;
z_wire_gap = 12;
z_flange_thick = 5;
z_platform_thick = 5;
z_platform_w = 50;
z_platform_d = 50;
z_wall_h = 50;
z_wall_thick = 5;
z_corner_r = 8;

// Spool positioning
z_spool_w = 15;
z_spool_clearance = 2;
z_motor_wall_inner = -(z_spool_w/2 + z_spool_clearance);
z_motor_wall_outer = z_motor_wall_inner - z_wall_thick;
z_bearing_wall_inner = z_spool_w/2 + z_spool_clearance;
z_bearing_wall_outer = z_bearing_wall_inner + z_wall_thick;

// Z positions relative to shaft top
z_base_z = shaft_top;
z_flange_z = z_base_z + z_tube_ext;
z_skirt_z = z_flange_z + z_flange_thick;
z_plat_z = z_skirt_z + z_wire_gap;
z_wall_base_z = z_plat_z + z_platform_thick;
z_shaft_z = z_wall_base_z + z_wall_h / 2;

// NEMA17 motor dimensions
nema17_size = 42.3;
nema17_length = 40;

// Spool dimensions
spool_flange_od = 32;
spool_core_od = 20;

// 625ZZ bearing
z_bearing_od = 16;
z_bearing_boss_od = z_bearing_od + 6;
z_bearing_boss_len = 8;

// Cable guide position
cable_guide_y = -(center_tube_dia/2 + 1);

// --- Tube extension ---
color("CornflowerBlue")
translate([0, 0, z_base_z])
difference() {
    cylinder(d=center_tube_dia, h=z_tube_ext);
    cylinder(d=15, h=z_tube_ext);
}

// --- Flange ---
color("CornflowerBlue")
translate([0, 0, z_flange_z])
difference() {
    cylinder(d=center_tube_dia + 12, h=z_flange_thick);
    cylinder(d=15, h=z_flange_thick);
}

// --- Support skirt (270° partial cylinder) ---
color("CornflowerBlue")
translate([0, 0, z_skirt_z])
difference() {
    cylinder(d=center_tube_dia + 12, h=z_wire_gap);
    cylinder(d=center_hole_dia + 2, h=z_wire_gap);
    // 90° wire exit opening
    rotate([0, 0, -45])
    translate([0, 0, -0.5])
        cube([center_tube_dia + 12, center_tube_dia + 12, z_wire_gap + 1]);
}

// --- Platform (rounded rectangle) ---
color("CornflowerBlue")
translate([0, 0, z_plat_z])
hull() {
    for (x = [-z_platform_w/2 + z_corner_r, z_platform_w/2 - z_corner_r])
        for (y = [-z_platform_d/2 + z_corner_r, z_platform_d/2 - z_corner_r])
            translate([x, y, 0])
                cylinder(r=z_corner_r, h=z_platform_thick);
}

// --- Cable fairlead ---
color("CornflowerBlue")
translate([0, cable_guide_y, z_plat_z + z_platform_thick]) {
    cylinder(d=10, h=10);
    translate([0, 0, 7])
        cylinder(d1=10, d2=16, h=3);
}

// --- Frame walls ---
color("CornflowerBlue") {
    // Motor wall (left)
    translate([z_motor_wall_outer, -z_platform_d/2, z_wall_base_z])
        cube([z_wall_thick, z_platform_d, z_wall_h]);
    // Bearing wall (right)
    translate([z_bearing_wall_inner, -z_platform_d/2, z_wall_base_z])
        cube([z_wall_thick, z_platform_d, z_wall_h]);
    // Bearing boss
    translate([z_bearing_wall_outer, 0, z_shaft_z])
        rotate([0, 90, 0])
        cylinder(d=z_bearing_boss_od, h=z_bearing_boss_len);
}

// --- NEMA17 Motor ---
color("DimGray")
translate([z_motor_wall_outer, 0, z_shaft_z])
rotate([0, -90, 0])
translate([-nema17_size/2, -nema17_size/2, 0])
    cube([nema17_size, nema17_size, nema17_length]);
// Motor shaft
color("Silver")
translate([z_motor_wall_outer, 0, z_shaft_z])
rotate([0, 90, 0])
    cylinder(d=5, h=z_spool_w + z_spool_clearance*2 + z_wall_thick*2);

// --- Cable spool ---
color("Orange")
translate([-z_spool_w/2, 0, z_shaft_z])
rotate([0, 90, 0]) {
    // Left flange
    cylinder(d=spool_flange_od, h=2.5);
    // Core
    translate([0, 0, 2.5])
        cylinder(d=spool_core_od, h=10);
    // Right flange
    translate([0, 0, 12.5])
        cylinder(d=spool_flange_od, h=2.5);
}

// --- 625ZZ Bearing ---
color("Silver")
translate([z_bearing_wall_outer, 0, z_shaft_z])
rotate([0, 90, 0])
difference() {
    cylinder(d=z_bearing_od, h=5);
    cylinder(d=5, h=5);
}

// --- Motor cover (semi-transparent) ---
z_env_left = z_motor_wall_outer - nema17_length - 2;
z_env_right = z_bearing_wall_outer + z_bearing_boss_len + 2;
z_env_front = -(z_platform_d/2 + 2);
z_env_back = z_platform_d/2 + 2;
z_env_h = z_wall_h + 5;

color("LimeGreen", 0.25)
translate([0, 0, z_wall_base_z])
hull() {
    for (x = [z_env_left + z_corner_r, z_env_right - z_corner_r])
        for (y = [z_env_front + z_corner_r, z_env_back - z_corner_r]) {
            translate([x, y, 0])
                cylinder(r=z_corner_r, h=0.1);
            translate([x, y, z_env_h - z_corner_r])
                sphere(r=z_corner_r);
        }
}

// --- Cable (from spool down to washer head) ---
color("DarkGray")
hull() {
    translate([0, cable_guide_y, z_plat_z + z_platform_thick + 10])
        sphere(d=1.5);
    translate([0, cable_guide_y, head_z + head_collar_h/2])
        sphere(d=1.5);
}

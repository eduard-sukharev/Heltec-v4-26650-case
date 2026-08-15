"""
Parametric CadQuery case for a Heltec V4 board (ESP32-S3, no GPS variant),
IPEX-to-SMA antenna pigtail, and a 26650 Li-ion cell.

Three-piece design:
  - BASE half:      battery tub -- cradle plus a straight rectangular shaft
                     so the cell drops in vertically. Carries no board
                     features.
  - PLATE half:      face plate with the OLED window; carries a wide
                     registration shoulder the board's top face rests
                     against, plus the mounting bosses for the retainer.
  - RETAINER plank:  a separate printed part, screwed to the plate after the
                     board is set on the shoulder. Presses up against the
                     GPS and battery/solar connector housings on the
                     board's underside to keep it from falling back out.

The cell lies along the case's long axis, centred directly *underneath* the
board. Because the cell is both wider and longer than the board, anything
supporting the board from the base would stand inside the cell's insertion
path -- so the board hangs from the plate instead. See README.md.

Board dimensions come from a Heltec mechanical reference drawing; some
component heights are still estimates -- see README.md.

Usage:
    python3 case.py       # export STL/STEP of all three printed parts, plus
                           # a coloured STEP/STL/glTF assembly (base, plate,
                           # retainer, cell, board, SMA) for viewing
    python3 verify.py     # collision / fit / insertion-path checks
"""

import cadquery as cq
from cadquery import exporters
import math
import os

# ---------------------------------------------------------------------------
# CONFIG -- all measurements in millimetres
# ---------------------------------------------------------------------------

# --- Heltec V4 board -------------------------------------------------------
# Outline and PCB thickness are measured directly off reference/heltec_v4_top.JPG
# and reference/heltec_v4_side.JPG (own board, hand-annotated). Everything
# else not called out there is still marked (est).
BOARD_L = 51.0            # board length, along the cell axis (measured, excl. antenna nub)
BOARD_W = 25.6            # board width (measured)
BOARD_T = 1.6             # PCB thickness (measured)
BOARD_CORNER_CHAMFER = 2.0   # angled corners shown on the drawing
BOARD_CLEARANCE = 0.4    # slack around the board footprint

# No mounting holes anywhere on the board (confirmed against
# reference/heltec_v4_top.JPG -- the USB-C end is just header pins, two
# tactile buttons and the connector). The board is retained by a rail/lip
# channel in the plate instead -- see RAIL_* below.

# OLED module. Active width 27.28 and module width 33.28 are dimensioned;
# module height 18.56 is taken from the drawing's side view. Active height
# is derived from a 128x64 panel at the dimensioned active width.
OLED_ACTIVE_W = 27.28
OLED_ACTIVE_H = OLED_ACTIVE_W * 64.0 / 128.0    # = 13.64
OLED_MODULE_W = 33.28
OLED_MODULE_H = 18.56
OLED_MODULE_THICK = 5.6      # module height above the PCB top face, measured
                              # -- taller than every other top-side
                              # component, so it's deliberately excluded
                              # from PLATE_INNER_H (see below): rather than
                              # sizing the ceiling to clear it with a gap,
                              # the module pokes straight through its own
                              # window cutout and out past the top wall.
                              # See "Why the ceiling no longer clears the
                              # OLED module" in README.md.
OLED_WINDOW_MARGIN = 0.6     # window opens this much larger than the module, all
                              # round, so the whole module (frame + corner screws)
                              # can show through -- not just the active glass.
OLED_WINDOW_W = OLED_MODULE_W + 2 * OLED_WINDOW_MARGIN
OLED_WINDOW_H = OLED_MODULE_H + 2 * OLED_WINDOW_MARGIN
# Module sits toward the u.FL (-X) end, ~1mm in from that board edge. Cross-
# checked against the top-view photo's own directly-dimensioned "17.5mm, USB
# edge to OLED module edge" callout, which lines up with this formula to
# within <1mm -- the module already sits as close to the button/USB-C end as
# the real board allows, so no extra positioning logic is needed here.
OLED_MODULE_EDGE_GAP = 1.0
OLED_CENTER_X = -(BOARD_L / 2 - OLED_MODULE_EDGE_GAP) + OLED_MODULE_W / 2
OLED_CENTER_Y = 0.0

# USB-C connector, centred on the +X short edge, sitting on the PCB top face
USB_W = 9.0
USB_H = 3.3              # connector body height above the PCB, measured --
                          # now the tallest top-side component the ceiling
                          # actually has to clear (see OLED_MODULE_THICK)
USB_DEPTH = 7.0          # (est) how far the body extends onto the board
USB_OVERHANG = 1.0       # how far it protrudes past the board edge

# u.FL / IPEX antenna connector, near the -X end of the board
UFL_SIZE = 3.0
UFL_H = 1.6              # (est) height above the PCB
UFL_FROM_END = 4.0       # centre distance from the -X board edge

# Two SMD tactile buttons (silkscreened PRG/boot and RST), alongside the
# USB-C connector, top-mounted like the OLED/USB-C/u.FL. Size measured off
# reference/heltec_v4_top.JPG (pixel-calibrated against its own hand-drawn
# calipers) and reference/heltec_v4_side.JPG (component height); position
# measured directly off the board.
BUTTON_W = 4.3            # X footprint (along board length)
BUTTON_D = 3.1            # Y footprint (across board width)
BUTTON_H = 2.5            # height above the PCB top face
BUTTON_EDGE_GAP_X = 4.8   # board's +X (USB-C) edge -> button centre
BUTTON_Y = 8.15           # off centreline -- both buttons share this, mirrored

# IPEX-to-SMA pigtail: bulkhead SMA jack, from its own datasheet (measured,
# not estimated). Front to back: an externally-threaded barrel (what passes
# through the panel and receives the mating connector's nut), then a nut
# fixed (swaged) at the barrel's base so it can't back off, then a washer,
# then the stiff coax stub before the flexible pigtail cable begins.
SMA_THREAD_MAJOR_MIN = 6.19  # 1/4-36 UNS-2A thread major diameter, min
SMA_THREAD_MAJOR_MAX = 6.33  # ... max -- use max for hole/clearance sizing
SMA_BARREL_L = 13.0          # threaded barrel length
SMA_NUT_AF = 8.0              # fixed nut, across flats
SMA_NUT_T = 2.0                # fixed nut thickness
SMA_WASHER_OD = 9.5           # (est) washer OD -- not dimensioned on the
                                # datasheet; estimated a bit past the nut's
                                # own corner-to-corner distance (AF/cos(30)
                                # = 9.24mm for an 8mm hex), since a washer
                                # narrower than the nut it backs couldn't
                                # actually contact it
SMA_WASHER_T = 2.0             # washer thickness
SMA_PIGTAIL_D = 4.0           # stiff coax stub diameter
SMA_PIGTAIL_L = 13.0          # stiff coax stub length, before the flexible
                                # cable takes over
SMA_HOLE_CLEARANCE = 0.3      # clearance hole around the barrel's max major
                                # diameter, so the (unthreaded) panel hole
                                # doesn't bind on the thread crest
SMA_HOLE_D = SMA_THREAD_MAJOR_MAX + SMA_HOLE_CLEARANCE
# Widest cross-section the connector presents to the case -- the washer --
# governs how much clear footprint the mount needs.
SMA_FOOTPRINT_D = SMA_WASHER_OD

# --- 26650 cell -------------------------------------------------------------
CELL_D = 26.7             # actual cell diameter incl. wrap (measured, 26.7+/-0.2 on the label)
CELL_L = 65.2             # actual cell length (measured, 65.2+/-0.3 on the label)
CELL_CLEARANCE = 0.6      # diametral slack in the cradle bore
CELL_END_CLEARANCE = 1.0  # axial slack

CELL_BORE_R = (CELL_D + CELL_CLEARANCE) / 2
CELL_BORE_L = CELL_L + CELL_END_CLEARANCE

# The cell, its bore and its insertion shaft CAN be shifted off-centre along
# X (positive = toward +X/USB-C, away from the -X/antenna end) -- kept as a
# live parameter, not deleted, even though it's 0 now. It used to buy axial
# room inside the -X end wall for the SMA connector's body, at a 1:2 cost of
# case length for antenna clearance (every mm of offset grows OUTER_L by
# 2mm, since the outer envelope stays symmetric). That trade is moot now
# that the SMA mount lives in the PLATE's own end wall instead of the
# BASE's (see README's "Why the SMA mount moved to the plate") -- the
# plate's whole Z-band sits above the cell, so the connector never competes
# with it for room regardless of this offset. Left non-zero only if some
# future component needs axial room the same way the SMA body once did.
CELL_OFFSET_X = 0.0

# All "must not collide" sizing (case length, boss clearance, end chamfer)
# has to use whichever side of the shifted bore is CLOSER to its end wall --
# that is now the +X/USB end. CELL_NEAR_HALF_LEN is the same distance on the
# -X/antenna end, which is now larger and is what actually buys the pigtail
# its extra room.
CELL_FAR_HALF_LEN = CELL_BORE_L / 2 + CELL_OFFSET_X    # governs the +X side
CELL_NEAR_HALF_LEN = CELL_BORE_L / 2 - CELL_OFFSET_X   # -X/antenna side (more room)

# --- Wall / shell -----------------------------------------------------------
WALL = 2.2                 # outer shell wall thickness
FLOOR = 2.0                # base floor thickness under the cradle
# Half-lap mating. The base is a plain tub -- full-thickness wall right up
# to its rim, no lip at all. The plate's flange lands on that rim, and a plug
# hanging below the flange drops into the cavity to locate it:
#
#     ————————      plate flange, full outer footprint
#     ——____——      plug, inset to fit inside the base cavity
#
#     ||    ||      base wall, plain and full thickness
#
# The previous tongue/skirt split the 2.2mm wall lengthwise into a 0.88mm
# tongue and a 1.17mm skirt, each 5mm tall -- roughly two extrusion widths
# at a 5.7:1 aspect ratio, which is fragile to print and easy to snap.
# The plug is a free-standing wall instead, so it can be a sane thickness.
PLUG_DEPTH = 3.0           # how far the plug drops into the base cavity
PLUG_WALL = 1.6            # plug wall thickness
# The plug is inset from the plate's outer face, so it cannot hang off the
# plate's own 2.2mm wall -- it would float free. A short internal ledge just
# below the board carries it, after which the plate reverts to a thin wall.
PLUG_LEDGE = 1.5           # height of that ledge above the parting line
FIT_CLEARANCE = 0.15       # slack between base tongue and plate skirt
# How far the ledge juts inward of the cavity wall above it -- the whole
# height of the right-angle overhang the plate would otherwise print with,
# face-down (see build_plate()). LIP_CHAMFER is the 45 deg taper that
# replaces it; a hair under LIP_STEP so the chamfer does not have to
# consume the step face exactly edge-to-edge, which OCCT will not solve.
# What is left is a ~0.05mm lip, two orders below a nozzle width.
LIP_STEP = PLUG_WALL + FIT_CLEARANCE
LIP_CHAMFER = LIP_STEP - 0.05
# The cavity's own corner fillet must stay larger than LIP_CHAMFER. The taper
# is cut into the void cutter by chamfering its bottom rim (see build_plate());
# OCCT's chamfer offsets the rim's filleted corners by the chamfer size, so if
# the corner radius is smaller than the chamfer the parallel curve inverts and
# the chamfer returns a self-intersecting (invalid) solid -- which then breaks
# every downstream boolean and, in the worst case, silently deletes the whole
# plate. A hair above LIP_CHAMFER keeps the chamfer valid while leaving the
# cavity corners only marginally rounder than the base's own.
LIP_CORNER_FILLET = LIP_CHAMFER + 0.1
M2_HEAD_H = 2.2            # M2 socket head height clearance, for the case's
                            # own corner-screw counterbores
# reference/heltec_v4_side.JPG shows a component on the board's underside
# (RTC coin-cell holder, between the two 2.54mm header rows) standing 5.6mm
# proud of the PCB, present whether or not the GPIO headers are populated.
# This is the binding constraint on the gap.
BOARD_BOTTOM_COMPONENT_H = 5.6   # measured, tallest underside component

# Two more underside connectors, also visible in the side-view photo: one
# under the OLED (GPS module connector) and one under the USB-C connector
# (battery + solar panel connectors, modelled as a single combined footprint
# -- the photo only resolves one ~4.8mm-wide white block there, and the real
# split between the two isn't visible).
CONN_W = 4.8   # width (X extent), measured off the side-view photo
CONN_D = 15.8  # length (Y extent), measured off the reference image --
               # supersedes the earlier (est) 4.8mm square-footprint guess
CONN_H = 3.5   # height, measured protrusion below the PCB -- supersedes the
               # earlier 4.0mm figure
# Caliper measurements are given edge-to-edge (PCB edge to the connector's
# near face), not centre-to-centre, so these get converted to centres
# against the board's actual (shifted) edges in build_board().
CONN_BAT_SOLAR_EDGE_GAP = 1.3   # USB-C-end PCB edge -> battery/solar connector
CONN_GPS_EDGE_GAP = 8.6         # antenna-end PCB edge -> GPS connector

# Cell top -> board underside. Sized to clear the tallest of: any header-pin
# protrusion, the coin-cell holder, and the two connectors above -- NOT
# assumed zero, because this case's clearance no longer depends on the GPIO
# header rows being left unpopulated to fit.
#
# If your board DOES have headers soldered, the pins typically protrude
# ~2-3mm below the PCB -- raise HEADER_PIN_PROTRUSION below instead of this
# constant directly, so verify.py can enforce the relationship between the two.
HEADER_PIN_PROTRUSION = 0.0   # mm below the PCB; 0 = headers unpopulated
CELL_TO_BOARD_GAP = max(HEADER_PIN_PROTRUSION, BOARD_BOTTOM_COMPONENT_H, CONN_H) + 0.3
PARTING_ABOVE_CELL = 1.0   # parting line sits this far above the cell bore
CORNER_FILLET = 2.5

# --- Face plate chamfers ----------------------------------------------------
# Break the face plate's top outer edge so the case does not read as a slab.
FACE_CHAMFER = 1.5
# The display cutout is bevelled on its *face* side, matching FACE_CHAMFER's
# 45 deg. The aperture stays OLED_WINDOW_W x OLED_WINDOW_H at the inside face
# and opens out
# toward the viewer. Printed window-up the hole only ever widens with height,
# so every layer is supported by the one below -- no overhang at all. Must
# stay below the top wall thickness or no straight land is left.
WINDOW_CHAMFER = 1.0

# --- Bottom chamfer (base only) ---------------------------------------------
# The two long bottom edges are chamfered away, so the base's end-on profile
# becomes a truncated octagon: narrow flat bottom, two sloped flanks, two
# vertical sides, flat top where the face plate closes it. This deletes the
# dead corners of material outboard of the round cell.
#
# CHAMFER_ASPECT is rise/run. 1.0 gives a 45 deg face, which is a 45 deg
# overhang off the bed -- the printable limit. Values > 1.0 are shallower in
# plan (steeper walls, safer to print, but less material saved).
CHAMFER_ASPECT = 1.0
MIN_CHAMFER_WALL = 2.2     # material left between the chamfer and the cell bore
MIN_BOTTOM_W = 14.0        # flat width the case stands on

# The two short ends get only a small break, not the large flank -- the big
# chamfer exists to delete material outboard of the *cylinder*, which only
# has dead corners along its length. At the ends the cell's flat face is
# right there, so a large chamfer would eat the end stop for no gain.
# This is just an edge break, sized to match FACE_CHAMFER.
END_CHAMFER_ASPECT = 1.0
END_CHAMFER = 1.5           # small chamfer on the two short bottom edges
MIN_END_CHAMFER_WALL = 2.2  # material left between the end chamfer and the bore end
MIN_BOTTOM_L = 50.0         # flat length the case stands on

# Every remaining sharp junction around the chamfered bottom -- where the
# large flanks run out against the end walls -- gets the same small break.
PROFILE_EDGE_CHAMFER = 1.0

# --- Board retention (shoulder + screwed-on retainer plank) -----------------
# The board has no mounting holes (confirmed off the real board photo), so it
# can't hang from screw posts. An earlier revision tried a slide-under lip
# along both long edges instead: lift the board into the plate from its open
# underside, then slide it a few mm so the lip hooks under its underside.
# That mechanism was never actually buildable -- the lip covered nearly the
# whole rail length while the lip-free entry gap was only 5mm, and a 51mm
# rigid board cannot fit inside a 5mm gap to begin with. (The lip solid also
# wasn't attached to the rest of the plate -- it only touched the board-sized
# gap of empty air below the shoulder.)
#
# Now: a wide shoulder, attached to both the plate's own side wall and its
# ceiling, registers the board's top face and Y position -- the board is
# lifted straight up into it from the plate's open underside, no sliding
# involved. What stops the board falling back out is a *separate* printed
# retainer plank (see RETAINER_* below and build_retainer()), installed
# after the board by hand and then screwed to two bosses hanging off the
# shoulder. It presses up against the GPS and battery/solar connector
# housings on the board's underside, not the PCB edge -- so it never has to
# slide past the board either, only move straight up into contact. The base
# is not involved at all -- the cell's bore underlies the board's whole
# length, so a base-side pedestal would have to clear the cell *and* poke up
# past the parting line (see the module docstring for why the board hangs
# from the plate, not the base).
M2_BOSS_D = 5.5             # case corner screw bosses (base + plate) --
                             # square in cross-section (side length, not
                             # diameter -- kept the same name since it plays
                             # the same "how big is the boss" role the
                             # circular version used to), with rounded
                             # corners except where a corner sits flush
                             # against another solid (see _rounded_square_boss)
BOSS_CORNER_FILLET = 1.0    # rounds the boss's free corners; must stay
                             # under M2_BOSS_D/2
BOSS_WALL_FILLET = 0.4      # concave fillet where a corner screw post's
                             # exposed faces run into the cavity's own inner
                             # wall faces (see _fillet_post_wall_edges()).
                             # The plate's plug notch is grown by this too,
                             # so the plug still clears the base's posts
                             # once they carry the extra corner material.
                             # OCCT solves this edge set for radii in
                             # [0.25, 0.5] and refuses outside that, so this
                             # sits mid-band rather than at either edge --
                             # re-scan the range if nearby geometry moves
                             # (dropping the ear notch's rim chamfer alone
                             # shifted the upper limit from 0.8 to 0.5).
RAIL_SHOULDER_INNER_Y = 10.5     # inner edge of the wide registration shoulder;
                                  # clears the OLED window half-height by ~0.6mm
RAIL_OUTER_Y = BOARD_W / 2 + BOARD_CLEARANCE   # 13.2, board's own pocket edge
                                  # -- SHOULDER_OUTER_Y (below, once INNER_W is
                                  # known) is how far the built shoulder
                                  # actually extends, out to the plate's wall
PRELOAD_BUMP_INTERFERENCE = 0.2  # local shoulder protrusion, elastically
                                  # compressed when the retainer clamps the
                                  # board home, so it doesn't rattle
PRELOAD_BUMP_LEN = 3.0           # mm along X -- short local dimple, not a
                                  # full-length feature

# --- M2 socket-head cap screw fasteners -------------------------------------
M2_SHAFT_D = 2.2           # clearance hole for the screw shaft
M2_HEAD_D = 4.0            # socket head diameter clearance
M2_PILOT_D = 1.6           # pilot hole in the boss that receives the screw

# Push the boss out into the corner as far as it can go without poking
# through the case's own outer (filleted) surface. Its closest approach to
# the outside is along the corner's 45 deg diagonal, where the outer profile
# is the CORNER_FILLET arc rather than a flat wall -- solved so the boss is
# tangent to that arc. The boss doesn't touch the outer wall (BOSS_OUTER_MARGIN
# of backing material is kept there on purpose), so every one of its corners
# stays rounded here -- its own reach along that diagonal is therefore not
# the flat half-width M2_BOSS_D/2 but a rounded square's corner distance,
# sqrt(2)*(half-width - corner radius) + corner radius:
#
#   inset = CORNER_FILLET*(1 - 1/sqrt(2))
#           + (boss_diag_reach + BOSS_OUTER_MARGIN)/sqrt(2)
#
# The boss is bigger across than a single wall is thick (M2_BOSS_D=5.5 vs
# WALL=2.2), so it can't *also* be tangent to the inner wall without
# breaching the outer one -- this is the closest it can get while staying
# fully enclosed. Independent of OUTER_L/OUTER_W: the corner geometry is the
# same regardless of how long the case is, as long as the case is bigger
# than the corner region itself (true here by a wide margin).
#
# A second, unrelated constraint turns out to bind tighter: the plate's
# M2_HEAD_D counterbore around the boss has to stay clear of the top face's
# own FACE_CHAMFER (its edge break), or the counterbore would clip into the
# sloped edge instead of landing on flat material.
# The boss's own corner nearest the true outer corner (see
# _screw_boss_sharp_corners()) is left sharp rather than rounded -- a sharp
# point sitting close to the case's own CORNER_FILLET arc is robust the way
# two rounded surfaces tangent to each other are not (see the fillet-vs-
# fillet sliver this file hit elsewhere, lid_artifacts.png), so it can sit
# closer to "touching" without the fragile-tangency risk. Its reach along
# the diagonal is then the plain sharp-corner Euclidean distance, not a
# rounded corner's shorter one.
BOSS_OUTER_MARGIN = 0.05   # backing material left outside the boss at its
                            # closest approach to the outer surface -- a
                            # boolean/print-robustness epsilon now, not
                            # deliberate structural backing (that's what the
                            # sharp corner buys back); left non-zero only
                            # because a literal zero-margin tangent is its
                            # own fragile case
COUNTERBORE_MARGIN = 0.2   # buffer beyond exact tangency to the face chamfer
_boss_diag_reach = M2_BOSS_D / 2 * math.sqrt(2)
_inset_corner = (CORNER_FILLET * (1 - 1 / math.sqrt(2))
                 + (_boss_diag_reach + BOSS_OUTER_MARGIN) / math.sqrt(2))
_inset_counterbore = M2_HEAD_D / 2 + FACE_CHAMFER + COUNTERBORE_MARGIN
# In practice the counterbore constraint is the one that actually binds
# (3.7mm vs. the corner's ~3.5mm), so the boss ends up with real backing
# closer to 0.3mm than the nominal margin above, not touching -- true
# zero-gap contact would mean loosening COUNTERBORE_MARGIN/FACE_CHAMFER
# instead, a separate trade-off against the screw head's own seat.
SCREW_INSET = max(_inset_corner, _inset_counterbore)

# --- Derived Z levels (from the outside of the base floor, Z=0) -------------
CELL_AXIS_Z = FLOOR + CELL_BORE_R
CELL_BORE_TOP_Z = FLOOR + 2 * CELL_BORE_R
CELL_TOP_Z = CELL_AXIS_Z + CELL_D / 2          # top of the actual cell

BOARD_UNDER_Z = CELL_BORE_TOP_Z + CELL_TO_BOARD_GAP
BOARD_TOP_Z = BOARD_UNDER_Z + BOARD_T
OLED_TOP_Z = BOARD_TOP_Z + OLED_MODULE_THICK
USB_TOP_Z = BOARD_TOP_Z + USB_H

# Parting line sits just above the cell, so the base is a pure battery tub.
# The base now ends flat at its rim -- nothing rises above the parting line.
PARTING_Z = CELL_BORE_TOP_Z + PARTING_ABOVE_CELL
BASE_DEPTH = PARTING_Z

# Plate is modelled with its own Z=0 at the parting line. It extends *below*
# that, down to -PLUG_DEPTH, for the plug that drops into the base cavity.
BOARD_UNDER_LOCAL = BOARD_UNDER_Z - PARTING_Z
BOARD_TOP_LOCAL = BOARD_TOP_Z - PARTING_Z

# The ceiling is set by the tallest top-side component EXCEPT the OLED
# module -- the module pokes through its own window cutout instead of
# needing headroom under the ceiling, so it's excluded here on purpose, not
# an oversight. u.FL (1.6mm) is included for completeness even though USB-C
# (3.3mm) always wins in practice.
CEILING_CLEARANCE = max(USB_H, UFL_H)   # flush contact, no added gap
PLATE_INNER_H = BOARD_TOP_LOCAL + CEILING_CLEARANCE
PLATE_DEPTH = PLATE_INNER_H + WALL
TOTAL_HEIGHT = PARTING_Z + PLATE_DEPTH

# How far the OLED module pokes past the top wall's own outer face -- the
# whole point of excluding it from PLATE_INNER_H above. Informational (and
# checked by verify.py): if this goes negative, whatever shrank
# OLED_MODULE_THICK or grew CEILING_CLEARANCE has quietly gone back to the
# old "recessed behind the window" behaviour.
OLED_PROTRUSION = OLED_TOP_Z - (PARTING_Z + PLATE_DEPTH)

# Case screws pass through a post in the plate (which the head seats on top
# of) and thread into the base's boss below, so they must be long enough to
# cross the post and still bite. Engagement is what is left over.
SCREW_LEN = 16.0           # M2x16 SHCS for the case halves
SCREW_ENGAGE = SCREW_LEN - PLATE_INNER_H

# --- Derived plan dimensions ------------------------------------------------
# Width is set by the cell (which is wider than the board) plus side walls.
INNER_W = max(BOARD_W + 2 * BOARD_CLEARANCE, CELL_D + CELL_CLEARANCE) + 4.0
OUTER_W = INNER_W + 2 * WALL

# The registration shoulder is built out to the plate's own wall (rather
# than stopping at RAIL_OUTER_Y, well short of it) so it is attached on two
# sides -- wall and ceiling -- instead of hanging from the ceiling alone as
# an unsupported rib. Needs INNER_W, so it can't live in the board-retention
# config block above.
SHOULDER_OUTER_Y = INNER_W / 2

# Length must leave room for the corner screw bosses *beyond* the ends of the
# cell's insertion shaft -- the shaft spans most of the cavity width, so a
# boss anywhere within its length would stand in the cell's way. The shaft is
# off-centre (CELL_OFFSET_X), so CELL_FAR_HALF_LEN (the +X/USB side, which is
# now the closer one) is what sizes this -- the outer envelope is symmetric,
# so both sides grow to match the tighter one, and the -X/antenna side ends
# up with CELL_OFFSET_X of extra clearance beyond what this alone requires.
# Kept to the same order as the other minimal-but-safe clearances in this
# file (RETAINER_EAR_CORNER_MARGIN etc.), now that the boss itself sits much
# closer to the corner and no longer needs a generous margin here too.
BOSS_END_MARGIN = 0.5
_min_half_len = CELL_FAR_HALF_LEN + BOSS_END_MARGIN + M2_BOSS_D / 2 + SCREW_INSET
OUTER_L = 2 * max(_min_half_len, BOARD_L / 2 + WALL + 4.0)
INNER_L = OUTER_L - 2 * WALL

screw_positions = [
    ( OUTER_L / 2 - SCREW_INSET,  OUTER_W / 2 - SCREW_INSET),
    ( OUTER_L / 2 - SCREW_INSET, -OUTER_W / 2 + SCREW_INSET),
    (-OUTER_L / 2 + SCREW_INSET,  OUTER_W / 2 - SCREW_INSET),
    (-OUTER_L / 2 + SCREW_INSET, -OUTER_W / 2 + SCREW_INSET),
]


def _bore_half_width(z):
    """Half-width of the cell bore at height z (0 outside the bore)."""
    dz = z - CELL_AXIS_Z
    return math.sqrt(max(CELL_BORE_R ** 2 - dz * dz, 0.0))


def chamfer_outer_half_width(z):
    """Half-width of the base's outer surface at height z, after chamfering."""
    rise = CHAMFER_RISE
    if z >= rise:
        return OUTER_W / 2
    return OUTER_W / 2 - CHAMFER_RUN * (1.0 - z / rise)


def _max_chamfer_run():
    """Largest chamfer that keeps MIN_CHAMFER_WALL of material between the
    sloped face and the cell bore, and leaves MIN_BOTTOM_W to stand on."""
    def wall_ok(run):
        rise = run * CHAMFER_ASPECT
        for i in range(201):
            z = rise * i / 200.0
            outer = OUTER_W / 2 - run * (1.0 - (z / rise if rise else 1.0))
            if outer - _bore_half_width(z) < MIN_CHAMFER_WALL:
                return False
        return True

    hi = (OUTER_W - MIN_BOTTOM_W) / 2.0
    if hi <= 0:
        return 0.0
    if wall_ok(hi):
        return hi
    lo = 0.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if wall_ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


CHAMFER_RUN = _max_chamfer_run()
CHAMFER_RISE = CHAMFER_RUN * CHAMFER_ASPECT
BOTTOM_W = OUTER_W - 2 * CHAMFER_RUN
# Overhang measured from vertical; must stay <= 45 deg to print unsupported
CHAMFER_OVERHANG_DEG = math.degrees(math.atan2(CHAMFER_RUN, CHAMFER_RISE))


def end_chamfer_outer_half_length(z):
    """Half-length of the base's outer surface at height z, after chamfering."""
    if z >= END_CHAMFER_RISE:
        return OUTER_L / 2
    return OUTER_L / 2 - END_CHAMFER_RUN * (1.0 - z / END_CHAMFER_RISE)


def _max_end_chamfer_run():
    """Ceiling on the end chamfer, kept as a guard rather than a target.

    END_CHAMFER is deliberately a small edge break, so this normally has no
    effect -- but if anyone raises it, this stops the chamfer eating into the
    cell bore's end (which doubles as the axial end stop). The bore's X
    extent is constant, so the pinch is at the lowest height it reaches.

    The chamfer is symmetric (same run on both ends), so the +X/USB end --
    the closer one now that the bore is offset -- is what has to be checked;
    the -X/antenna end automatically has CELL_OFFSET_X more slack than this.
    """
    bore_lo = CELL_AXIS_Z - CELL_BORE_R
    bore_hi = CELL_AXIS_Z + CELL_BORE_R

    def wall_ok(run):
        rise = run * END_CHAMFER_ASPECT
        for i in range(201):
            z = rise * i / 200.0
            if not (bore_lo <= z <= bore_hi):
                continue          # no bore at this height, nothing to clear
            outer = OUTER_L / 2 - run * (1.0 - (z / rise if rise else 1.0))
            if outer - CELL_FAR_HALF_LEN < MIN_END_CHAMFER_WALL:
                return False
        return True

    hi = min(END_CHAMFER, (OUTER_L - MIN_BOTTOM_L) / 2.0)
    if hi <= 0:
        return 0.0
    if wall_ok(hi):
        return hi
    lo = 0.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if wall_ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


END_CHAMFER_RUN = _max_end_chamfer_run()
END_CHAMFER_RISE = END_CHAMFER_RUN * END_CHAMFER_ASPECT
BOTTOM_L = OUTER_L - 2 * END_CHAMFER_RUN
END_CHAMFER_OVERHANG_DEG = math.degrees(
    math.atan2(END_CHAMFER_RUN, END_CHAMFER_RISE))

# The board floats on the plate's rail channel rather than screw posts, so
# nothing pins it to X=0 -- it's shifted toward +X (USB-C) instead, to close
# most of the gap between the connector and the case's own USB cutout. Now
# that the corner boss is tucked into the corner (SCREW_INSET above) rather
# than sitting well inside the cavity, it's no longer the tighter
# constraint -- whichever of the two actually binds wins.
# USB-C faces +X, antenna -X.
BOARD_USB_WALL_CLEARANCE = 0.3   # target gap, USB-C face to inner wall
# The real PCB can't be locally notched around the corner screw boss the
# way a printed part can (see FIT_CLEARANCE-style notches elsewhere in this
# file) -- its rectangular corner has to clear the boss's full outline on
# its own. This is consistently the tighter of the two constraints below
# (the boss, not the USB wall, is what actually holds the board back).
#
# A flat rectangle-vs-square model (comparing the board's edge against the
# boss's inner edge at the boss's own centre Y) would put the tangent point
# well short of the real one, because the board's nearest corner isn't
# square -- it's cut by BOARD_CORNER_CHAMFER. The true closest approach is
# along that 45 deg diagonal, not a flat edge.
#
# The corner boss is square with rounded corners (see _rounded_square_boss)
# -- and stays rounded on every corner here, including the one facing the
# board: the retainer boss touches this post's flat -X face, but only
# across its own middle, nowhere near the fillet at either end of that face
# (see _screw_boss_sharp_corners()), so the corner the board approaches is a
# genuine BOSS_CORNER_FILLET arc, not a sharp point. Solved in closed form
# for the board shift that puts the chamfer diagonal exactly tangent to
# that arc:
#
#   the diagonal (in the board's own local frame) satisfies
#     x + y == (BOARD_L/2 - BOARD_CORNER_CHAMFER) + BOARD_W/2
#   the arc's own centre (inset from the sharp corner by the fillet radius
#   along both axes), shifted into that same local frame, sits at
#     (corner_boss_x - (M2_BOSS_D/2 - BOSS_CORNER_FILLET) - BOARD_CENTER_X,
#      corner_boss_y - (M2_BOSS_D/2 - BOSS_CORNER_FILLET))
#   distance from a point to that line is |x + y - line_const| / sqrt(2);
#   setting it equal to the fillet radius and solving for BOARD_CENTER_X
#   gives the formula below.
#
# Verified against the real (chamfered) board solid and the real (rounded-
# corner) boss solid by direct boolean intersection, bisected to zero
# volume -- matches this closed form to sub-micron precision. This is an
# *exact* geometric tangent with no added margin, so it assumes zero print
# slop between the board and the boss; back it off if your printer/board
# stock has real tolerance to account for.
_corner_boss_x = OUTER_L / 2 - SCREW_INSET
_corner_boss_y = OUTER_W / 2 - SCREW_INSET
BOARD_CENTER_X_TANGENT = (_corner_boss_x + _corner_boss_y
                          - BOARD_L / 2 - BOARD_W / 2 + BOARD_CORNER_CHAMFER
                          - (2 * (M2_BOSS_D / 2 - BOSS_CORNER_FILLET)
                             + BOSS_CORNER_FILLET * math.sqrt(2)))
_shift_for_usb = (INNER_L / 2 - BOARD_USB_WALL_CLEARANCE) - (BOARD_L / 2 + USB_OVERHANG)
# Getting closer than this would mean moving/shrinking the corner boss or
# growing OUTER_L -- out of scope here.
BOARD_CENTER_X = min(_shift_for_usb, BOARD_CENTER_X_TANGENT)

BOARD_CONNECTOR_END_X = BOARD_L / 2 + BOARD_CENTER_X
BOARD_FAR_END_X = -BOARD_L / 2 + BOARD_CENTER_X
OLED_CENTER_X += BOARD_CENTER_X
USB_CENTER_X = BOARD_CONNECTOR_END_X + USB_OVERHANG - USB_DEPTH / 2

# The two buttons share BUTTON_EDGE_GAP_X, so they share one X too --
# BUTTON_CENTER_X lands inside the USB-C connector's own X span
# (USB_CENTER_X +- USB_DEPTH/2), which is expected: the buttons sit right
# beside the connector on the real board. Only a Y-running bridge straight
# between them would actually cross the connector -- see the button bridge
# section below.
BUTTON_CENTER_X = BOARD_CONNECTOR_END_X - BUTTON_EDGE_GAP_X
button_positions = [(BUTTON_CENTER_X, BUTTON_Y), (BUTTON_CENTER_X, -BUTTON_Y)]

# --- Button actuator bridge (see build_button_bridge()) ---------------------
# A separate printed part carrying both button actuators, joined under the
# lid instead of two loose pieces. Round posts pass through round ceiling
# holes (self-aligning, forgiving of small position error) down to a flat
# bracket that reaches the actual buttons. USB_CENTER_X/USB_DEPTH place the
# connector's own inner (board-centre-side) edge; the bridge's spine has to
# stay clear of it since the connector sits flush against the ceiling with
# zero spare headroom there (CEILING_CLEARANCE == USB_H) -- it can only be
# dodged in-plane, not stepped over.
#
# Each post is a plain, constant-diameter cylinder -- no wider head/cap and
# no counterbore. A stepped post (narrow shaft + wider head recessed into a
# counterbore, the first version of this) prints with the head's overhang
# unsupported no matter which way up the part goes: cap-down has the arm/
# spine cantilevered off a thin post with nothing under them, post-down (the
# orientation that actually works for the arm) still leaves the head's own
# rim overhanging the narrower shaft above it. A single diameter the whole
# way up removes the overhang either way. Retention no longer needs a cap
# catching in a counterbore either: the arm/spine sitting below the solid
# ceiling (wider than the hole, everywhere except right at the two holes
# themselves) is what stops the bridge from being pushed straight through --
# the same role a rivet's far-side head plays, just on the inside instead of
# a recessed head on the outside.
BUTTON_POST_D = 3.0             # constant diameter, arm to outer face
BUTTON_HOLE_CLEARANCE = 0.3     # diametral, post in its ceiling hole
BUTTON_HOLE_D = BUTTON_POST_D + BUTTON_HOLE_CLEARANCE
BUTTON_PLUNGER_TRAVEL = 0.2     # dead-gap left between the bridge's foot and
                                  # the real button's top face, so the bridge
                                  # can't preload/permanently depress either
                                  # switch
BUTTON_ARM_T = 0.5              # bridge thickness (Z) -- capped by the same
                                  # 0.8mm gap the post crosses (CEILING_CLEARANCE
                                  # minus BUTTON_H): the arm/spine run the
                                  # whole C-shape at button-top height, so
                                  # BUTTON_PLUNGER_TRAVEL + BUTTON_ARM_T has to
                                  # stay under that 0.8mm or the arm's own
                                  # footprint (wide, unlike the narrow post)
                                  # would collide with the solid ceiling
                                  # outside the round through-hole
BUTTON_ARM_W = 2.4              # bridge width (Y at the arms, X at the spine)
BUTTON_BRIDGE_CLEARANCE = 1.0   # spine kept this far clear of the USB-C
                                  # connector's own footprint

_usb_inner_x = USB_CENTER_X - USB_DEPTH / 2
BUTTON_SPINE_X = _usb_inner_x - BUTTON_BRIDGE_CLEARANCE - BUTTON_ARM_W / 2

BUTTON_ARM_BOTTOM_Z = BOARD_TOP_Z + BUTTON_H + BUTTON_PLUNGER_TRAVEL
BUTTON_ARM_TOP_Z = BUTTON_ARM_BOTTOM_Z + BUTTON_ARM_T
# The post starts at the SAME level as the arm's own bottom (not its top),
# so the two overlap through the arm's full thickness instead of merely
# butting together at one Z-plane -- a deliberately redundant overlap for a
# robust boolean union, and it means the post's own material is there from
# the very first printed layer instead of appearing only once the arm's
# 0.5mm has already gone down.
BUTTON_POST_H = (PARTING_Z + PLATE_DEPTH) - BUTTON_ARM_BOTTOM_Z

# RST (reset) needs to stay reachable but not so exposed it gets pressed by
# accident -- recessed BUTTON_RST_OFFSET below the outer face. PRG (boot) is
# the one actually reached for day-to-day use (held with RST for flashing),
# so it gets the opposite treatment, proud of the face by the same amount.
# Both are a per-button adjustment to the post's own length (BUTTON_POST_H
# above is the shared flush baseline); the hole itself doesn't change, since
# it already runs the plate's full depth regardless of how long the post is.
BUTTON_RST_OFFSET = -0.5
BUTTON_PRG_OFFSET = 0.5
BUTTON_TOP_CHAMFER = 0.4        # printable break on each post's pressable top

# (x, y, top_offset) -- RST at +Y, PRG at -Y, matching the reference photo.
button_actuators = [
    (BUTTON_CENTER_X, BUTTON_Y, BUTTON_RST_OFFSET),
    (BUTTON_CENTER_X, -BUTTON_Y, BUTTON_PRG_OFFSET),
]

# --- USB-C plug recess (see _usb_recess_collar()/_usb_recess_cutter()) ------
# The plain rectangular window (_usb_cutter()) is sized to the *connector*,
# not to the *cable*, and that is not enough to plug anything in. Two things
# stand between a cable and the receptacle: WALL (2.2mm) of end wall, and
# whatever gap the board shift couldn't close (BOARD_CENTER_X is capped by
# the corner boss, not by BOARD_USB_WALL_CLEARANCE -- see there), which is
# another ~2.1mm. A USB-C plug's shell only protrudes ~6.5mm from its own
# overmoulded body, and the body is far too big for the window, so the body
# grounds out on the outer face with barely 2mm of shell inside the
# receptacle -- it doesn't reach the latch, let alone the contacts.
#
# So the plate's +X end gets a recess -- a well sunk into the end face,
# between the two corner screws, wide/tall enough to swallow the cable's
# overmould and deep enough to carry it right up to the connector's face.
# The well necessarily reaches PAST the cavity's inner wall (the connector
# sits behind it), so it can't be a plain cut: everything inboard of
# INNER_L/2 has to be built up first as a collar around the well, or the
# well would simply open into the case interior. The collar is what gives
# the recess its own side walls and its own floor, under the connector.
#
# Sizes are the *cable's* envelope, not the case's -- the well is derived
# from them, so re-measuring a chunkier cable and re-running is the whole
# adjustment.
USB_PLUG_W = 12.4        # overmoulded plug body: width (Y) ...
USB_PLUG_H = 6.5         # ... and height (Z). Sized to the largest bodies
                          # the Type-C spec's own overmould envelope allows
                          # (~12.35 x 6.5mm), so slimmer cables just have
                          # room to spare rather than needing a reprint.
USB_PLUG_SHELL_L = 6.5   # how far the metal shell stands proud of that
                          # body -- i.e. how much X the well has to give
                          # back before the plug can seat
USB_PLUG_NOSE_GAP = 0.3  # well's inner end -> connector's own outer face.
                          # Not zero: the board is lifted vertically into
                          # the plate past this very face, and its X is set
                          # by the rail shoulder's endstop, so the collar
                          # must not be in the connector's way.
USB_RECESS_WALL = 1.6    # collar wall thickness (same as PLUG_WALL)
USB_RECESS_FLARE = 1.5   # 45 deg lead-in on the well's two SIDE walls at
                          # the outer face -- a funnel for the plug, and it
                          # keeps the mouth from reading as a raw slot. It
                          # is confined to the wall itself (it ends well
                          # outboard of INNER_L/2), so it never thins the
                          # collar.

USB_RECESS_BACK_X = BOARD_CONNECTOR_END_X + USB_OVERHANG + USB_PLUG_NOSE_GAP
USB_RECESS_HALF_W = USB_PLUG_W / 2
# Centred on the connector's own mid-height, not on anything of the case's:
# a plug's body is centred on its shell, and the shell is centred in the
# receptacle. That works out to the board's own underside plane, since
# USB_PLUG_H/2 - USB_H/2 happens to be almost exactly BOARD_T.
USB_RECESS_FLOOR_Z = (BOARD_TOP_Z + USB_H / 2) - USB_PLUG_H / 2
USB_RECESS_FLOOR_LOCAL = USB_RECESS_FLOOR_Z - PARTING_Z
# Shell engagement the well actually buys back: everything the plug has to
# give up is the nose gap, since its body can now follow the shell all the
# way in.
USB_PLUG_ENGAGEMENT = USB_PLUG_SHELL_L - USB_PLUG_NOSE_GAP

# The well is open at the TOP -- it breaks through the plate's top face
# rather than being roofed over -- and that isn't a shortcut, it's forced.
# The connector's own top face is flush with the ceiling (CEILING_CLEARANCE
# == USB_H), which leaves WALL of top wall over it, and FACE_CHAMFER (1.5mm)
# eats nearly all of that again at the outer face: a roof over a well this
# tall would be a fraction of a millimetre thick right where the cable
# pushes on it. An open top costs nothing structurally (the collar's walls
# and floor are what seal the interior, and they are untouched), removes the
# only unsupported span the feature would have had, and lets an oversized
# cable stick up out of the well instead of not fitting at all.

# GPS and battery/solar underside connector centres -- edge-referenced off
# the (shifted) board ends, matching the caliper measurements. Hoisted to
# module level (rather than staying local to build_board()) so build_plate()
# and build_retainer() can target the same X positions the connectors are
# actually built at.
GPS_CONN_X = BOARD_FAR_END_X + CONN_GPS_EDGE_GAP + CONN_W / 2
POWER_CONN_X = BOARD_CONNECTOR_END_X - CONN_BAT_SOLAR_EDGE_GAP - CONN_W / 2

# --- Retainer plank (see "Board retention" above) ---------------------------
# A separate printed part, screwed to two bosses hanging off the plate's own
# registration shoulder. It presses up against the GPS and battery/solar
# connector housings on the board's underside -- not the bare PCB -- so its
# contact height is set by CONN_H, not by BOARD_T.
RETAINER_MARGIN = 3.0        # clear length kept past each connector's own
                              # footprint, at both ends of the plank
RETAINER_THICKNESS = 1.0     # plank thickness under the connectors
RETAINER_WIDTH = CONN_D - 1.0    # contact pad width (Y), slightly narrower
                                  # than the connector so it can't foul
                                  # anything just past its edges
# The plank's own main body must also stay clear of the plug's SHORT-END
# ring -- solid across the plate's full width near each end wall, the same
# mechanism as the long-edge ledge (see build_plate()), just not notched
# anywhere along here. Capped rather than left to grow unbounded with
# RETAINER_MARGIN: a board shift that pulls a connector close to an end
# wall (see BOARD_CENTER_X_TANGENT above) could otherwise push the plank
# straight into that ring -- the same failure mode as the retainer-ear-vs-
# corner-post conflict resolved in _retainer_ear_x_range(), just for the
# plank body instead of one of its ears.
_PLUG_SHORT_END_MARGIN = 0.3
_plug_short_end_inner_x = INNER_L / 2 - FIT_CLEARANCE - PLUG_WALL
RETAINER_X0 = max(GPS_CONN_X - CONN_W / 2 - RETAINER_MARGIN,
                   -_plug_short_end_inner_x + _PLUG_SHORT_END_MARGIN)
RETAINER_X1 = min(POWER_CONN_X + CONN_W / 2 + RETAINER_MARGIN,
                   _plug_short_end_inner_x - _PLUG_SHORT_END_MARGIN)
RETAINER_EAR_LEN = 4.0        # X length of each mounting ear/boss pair --
                               # the bosses themselves fill the dead zone
                               # between RAIL_OUTER_Y and RETAINER_BOSS_Y1
                               # (see build_plate()), so they need no
                               # separate diameter/Y-position of their own.
                               # Kept just wide enough for the pilot hole
                               # (M2_PILOT_D) plus a real wall on each side.
RETAINER_EAR_FILLET = 0.8      # rounds the ear/boss/notch corners on both
                                # the retainer and the plate -- must stay
                                # under half of every rectangle's shortest
                                # side (the boss dead zone is only
                                # RAIL_OUTER_Y..RETAINER_BOSS_Y1)
RETAINER_SCREW_SHAFT_D = M2_SHAFT_D
RETAINER_SCREW_PILOT_D = M2_PILOT_D
RETAINER_SCREW_ENGAGE = 4.0   # pilot hole depth into the boss

# The bare dead zone between the board's pocket edge (RAIL_OUTER_Y) and the
# wall's inner face (SHOULDER_OUTER_Y) is only 2.45mm wide. Centred in that,
# the retainer's own screw leaves almost no wall: the ear's M2 clearance
# hole (M2_SHAFT_D=2.2mm) is nearly as wide as the whole zone, down to
# ~0.125mm of plastic on either side of it -- not printable, and not a real
# hole once printed (it breaks out to the ear's own edge). The plate-side
# boss's pilot hole (M2_PILOT_D=1.6mm) fares better but is still thin
# (~0.425mm/side) on its unbacked (board-pocket) face.
#
# Recessing the dead zone's outboard edge into the side wall (which is
# WALL=2.2mm thick outboard of SHOULDER_OUTER_Y) buys width without
# touching the board-clearance or wall-thickness constants everything else
# is built from. RETAINER_BOSS_RECESS is how far past SHOULDER_OUTER_Y that
# goes; it has to stay well under WALL so real skin survives outboard of
# it, but doesn't have to hit a printability minimum since it is buried
# inside the assembled case, not a bare printed edge.
RETAINER_BOSS_RECESS = 1.0
RETAINER_BOSS_Y1 = SHOULDER_OUTER_Y + RETAINER_BOSS_RECESS
RETAINER_BOSS_CY = (RAIL_OUTER_Y + RETAINER_BOSS_Y1) / 2
RETAINER_BOSS_WALL_FILLET = 0.4  # concave fillet blending a retainer boss
                                   # into the shoulder overhead and into the
                                   # side wall its free end butts against --
                                   # printability only (see the "Retainer
                                   # mounting bosses" loop in build_plate()).
                                   # Deliberately NOT applied to the ear
                                   # notch's own top rim: that face is the
                                   # retainer plank's seat and has to stay
                                   # dead flat (see _retainer_ear_notch()).
                                   # Pinned by what OCCT's fillet solver will
                                   # actually accept for that edge set, which
                                   # is not monotonic in radius: 0.6, 0.5 and
                                   # 0.3 all fail, 0.4 succeeds. Re-test this
                                   # value if the boss geometry moves.

# The POWER_CONN_X boss sits close to the +X corner screw boss -- the
# board's own tangent shift (BOARD_CENTER_X_TANGENT above) pulls
# POWER_CONN_X close enough that even the *plain* (un-merged) ear width
# already reaches into the corner boss's own footprint.
#
# The PLATE's own boss is a static printed feature merging into another
# static printed feature (the corner screw post) -- safe to stretch out
# and union with it, closing what would otherwise be a visible gap.
#
# The RETAINER's own ear is a *different physical part*, though -- it can
# never be allowed to occupy the same space as the corner post, or the two
# parts couldn't both exist there once assembled. If its plain, centred
# window would reach that far, the whole window is slid back (kept the
# same length, just moved off-centre from conn_x) until it just clears the
# post -- its screw hole stays at the true conn_x regardless, since that's
# cut separately and only needs to land somewhere inside the ear, not at
# its centre.
_CORNER_BOSS_NEAR_X = OUTER_L / 2 - SCREW_INSET - M2_BOSS_D / 2
RETAINER_EAR_MERGE_OVERLAP = 0.1   # guaranteed overlap for a clean union,
                                     # not just an exact (fragile) tangent
RETAINER_EAR_CORNER_MARGIN = 0.2    # real clearance kept between the
                                      # retainer's own ear and the corner
                                      # post -- these are separate parts
# (conn_x, merge_into_corner_boss) pairs -- shared by build_plate(),
# _retainer_ear_notch() and build_retainer() so all three stay in sync.
RETAINER_CONNECTORS = [(GPS_CONN_X, False), (POWER_CONN_X, True)]


def _screw_boss_sharp_corners(x, y):
    """Which of a corner screw post's own corners stay unrounded.

    The corner facing the retainer boss (the plate's +X posts' -X-facing
    corners) does NOT need to: the retainer boss's Y-band (RAIL_OUTER_Y to
    RETAINER_BOSS_Y1, 3.45mm) reaches the post's flat -X face across most of
    its own middle -- the post's corner fillets only affect the outer
    BOSS_CORNER_FILLET (1mm) of that face near each end (Y within 1mm of
    +-M2_BOSS_D/2 from the post's own centre). At the merged connector
    (POWER_CONN_X) the recessed band's outboard tip does reach ~0.75mm into
    that fillet-affected sliver, but a flat box overlapping a convex fillet
    surface there doesn't reproduce the tangent-arc degeneracy this
    function exists to avoid (that only bites when *two* rounded surfaces
    meet); the union stays a single clean solid (see verify.py's "retainer
    boss intact"/"plate is a single connected solid" checks). It's only the
    *retainer boss's own* corner, right at the point of contact, that has
    to stay sharp for that junction (see the "Retainer mounting bosses"
    loop in build_plate()).

    The post's own **outward** corner -- the one nearest the case's own
    rounded outer corner, i.e. (sign(x), sign(y)) in the post's local frame
    -- does stay sharp, though, for every post (base and plate alike,
    since screw_positions is shared): rounding it would make it tangent to
    the case's own CORNER_FILLET arc, repeating the fragile fillet-vs-
    fillet contact that produced the sliver in lid_artifacts.png elsewhere
    in this file. A sharp point sitting close to that arc is robust in a
    way two rounded surfaces tangent to each other are not, and it lets
    the real backing material there shrink from ~0.72mm to ~0.31mm (see
    SCREW_INSET's derivation) without that risk. It doesn't reach zero --
    the counterbore-vs-face-chamfer constraint is what actually holds
    SCREW_INSET back, not this corner -- so there's no way to close the
    gap further without loosening COUNTERBORE_MARGIN/FACE_CHAMFER instead."""
    return {(int(math.copysign(1, x)), int(math.copysign(1, y)))}


def _retainer_ear_x_range(conn_x, merge_corner):
    """X0, X1 of the mounting ear/boss/notch at this connector position."""
    x0 = conn_x - RETAINER_EAR_LEN / 2
    x1 = conn_x + RETAINER_EAR_LEN / 2
    if merge_corner:
        # Plate's own boss: safe to reach into and merge with the post.
        x1 = max(x1, _CORNER_BOSS_NEAR_X + RETAINER_EAR_MERGE_OVERLAP)
    else:
        # Retainer's own ear: must never enter the post's footprint. Slide
        # the whole window back instead of shrinking it, so it keeps its
        # full RETAINER_EAR_LEN width for the screw hole and fillets.
        limit = _CORNER_BOSS_NEAR_X - RETAINER_EAR_CORNER_MARGIN
        if x1 > limit:
            shift = x1 - limit
            x0 -= shift
            x1 -= shift
    return x0, x1


RETAINER_POCKET_MARGIN = 0.5   # per-side X clearance the ear notch keeps
                                 # around the retainer's own ear, so a printed
                                 # ear can actually pass up through it


def _retainer_pocket_x_range(conn_x, merge_corner):
    """X0, X1 of the ear notch pocket AND of the plate boss that roofs it --
    deliberately one function for both, so the two can't drift apart.

    The pocket has to be wider than the ear that passes through it
    (RETAINER_POCKET_MARGIN), but there is nothing to gain by leaving the
    boss narrower than the pocket it caps: that only exposed a step of bare
    ledge around the boss's footprint (the gap the green arrows mark in
    retainer_cutouts.png). Growing the boss to the pocket's own width closes
    it without touching the ear's clearance, since the ear is sized off
    _retainer_ear_x_range() and never off this."""
    x0, x1 = _retainer_ear_x_range(conn_x, merge_corner)
    return x0 - RETAINER_POCKET_MARGIN, x1 + RETAINER_POCKET_MARGIN


def _retainer_pocket_sharp_corners(sign, merge_corner):
    """Corners of the pocket/boss rectangle left unrounded, in its own local
    (sx, sy) frame.

    The OUTBOARD pair (sy == sign, the side facing the plate's own wall) is
    always square. The notch deliberately overshoots the wall's inner face
    by a hair, so a rounded corner there leaves a thin crescent of ledge
    material trapped between the fillet arc and the wall, tapering to a
    point -- the little cusps the red arrows mark in retainer_cutouts.png.
    Square corners run straight out past the wall face instead, and nothing
    is left behind.

    A merged boss additionally keeps its +X pair square, so it unions flush
    into the corner screw post (see build_plate())."""
    sharp = {(1, sign), (-1, sign)}
    if merge_corner:
        sharp |= {(1, 1), (1, -1)}
    return sharp

# --- Cell insertion shaft ---------------------------------------------------
# Straight rectangular prism, from the widest point of the cradle bore up
# through the top of the base. The cell drops in vertically along this.
# Centred at CELL_OFFSET_X, not 0 -- see that constant's comment above.
SHAFT_W = 2 * CELL_BORE_R      # = cell dia + clearance
SHAFT_L = CELL_BORE_L
SHAFT_Z0 = CELL_AXIS_Z         # cradle's widest point
SHAFT_Z1 = BASE_DEPTH          # open at the top of the base

# SMA mount: axial, through the PLATE's own -X end wall -- the "profile"
# (short-end) wall of the lid, the same orientation as the original
# axial mount, just carried by the plate instead of the base. Not through
# the top face: a vertical mount was tried first, but a horizontal one
# keeps the connector's usual front-facing orientation.
#
# This sidesteps the cell entirely: the plate's whole Z-band sits above
# CELL_TOP_Z, so unlike a base-mounted axial hole, X position here isn't
# limited by SMA_CLEAR_DEPTH / the cell's near end at all -- the only axial
# limit is the board's own far edge. SMA_CLEAR_DEPTH is kept only as the
# still-relevant number for "how much room CELL_OFFSET_X buys," referenced
# from README's old-axial-mount comparison.
SMA_CLEAR_DEPTH = (INNER_L / 2) - CELL_NEAR_HALF_LEN

# Order, outward to inward, per the datasheet: threaded barrel, then the
# washer flush against the wall's inside face (no standoff -- this is what
# actually locates the connector, the same way it's captured on the real
# panel), then the fixed nut right behind the washer, then the stiff
# pigtail stub. SMA_WASHER_OUTER_X is exactly the plate's own wall inner
# face -- zero gap, not offset inward for any reason.
SMA_WASHER_OUTER_X = -(INNER_L / 2)

# The plate's half-lap ledge (PLUG_LEDGE tall, PLUG_WALL thick, inset by
# FIT_CLEARANCE) is real solid material right at the wall's inner face,
# though only for Z <= PLUG_LEDGE -- exactly where the washer, flush
# against the wall with no offset, would otherwise collide with it. Rather
# than move the washer to dodge it, the ledge gets a local notch instead
# (see build_plate()), the same pattern already used to let the case
# screw bosses through the plug -- so SMA_Z is free to sit wherever leaves
# the most margin to the ceiling, not pinned by the ledge at all.
SMA_Z_LOCAL = PLATE_INNER_H / 2
SMA_Z = PARTING_Z + SMA_Z_LOCAL   # global
SMA_NOTCH_R = SMA_WASHER_OD / 2 + FIT_CLEARANCE

# Flat-bottomed slot squaring off the lower part of the washer notch (see
# _sma_ledge_notch()), full washer width. Both bounds are derived, not
# measured, so the slot tracks correctly if the lip or the washer's own
# position ever move:
#   SMA_FLAT_Z0 -- the lip's taper actually ends at PLUG_LEDGE + LIP_CHAMFER
#   (see build_plate()); above that the cavity is already open on its own,
#   so there is nothing left for the slot to usefully square off.
#   SMA_FLAT_Z1 -- the ledge is only the top of one continuous PLUG_WALL-
#   thick ring that runs all the way down through the plug beneath it (see
#   build_plate()); the slot has to reach -PLUG_DEPTH, the plug's own full
#   depth, or it just leaves that ring's material standing below it.
SMA_FLAT_Z0 = PLUG_LEDGE + LIP_CHAMFER
SMA_FLAT_Z1 = -PLUG_DEPTH


def _rounded_box(length, width, height, z0, fillet):
    """A box centred in X/Y, standing on z0, with filleted vertical edges."""
    wp = (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .box(length, width, height, centered=(True, True, False))
    )
    if fillet > 0:
        wp = wp.edges("|Z").fillet(fillet)
    return wp


def _rounded_square_boss(cx, cy, half_x, half_y, z0, height, corner_r,
                          sharp_corners=()):
    """A rectangular boss (half-extents half_x/half_y from its own centre,
    from z0 up by height) with its four vertical corners rounded to
    corner_r -- except any corner listed in sharp_corners, each an
    (sx, sy) pair of +-1 picking it out in the boss's own local frame (e.g.
    (1, 1) is the corner at (cx+half_x, cy+half_y)).

    A sharp corner is left unrounded because that corner sits flush against
    another solid -- a wall, or another boss -- along its full edge, not
    just a point. Rounding it there would recede the boss's own surface out
    from under whatever it's meant to merge into: the two solids would
    still union without error, but the sliver of material actually bridging
    them could shrink to almost nothing right at the point that matters
    most, which is exactly what happened when a circular boss and a
    rectangular one were merged with an ordinary fillet on both (see the
    retainer-boss/corner-post case in build_plate()). A flat, unrounded
    corner against a flat, unrounded edge merges with no such taper."""
    solid = (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .center(cx, cy)
        .rect(2 * half_x, 2 * half_y)
        .extrude(height)
    )
    if corner_r <= 0:
        return solid
    for sx in (1, -1):
        for sy in (1, -1):
            if (sx, sy) in sharp_corners:
                continue
            corner_x = cx + sx * half_x
            corner_y = cy + sy * half_y
            eps = 0.05
            box_lo = (min(cx, corner_x) + sx * eps, min(cy, corner_y) + sy * eps, z0 - 1)
            box_hi = (max(cx, corner_x) + sx * eps, max(cy, corner_y) + sy * eps, z0 + height + 1)
            solid = solid.edges("|Z").edges(
                cq.selectors.BoxSelector(box_lo, box_hi, boundingbox=True)
            ).fillet(corner_r)
    return solid


def _fillet_post_wall_edges(solid, z_lo, z_hi, radius):
    """Concave fillet where the corner screw posts meet the cavity's own
    inner wall faces.

    Each post is wider than the corner it sits in, so it is partly buried
    in the two walls there and only its inboard quadrant stands exposed in
    the cavity. That leaves two vertical internal corners per post -- the
    post's inboard X face running into the side wall, and its inboard Y
    face running into the end wall -- which were bare 90 deg steps.

    Both are found by position rather than by any face/normal test: the
    post's inboard faces sit half a boss in from its centre, and the wall
    faces are at INNER_L/2 / INNER_W/2. All of them go into ONE .fillet()
    call, for the same reason the retainer boss's blends do (see
    build_plate()) -- sequential fillets that have to terminate into each
    other's surfaces make OCCT give up.

    A location with no edge (the plate's +X posts, where the retainer boss
    occupies that corner and carries its own blend instead) simply
    contributes nothing to the selection."""
    half = M2_BOSS_D / 2
    sel = None
    for (px, py) in screw_positions:
        sx = math.copysign(1, px)
        sy = math.copysign(1, py)
        for ex, ey in ((px - sx * half, sy * INNER_W / 2),
                       (sx * INNER_L / 2, py - sy * half)):
            box = cq.selectors.BoxSelector(
                (ex - 0.04, ey - 0.04, z_lo),
                (ex + 0.04, ey + 0.04, z_hi),
                boundingbox=True,
            )
            sel = box if sel is None else cq.selectors.SumSelector(sel, box)
    return solid.edges(sel).fillet(radius)


def cell_bore():
    """Cylindrical pocket for the cell, axis along X at the cradle height,
    centred at CELL_OFFSET_X rather than the case's X=0."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=CELL_OFFSET_X - CELL_BORE_L / 2)
        .center(0, CELL_AXIS_Z)
        .circle(CELL_BORE_R)
        .extrude(CELL_BORE_L)
    )


def insertion_shaft():
    """The volume the cell sweeps as it is lowered into the cradle."""
    return (
        cq.Workplane("XY")
        .workplane(offset=SHAFT_Z0)
        .center(CELL_OFFSET_X, 0)
        .box(SHAFT_L, SHAFT_W, SHAFT_Z1 - SHAFT_Z0, centered=(True, True, False))
    )


def usb_plug_envelope():
    """The volume a fully-seated USB-C cable plug needs, in global
    coordinates: its overmoulded body from the connector's face (less the
    nose gap) outward, past the case entirely.

    Not part of the assembly -- it's the probe verify.py pushes at the plate
    to prove the recess actually admits a cable, rather than trusting that
    the constants that shaped the well were the ones the well got built to.
    """
    return (
        cq.Workplane("XY")
        .workplane(offset=USB_RECESS_FLOOR_Z)
        .center((USB_RECESS_BACK_X + OUTER_L / 2 + 10) / 2, 0)
        .box(OUTER_L / 2 + 10 - USB_RECESS_BACK_X, USB_PLUG_W, USB_PLUG_H,
             centered=(True, True, False))
    )


def bottom_chamfer_profile():
    """Prism whose end-on (YZ) section is the base's chamfered outer profile.
    Intersecting the base with this shaves both long bottom edges at once,
    which is far more robust than selecting edges for a large .chamfer()."""
    hw = OUTER_W / 2
    top = BASE_DEPTH + 1
    inner = hw - CHAMFER_RUN
    # The sloped segment runs exactly (inner, 0) -> (hw, CHAMFER_RISE); the
    # skirt below Z=0 only exists so the boolean does not have to resolve
    # faces coplanar with the base's own underside.
    pts = [
        (-inner, -1.0),
        (inner, -1.0),
        (inner, 0.0),
        (hw, CHAMFER_RISE),
        (hw, top),
        (-hw, top),
        (-hw, CHAMFER_RISE),
        (-inner, 0.0),
    ]
    return (
        cq.Workplane("YZ")
        .polyline(pts)
        .close()
        .extrude((OUTER_L + 2) / 2, both=True)
    )


class FlankRunoutSelector(cq.Selector):
    """The four edges where the large bottom flanks run out against the end
    walls. They are the only edges on the part that are diagonal in Y/Z while
    holding X constant, which makes them cheap to pick out exactly -- far
    more robust than indexing into an edge list that shifts whenever another
    feature is added."""

    def filter(self, objectList):
        out = []
        for e in objectList:
            try:
                start, end = e.startPoint(), e.endPoint()
            except Exception:
                continue
            d = end.sub(start)
            if d.Length < 1e-6:
                continue
            d = d.multiply(1.0 / d.Length)
            if abs(d.x) < 1e-6 and abs(d.y) > 1e-3 and abs(d.z) > 1e-3:
                out.append(e)
        return out


def end_chamfer_profile():
    """Same idea as bottom_chamfer_profile(), but for the two short ends, so
    the bottom chamfer wraps the whole perimeter. Where the two prisms meet
    the corners resolve into a clean mitre on their own."""
    hl = OUTER_L / 2
    top = BASE_DEPTH + 1
    inner = hl - END_CHAMFER_RUN
    pts = [
        (-inner, -1.0),
        (inner, -1.0),
        (inner, 0.0),
        (hl, END_CHAMFER_RISE),
        (hl, top),
        (-hl, top),
        (-hl, END_CHAMFER_RISE),
        (-inner, 0.0),
    ]
    return (
        cq.Workplane("XZ")
        .polyline(pts)
        .close()
        .extrude((OUTER_W + 2) / 2, both=True)
    )


def _oled_window_cutter():
    """Display cutout, in plate-local coordinates: a plain rectangular hole
    through the top wall. The bevel is added afterwards by chamfering the
    resulting top edge, not by shaping this cutter."""
    return (
        cq.Workplane("XY")
        .workplane(offset=PLATE_INNER_H - 1)
        .center(OLED_CENTER_X, OLED_CENTER_Y)
        .rect(OLED_WINDOW_W, OLED_WINDOW_H)
        .extrude(PLATE_DEPTH - PLATE_INNER_H + 2)
    )


def _usb_cutter():
    """USB-C opening, in global coordinates.

    With the parting line just above the cell, this now falls entirely within
    the plate, so cutting it from the base removes nothing. It is still cut
    from both halves so the opening survives if the parting line is moved.

    In the plate this cut is now fully contained inside the plug recess
    (_usb_recess_cutter(), which is bigger in every direction and starts
    further in), so it removes nothing there either. It is kept as the thing
    that defines the *opening* independently of the recess -- move the
    parting line down and the base needs it again.
    """
    return (
        cq.Workplane("YZ")
        .workplane(offset=OUTER_L / 2 + 2)
        .center(0, BOARD_TOP_Z + USB_H / 2)
        .rect(USB_W + 1.0, USB_H + 1.0)
        .extrude(-(WALL + 8))
    )


def _usb_recess_collar():
    """The material that has to exist BEFORE the plug recess is cut, so the
    recess ends up with side walls and a floor instead of a hole into the
    cavity -- plate-local coordinates (Z=0 at the parting line).

    A plain block, running from the well's inner end (USB_RECESS_BACK_X)
    outboard into the end wall, and from USB_RECESS_WALL below the well's
    floor up to the ceiling. Two things it deliberately does NOT do:

      - it stops at the ceiling (PLATE_INNER_H) rather than at the plate's
        top face. Above the ceiling the plate is already solid across its
        whole footprint, so there is nothing to add there -- the recess just
        carves its own channel through that top wall, and the material left
        either side of it is that same wall.
      - it is buried in the end wall rather than merely touching it: the
        block runs a little past INNER_L/2 so the union has real overlap to
        work with instead of two coincident faces.

    It hangs into the cavity by only (INNER_L/2 - USB_RECESS_BACK_X), under
    2mm, and the board's own +X edge is a further USB_DEPTH-ish inboard of
    that, so nothing has to be moved to make room for it -- see verify.py's
    pairwise collision checks.
    """
    x0 = USB_RECESS_BACK_X
    x1 = INNER_L / 2 + USB_RECESS_WALL
    z0 = USB_RECESS_FLOOR_LOCAL - USB_RECESS_WALL
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .center((x0 + x1) / 2, 0)
        .rect(x1 - x0, USB_PLUG_W + 2 * USB_RECESS_WALL)
        .extrude(PLATE_INNER_H - z0)
    )


def _usb_recess_cutter():
    """The well itself -- plate-local coordinates.

    One extruded plan-view polygon, from the well's floor straight up
    through the plate's top face (see USB_RECESS_* on why it is open at the
    top). The polygon is the shape drawn in plan: constant USB_PLUG_W across
    the well proper, then flaring out at 45 deg over the last
    USB_RECESS_FLARE of the end wall to a wider mouth.

    Extruding one polygon, rather than cutting a box and chamfering the
    result, keeps the mouth's lead-in exact and the boolean plain -- the
    same reasoning as the OLED window's bevel, just solved on the cutter
    because these edges are on the end face, which the top-face chamfer has
    already been taken on by this point.
    """
    hw = USB_RECESS_HALF_W
    mouth_hw = hw + USB_RECESS_FLARE
    face_x = OUTER_L / 2
    flare_x = face_x - USB_RECESS_FLARE
    out_x = face_x + 1.0          # past the face, so the cut breaks through
    pts = [
        (USB_RECESS_BACK_X, hw),
        (flare_x, hw),
        (face_x, mouth_hw),
        (out_x, mouth_hw),
        (out_x, -mouth_hw),
        (face_x, -mouth_hw),
        (flare_x, -hw),
        (USB_RECESS_BACK_X, -hw),
    ]
    return (
        cq.Workplane("XY")
        .workplane(offset=USB_RECESS_FLOOR_LOCAL)
        .polyline(pts)
        .close()
        .extrude(PLATE_DEPTH - USB_RECESS_FLOOR_LOCAL + 1.0)
    )


def _sma_cutter():
    """SMA panel hole, axial through the plate's own -X end wall at
    (Y=0, SMA_Z_LOCAL) -- plate-local coordinates (Z=0 at the parting
    line). Plain barrel-sized cylinder, straight through from the panel
    face to the washer's own seating plane (SMA_WASHER_OUTER_X) -- the
    washer notch itself is a separate, wider cut (_sma_ledge_notch())."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=-OUTER_L / 2)
        .center(0, SMA_Z_LOCAL)
        .circle(SMA_HOLE_D / 2)
        .extrude(SMA_WASHER_OUTER_X - (-OUTER_L / 2))
    )


def _sma_ledge_notch():
    """Clears the half-lap ledge/plug locally where the SMA washer sits
    flush against the wall -- same pattern as the screw-boss notches
    below, just swept along X (the connector's own axis) instead of Z.
    Starts at the wall's *inner* face, not the outer one: the actual
    through-wall hole stays barrel-sized (_sma_cutter()) -- this only
    widens the ledge/plug material behind it, not the wall itself.

    The round notch alone leaves the lip's own material wrapped all the
    way around the washer. A flat-bottomed slot is cut into it too, full
    washer width (+/- SMA_NOTCH_R), from SMA_FLAT_Z0 (just below the
    washer's own centre -- above that the plain round notch is untouched
    since the lip itself has already ended, see SMA_FLAT_Z0) down through
    SMA_FLAT_Z1, the plug's own full depth -- the ledge is only the top of
    the same continuous ring that runs down through the plug, so the slot
    has to clear that too or it leaves the ring's material standing."""
    notch = (
        cq.Workplane("YZ")
        .workplane(offset=-INNER_L / 2)
        .center(0, SMA_Z_LOCAL)
        .circle(SMA_NOTCH_R)
        .extrude(SMA_WASHER_T + 1.5)
    )
    slot = (
        cq.Workplane("YZ")
        .workplane(offset=-INNER_L / 2)
        .center(0, (SMA_FLAT_Z0 + SMA_FLAT_Z1) / 2)
        .rect(2 * SMA_NOTCH_R, SMA_FLAT_Z0 - SMA_FLAT_Z1)
        .extrude(SMA_WASHER_T + 1.5)
    )
    return notch.union(slot)


def _retainer_ear_notch():
    """Clears the half-lap ledge AND the plug beneath it, locally, where the
    retainer's mounting ears pass through -- both are solid across the same
    outboard Y band the ears occupy (the ledge from the parting line up to
    PLUG_LEDGE, the plug itself from there down to -PLUG_DEPTH), so without
    this cut the ears could never even be inserted: the retainer is brought
    up from outside the plate's open underside, along this same Z path,
    before the plate is ever closed onto the base. Same pattern as
    _sma_ledge_notch() and the screw-boss notches (which already cut clean
    through the plug's full depth for exactly this reason, at the four
    corner bosses) -- just four more local cuts instead of relying on the
    plug staying solid everywhere.

    An earlier version stopped this cut at the parting line on the theory
    that the plug below it "must stay solid for the half-lap fit" -- true
    of the plug as a whole, but the corner-boss notches already establish
    that *local* full-depth notches don't compromise that, and skipping the
    plug portion here just left it blocking the ears' only way in.

    Stops at the top exactly at the retainer's own contact height (where
    the boss built above it begins), not above it -- an earlier version
    used PLUG_LEDGE + 1.0mm of margin there instead, which reached past
    where the boss starts and hollowed out its lower ~1.1mm along with the
    ledge, since this cut runs *after* the boss is unioned in.

    Y extent is asymmetric on purpose: generous margin inward (into
    already-open cavity, so it costs nothing) but only a boolean-robustness
    epsilon outward, stopping right at RETAINER_BOSS_Y1 instead of further
    past it -- an earlier symmetric-width version overshot 0.5mm past that
    line into the solid outer wall, cutting a visible pocket that was never
    actually needed. RETAINER_BOSS_Y1 itself is *not* the wall's bare inner
    face (SHOULDER_OUTER_Y) any more -- it is recessed RETAINER_BOSS_RECESS
    past it, on purpose, to give the retainer's own screw hole a real wall
    (see RETAINER_BOSS_RECESS)."""
    retainer_top_local = BOARD_UNDER_LOCAL - CONN_H
    z0 = -PLUG_DEPTH - 1.0
    z1 = retainer_top_local
    y0 = RAIL_OUTER_Y - 1.0
    y1 = RETAINER_BOSS_Y1 + 0.05
    cy = (y0 + y1) / 2
    w = y1 - y0
    cutter = None
    for conn_x, merge_corner in RETAINER_CONNECTORS:
        # Shares _retainer_pocket_x_range() with the boss that roofs this
        # pocket, so the two are the same width by construction. Both are
        # wider than the retainer's own ear, which is what actually has to
        # pass through here -- that clearance is RETAINER_POCKET_MARGIN.
        ex0, ex1 = _retainer_pocket_x_range(conn_x, merge_corner)
        ecx = (ex0 + ex1) / 2
        elen = ex1 - ex0
        for sign in (1, -1):
            # A plain prism, deliberately: the top face at z1 IS the surface
            # the retainer plank lands against, so it has to stay dead flat
            # right out to the pocket walls. An earlier version chamfered
            # this cut's top rim -- the cutter was grown by the chamfer size
            # first so the z1 cross-section still came out at elen x w, and
            # the ear (narrower than the pocket) did still seat on flat
            # material. But it left a 45 deg flare all the way around the
            # seating plane, which reads as the pocket "rounding up" into
            # its own walls (retainer_cutouts.png) -- and it is an inward-
            # jutting lip at the top of a pocket, so it was buying an
            # overhang rather than removing one.
            piece = _rounded_square_boss(
                ecx, sign * cy, elen / 2, w / 2, z0, z1 - z0,
                RETAINER_EAR_FILLET,
                _retainer_pocket_sharp_corners(sign, merge_corner),
            )
            cutter = piece if cutter is None else cutter.union(piece)
    return cutter


# ---------------------------------------------------------------------------
# BASE half -- battery tub only
# ---------------------------------------------------------------------------

def build_base(break_runout=True):
    base = _rounded_box(OUTER_L, OUTER_W, BASE_DEPTH, 0, CORNER_FILLET).cut(
        _rounded_box(INNER_L, INNER_W, BASE_DEPTH, FLOOR,
                     max(CORNER_FILLET - WALL, 0.5))
    )

    # Cradle pedestal: fills the cavity up to the cell's axis height. The
    # bore is cut from it below, leaving a half-round saddle that hugs the
    # cell, and solid blocks past each end of the bore that act as end stops.
    base = base.union(
        _rounded_box(INNER_L, INNER_W, CELL_AXIS_Z - FLOOR, FLOOR,
                     max(CORNER_FILLET - WALL, 0.5))
    )
    base = base.cut(cell_bore())

    # Guarantee the vertical drop-in path. The cavity above the cradle is
    # already open, so this normally removes nothing -- it is kept as an
    # explicit guard so any feature added here fails verify.py instead of
    # silently trapping the cell.
    base = base.cut(insertion_shaft())

    # No SMA hole in the BASE's portion of the -X end wall -- the mount
    # lives entirely in the PLATE's portion of that same wall instead (see
    # SMA_Z / _sma_cutter()), since the plate's Z-band sits above the cell
    # and isn't limited by SMA_CLEAR_DEPTH the way a base-mounted hole
    # would be.

    # No tongue: the base ends flat at PARTING_Z with a full-thickness wall.
    # The plate's plug drops into the cavity to locate the two halves.

    # Screw bosses, full height, with pilot holes drilled from the top. No
    # retainer feature to merge into here, so only the outward corner (see
    # _screw_boss_sharp_corners()) stays sharp.
    #
    # No fillet at the post-to-cavity-floor junction (where the post rises
    # exposed out of the cradle pedestal, around Z=CELL_AXIS_Z): tried it
    # here and on the plate's posts, and while the edge selection itself
    # was fine, .fillet() on that specific edge set didn't just round the
    # step -- it silently filled in ~26 mm^3 of what should have stayed
    # open cavity, discovered only by diffing the solid before/after (no
    # exception, no warning, just wrong material where the cell needs to
    # pass). Not safe to ship. The *vertical* post-to-wall corners right
    # below are a different matter -- those solve cleanly at every radius
    # tried, and are filleted.
    for (x, y) in screw_positions:
        base = base.union(
            _rounded_square_boss(x, y, M2_BOSS_D / 2, M2_BOSS_D / 2, 0,
                                  BASE_DEPTH, BOSS_CORNER_FILLET,
                                  _screw_boss_sharp_corners(x, y))
        )
    # Blend each post into the two walls it is buried in. The *vertical*
    # post-to-wall corners are well-behaved, unlike the horizontal
    # post-to-floor ones noted above.
    base = _fillet_post_wall_edges(base, -1.0, BASE_DEPTH + 1.0,
                                    BOSS_WALL_FILLET)
    for (x, y) in screw_positions:
        base = base.cut(
            cq.Workplane("XY")
            .workplane(offset=BASE_DEPTH)
            .center(x, y)
            .circle(M2_PILOT_D / 2)
            .extrude(-min(SCREW_ENGAGE + 1.5, BASE_DEPTH - 1.0))
        )

    # Shave the bottom edges to the octagonal profile. The large flanks go on
    # the two long edges only -- that is where the round cell leaves dead
    # corners along its length. The short ends get only a small break, since
    # the cell's flat end face is right behind them.
    base = base.intersect(bottom_chamfer_profile())
    base = base.intersect(end_chamfer_profile())

    # Break the four remaining sharp junctions, where the large flanks run
    # out against the end walls, so nothing around the profile is left sharp.
    # break_runout=False is only for verify.py, to measure what this removes.
    if break_runout:
        base = base.edges(FlankRunoutSelector()).chamfer(PROFILE_EDGE_CHAMFER)

    return base.cut(_usb_cutter())


# ---------------------------------------------------------------------------
# PLATE half -- face plate, carries the board
# ---------------------------------------------------------------------------

def build_plate():
    """Modelled with Z=0 at the plate's underside, which lands on PARTING_Z."""
    plate = _rounded_box(OUTER_L, OUTER_W, PLATE_DEPTH, 0, CORNER_FILLET)

    # Plug: a solid block hanging below the flange, sized to drop into the
    # base cavity. Hollowed out together with the plate below, so it ends up
    # a PLUG_WALL-thick wall continuous with the plate's inner surface.
    plug_outer_l = INNER_L - 2 * FIT_CLEARANCE
    plug_outer_w = INNER_W - 2 * FIT_CLEARANCE
    plate = plate.union(
        _rounded_box(plug_outer_l, plug_outer_w, PLUG_DEPTH, -PLUG_DEPTH,
                     max(CORNER_FILLET - WALL - FIT_CLEARANCE, 0.4))
    )

    # Hollow the plug and the ledge above it, and open the main cavity back
    # to a thin WALL-thick outer wall. Both as ONE cutter, because the step
    # between them is what needs tapering (see below): the plug's inner face
    # and the ledge's inner face end up the same surface -- that ledge is
    # what actually holds the plug on, since the plug is inset well clear of
    # the plate's own wall.
    _hollow_hl = plug_outer_l / 2 - PLUG_WALL
    _hollow_hw = plug_outer_w / 2 - PLUG_WALL
    _void = _rounded_box(
        2 * _hollow_hl, 2 * _hollow_hw,
        PLUG_DEPTH + PLUG_LEDGE + 1, -PLUG_DEPTH - 1, 0.4
    ).union(
        _rounded_box(INNER_L, INNER_W, PLATE_INNER_H - PLUG_LEDGE, PLUG_LEDGE,
                     LIP_CORNER_FILLET)
    )

    # Taper that step at 45 deg instead of leaving it square.
    #
    # The plate prints face-down, so the build direction runs from the top
    # face toward the plug -- every layer is supported by the one at HIGHER
    # local Z. At PLUG_LEDGE the ledge juts LIP_STEP inward of the cavity
    # wall above it, with nothing over it: a full-height right-angle
    # overhang all the way around the lip, antenna cutout included. Cutting
    # the taper into the cutter (rather than filleting the built plate)
    # keeps it a plain deterministic boolean, and puts it before every notch
    # that later carves this same region.
    #
    # The chamfer is taken on the CAVITY's bottom rim only -- the outer of
    # the two edge loops sitting at PLUG_LEDGE. That loop is convex on the
    # cutter, so chamfering shrinks the cutter there, which is what leaves
    # the ramp behind on the plate. The hollow's own top rim is the inner
    # loop and is concave; chamfering it would grow the cutter and eat the
    # lip instead, hence the explicit subtract selector rather than a plain
    # "everything at this Z" band.
    #
    # The cavity box's corner fillet is LIP_CORNER_FILLET, deliberately a
    # hair larger than LIP_CHAMFER: chamfering a rim whose filleted corners
    # are smaller than the chamfer size makes OCCT invert the corner's
    # parallel curve and return an invalid (self-intersecting) cutter, which
    # then corrupts the plate cut below it -- the exact failure this fix
    # removes. With the fillet above the chamfer the taper wraps the whole
    # rim, corners included, as a clean 45 deg ramp.
    _band = (PLUG_LEDGE - 0.05, PLUG_LEDGE + 0.05)
    _void = _void.edges(
        cq.selectors.SubtractSelector(
            cq.selectors.BoxSelector(
                (-OUTER_L, -OUTER_W, _band[0]), (OUTER_L, OUTER_W, _band[1]),
                boundingbox=True),
            cq.selectors.BoxSelector(
                (-_hollow_hl - 0.4, -_hollow_hw - 0.4, _band[0]),
                (_hollow_hl + 0.4, _hollow_hw + 0.4, _band[1]),
                boundingbox=True),
        )
    ).chamfer(LIP_CHAMFER)
    plate = plate.cut(_void)

    # Notch the plug around the base's screw bosses, which rise to the rim.
    # Matches the base's own bosses (same sharp outward corner, grown by
    # FIT_CLEARANCE) -- not the plate's own posts below. Sharing the same
    # sharp corner is required, not just cosmetic: a rounded clearance
    # notch doesn't reach as far out along the diagonal as the base boss's
    # actual sharp corner does, so it used to leave the corner's very tip
    # colliding with the plug (see "no collision: base <-> plate").
    # Grown by BOSS_WALL_FILLET as well as FIT_CLEARANCE: the base's posts
    # now carry a concave blend into the walls (_fillet_post_wall_edges())
    # whose material reaches that much further into the cavity than the
    # bare post does, and the plug has to drop past all of it.
    _notch_half = M2_BOSS_D / 2 + FIT_CLEARANCE + BOSS_WALL_FILLET
    for (x, y) in screw_positions:
        plate = plate.cut(
            _rounded_square_boss(x, y, _notch_half, _notch_half,
                                  -PLUG_DEPTH - 1, PLUG_DEPTH + 1,
                                  BOSS_CORNER_FILLET + FIT_CLEARANCE,
                                  _screw_boss_sharp_corners(x, y))
        )

    # Same idea, for the SMA washer sitting flush against the -X wall.
    plate = plate.cut(_sma_ledge_notch())

    # Build up the USB-C plug recess's collar before anything cuts the
    # recess itself -- it is the block the well's side walls and floor are
    # later left over from. Unioned here, after the cavity has been
    # hollowed out (or the hollow would take it straight back out again)
    # and before the top face is chamfered (it stops at the ceiling, so it
    # can't reach that edge, but the recess it serves does -- see below).
    plate = plate.union(_usb_recess_collar())

    # Break the top outer edge. Done here, while the top face is still a
    # plain rectangle, so the edge selection cannot pick up the window or
    # the screw counterbores cut later.
    plate = plate.faces(">Z").edges().chamfer(FACE_CHAMFER)

    # Board retention: a shoulder (Y registration + top-face contact) along
    # both long edges, attached to the plate's own side wall as well as its
    # ceiling -- no support needed to print it, unlike the rib-from-ceiling
    # shoulder this replaced. The board is lifted straight up into it from
    # the plate's open underside; nothing here needs it to slide. The
    # shoulder's own +X end doubles as the board's X endstop, which is what
    # keeps the USB-C connector registered against the case's cutout.
    #
    # What stops the board falling back out again is the separate retainer
    # plank (build_retainer()), screwed to the two bosses added below, which
    # press up against the underside connectors once the board is in place.
    rail_x0 = BOARD_FAR_END_X - 1.0
    rail_x1 = BOARD_CONNECTOR_END_X
    rail_len = rail_x1 - rail_x0
    shoulder_h = PLATE_INNER_H - BOARD_TOP_LOCAL

    for sign in (1, -1):
        shoulder_cy = sign * (RAIL_SHOULDER_INNER_Y + SHOULDER_OUTER_Y) / 2
        shoulder_w = SHOULDER_OUTER_Y - RAIL_SHOULDER_INNER_Y
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL)
            .center((rail_x0 + rail_x1) / 2, shoulder_cy)
            .rect(rail_len, shoulder_w)
            .extrude(shoulder_h)
        )
        # Preload dimple: local interference the board elastically
        # compresses as the retainer clamps it home, so it doesn't rattle.
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL - PRELOAD_BUMP_INTERFERENCE)
            .center((rail_x0 + rail_x1) / 2, sign * (RAIL_SHOULDER_INNER_Y + RAIL_OUTER_Y) / 2)
            .rect(PRELOAD_BUMP_LEN, RAIL_OUTER_Y - RAIL_SHOULDER_INNER_Y)
            .extrude(PRELOAD_BUMP_INTERFERENCE)
        )

    # Retainer mounting bosses: hang from the shoulder's own underside (so
    # they inherit its wall+ceiling support) down to exactly the retainer
    # plank's own contact height -- boss_z0 is the same Z the retainer's ear
    # top face sits at (see build_retainer()), so the two meet flush with no
    # gap -- outboard of the board. The dead zone between the board's own
    # pocket edge (RAIL_OUTER_Y) and the wall's inner face (SHOULDER_OUTER_Y)
    # is only 2.45mm wide -- too narrow for a free-standing round boss
    # without either overlapping the board or poking through the wall -- so
    # each boss is a block that exactly fills that gap, recessed
    # RETAINER_BOSS_RECESS further into the solid wall (see that constant),
    # rather than a cylinder placed within it. One pair per connector
    # position. A pilot hole is drilled from the bottom for the retainer's
    # own screw.
    retainer_top_local = BOARD_UNDER_LOCAL - CONN_H
    boss_z0 = retainer_top_local
    boss_h = BOARD_TOP_LOCAL - boss_z0
    boss_y0, boss_y1 = RAIL_OUTER_Y, RETAINER_BOSS_Y1
    boss_cy = (boss_y0 + boss_y1) / 2
    boss_w = boss_y1 - boss_y0
    for conn_x, merge_corner in RETAINER_CONNECTORS:
        # Same width as the pocket it roofs (_retainer_pocket_x_range), so
        # no step of bare ledge is left standing around the boss's footprint.
        bx0, bx1 = _retainer_pocket_x_range(conn_x, merge_corner)
        bcx = (bx0 + bx1) / 2
        blen = bx1 - bx0
        for sign in (1, -1):
            # Outboard corners square, matching the pocket below; a merged
            # boss also keeps its +X pair square so it unions flush into the
            # corner screw post, which leaves its own facing corners sharp
            # too (see _screw_boss_sharp_corners()) -- two flat, unrounded
            # faces merge with no taper, unlike the old fillet-vs-cylinder
            # union that left a wafer-thin sliver bridging the two (see
            # lid_artifacts.png).
            boss_block = _rounded_square_boss(
                bcx, sign * boss_cy, blen / 2, boss_w / 2, boss_z0, boss_h,
                RETAINER_EAR_FILLET,
                _retainer_pocket_sharp_corners(sign, merge_corner),
            )
            plate = plate.union(boss_block)
            # Blend the boss into everything it lands on, rather than
            # leaving it a bare block standing off the surrounding surfaces.
            # Two kinds of concave junction, both boxed tight to the single
            # edge they mean so the boss's own vertical corner edges
            # (already rounded, or deliberately sharp -- see `sharp` above)
            # can't be caught by the same selector:
            #
            #   - overhead, where the boss's inner face (Y=boss_y0) meets
            #     the wider shoulder: RAIL_SHOULDER_INNER_Y is inboard of
            #     boss_y0, so the shoulder overhangs the boss on that side.
            #   - at each FREE X end, where the boss's end face butts into
            #     the plate's own side wall at boss_y1 (RETAINER_BOSS_Y1,
            #     recessed into the wall -- see that constant). The merged
            #     end (bx1 under merge_corner) has no such edge -- it runs
            #     into the corner screw post and unions with it instead.
            #
            # All of them go into ONE .fillet() call. Filleting them one at
            # a time fails outright (StdFail_NotDone at every radius tried,
            # down to 0.1) because these edges meet each other: whichever
            # runs second has to terminate its fillet surface into the
            # first's, which OCCT won't solve. Handed the whole set at once
            # it resolves the shared corners itself.
            _sel = cq.selectors.BoxSelector(
                (bx0 - 0.5, sign * boss_y0 - 0.1, BOARD_TOP_LOCAL - 0.1),
                (bx1 + 0.5, sign * boss_y0 + 0.1, BOARD_TOP_LOCAL + 0.1),
                boundingbox=True,
            )
            for end_x, free in ((bx0, True), (bx1, not merge_corner)):
                if not free:
                    continue
                # The boss's OUTBOARD corners are square now
                # (_retainer_pocket_sharp_corners), so its end face runs
                # straight to the wall and the edge sits at end_x itself --
                # no arc to step past, unlike when those corners were
                # rounded and the edge sat a fillet radius inboard.
                tx = end_x
                wall_y = sign * boss_y1
                _sel = cq.selectors.SumSelector(_sel, cq.selectors.BoxSelector(
                    (tx - 0.05, min(wall_y - 0.05, wall_y + 0.05), boss_z0 - 0.05),
                    (tx + 0.05, max(wall_y - 0.05, wall_y + 0.05), boss_z0 + boss_h + 0.05),
                    boundingbox=True,
                ))
            plate = plate.edges(_sel).fillet(RETAINER_BOSS_WALL_FILLET)
            # The screw itself stays near the connector, not shifted out to
            # the merged corner -- only the surrounding block is stretched.
            plate = plate.cut(
                cq.Workplane("XY")
                .workplane(offset=boss_z0)
                .center(conn_x, sign * boss_cy)
                .circle(RETAINER_SCREW_PILOT_D / 2)
                .extrude(RETAINER_SCREW_ENGAGE)
            )

    # The half-lap ledge (solid Z 0 -> PLUG_LEDGE at this same outboard Y
    # band, see PLUG_LEDGE below) would otherwise foul the retainer's ears,
    # which sit right on top of it -- notch it locally, the same pattern
    # already used for the case screw bosses and the SMA washer.
    plate = plate.cut(_retainer_ear_notch())

    # Case screw posts: rise from the flange underside to the plate ceiling,
    # in line with the base's bosses. The counterbore goes clean through the
    # top wall, so it is the *top of these posts* the screw head bears on --
    # without them the head would have nothing to seat against at all. The
    # +X posts leave their -X corners sharp so the retainer boss (added
    # above) merges flush into them -- see _screw_boss_sharp_corners(). No
    # fillet at the post-to-ledge/ceiling junctions -- see build_base()'s
    # matching note; the same .fillet() call silently filled in cavity
    # volume instead of just rounding the step, here too.
    for (x, y) in screw_positions:
        plate = plate.union(
            _rounded_square_boss(x, y, M2_BOSS_D / 2, M2_BOSS_D / 2, 0,
                                  PLATE_INNER_H, BOSS_CORNER_FILLET,
                                  _screw_boss_sharp_corners(x, y))
        )
    # Same vertical post-to-wall blends the base gets. Only six edges here,
    # not eight: at the +X posts the retainer boss already occupies that
    # corner and carries its own blend instead.
    plate = _fillet_post_wall_edges(plate, -1.0, PLATE_INNER_H + 1.0,
                                     BOSS_WALL_FILLET)

    # OLED window through the top face, then bevel its outer edge. Using the
    # chamfer tool on the finished edge keeps the cutter a plain prism, so
    # the aperture stays exactly OLED_WINDOW_W x OLED_WINDOW_H at its narrowest.
    #
    # .faces(">Z").edges() would also pick up the plate's outer perimeter, so
    # the window's four edges are isolated with a box selector around them.
    plate = plate.cut(_oled_window_cutter())
    _pad = WINDOW_CHAMFER + 1.0
    plate = (
        plate.faces(">Z")
        .edges(
            cq.selectors.BoxSelector(
                (OLED_CENTER_X - OLED_WINDOW_W / 2 - _pad,
                 OLED_CENTER_Y - OLED_WINDOW_H / 2 - _pad,
                 PLATE_DEPTH - 1.0),
                (OLED_CENTER_X + OLED_WINDOW_W / 2 + _pad,
                 OLED_CENTER_Y + OLED_WINDOW_H / 2 + _pad,
                 PLATE_DEPTH + 1.0),
                boundingbox=True,
            )
        )
        .chamfer(WINDOW_CHAMFER)
    )

    # Screw clearance holes with socket-head counterbores
    for (x, y) in screw_positions:
        plate = plate.cut(
            cq.Workplane("XY").center(x, y).circle(M2_SHAFT_D / 2).extrude(PLATE_DEPTH)
        )
        plate = plate.cut(
            cq.Workplane("XY")
            .workplane(offset=PLATE_DEPTH - M2_HEAD_H)
            .center(x, y)
            .circle(M2_HEAD_D / 2)
            .extrude(M2_HEAD_H + 1)
        )

    plate = plate.cut(_sma_cutter())

    # Button actuator holes: a plain constant-diameter through-hole for the
    # bridge's post -- no counterbore, since the post itself has no wider
    # head to recess (see the button bridge config block for why).
    for (x, y) in button_positions:
        plate = plate.cut(
            cq.Workplane("XY").center(x, y).circle(BUTTON_HOLE_D / 2).extrude(PLATE_DEPTH)
        )

    # The USB-C plug recess, cut last: it breaks through the top face, so it
    # has to come after that face's own chamfer (which selects every edge on
    # the top face, and would otherwise pick up the well's mouth as well --
    # the same reason the OLED window is cut after it).
    plate = plate.cut(_usb_recess_cutter())

    return plate.cut(_usb_cutter().translate((0, 0, -PARTING_Z)))


# ---------------------------------------------------------------------------
# COMPONENTS -- mock solids used to check fit, not printed
# ---------------------------------------------------------------------------

def build_cell():
    """26650 cell, lying along X, concentric with the (offset) cradle bore."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=CELL_OFFSET_X - CELL_L / 2)
        .center(0, CELL_AXIS_Z)
        .circle(CELL_D / 2)
        .extrude(CELL_L)
    )


def build_board():
    """Simplified Heltec V4: PCB + OLED module + USB-C + u.FL connector on
    top, GPS + battery/solar connectors on the underside."""
    pcb = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_UNDER_Z)
        .center(BOARD_CENTER_X, 0)
        .box(BOARD_L, BOARD_W, BOARD_T, centered=(True, True, False))
        .edges("|Z")
        .chamfer(BOARD_CORNER_CHAMFER)
    )

    oled = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_TOP_Z)
        .center(OLED_CENTER_X, OLED_CENTER_Y)
        .rect(OLED_MODULE_W, OLED_MODULE_H)
        .extrude(OLED_MODULE_THICK)
    )
    usb = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_TOP_Z)
        .center(USB_CENTER_X, 0)
        .rect(USB_DEPTH, USB_W)
        .extrude(USB_H)
    )
    ufl = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_TOP_Z)
        .center(BOARD_FAR_END_X + UFL_FROM_END, 0)
        .rect(UFL_SIZE, UFL_SIZE)
        .extrude(UFL_H)
    )
    # GPS module connector, on the underside below the OLED module. Position
    # is edge-referenced (calipers, off the antenna-end PCB edge), not
    # centred under the OLED module -- the two don't coincide on the real
    # board.
    gps_conn = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_UNDER_Z)
        .center(GPS_CONN_X, 0)
        .rect(CONN_W, CONN_D)
        .extrude(-CONN_H)
    )
    # Battery + solar panel connectors, on the underside below USB-C.
    # Position is edge-referenced (calipers, off the USB-C-end PCB edge).
    power_conn = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_UNDER_Z)
        .center(POWER_CONN_X, 0)
        .rect(CONN_W, CONN_D)
        .extrude(-CONN_H)
    )
    # The two tactile buttons (PRG/boot and RST), top-mounted alongside USB-C.
    buttons = None
    for bx, by in button_positions:
        b = (
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_Z)
            .center(bx, by)
            .rect(BUTTON_W, BUTTON_D)
            .extrude(BUTTON_H)
        )
        buttons = b if buttons is None else buttons.union(b)

    return (pcb.union(oled).union(usb).union(ufl).union(gps_conn)
            .union(power_conn).union(buttons))


def build_sma_connector():
    """Mock of the SMA bulkhead jack, mounted axially through the plate's
    own -X end wall at (Y=0, SMA_Z). Outward (-X) to inward (+X), per the
    datasheet: the threaded barrel (mostly exposed outside the case), the
    washer -- flush against the wall's inside face at SMA_WASHER_OUTER_X,
    no offset -- the fixed nut right behind it, then the stiff pigtail
    stub."""
    barrel = (
        cq.Workplane("YZ")
        .workplane(offset=SMA_WASHER_OUTER_X)
        .center(0, SMA_Z)
        .circle(SMA_THREAD_MAJOR_MAX / 2)
        .extrude(-SMA_BARREL_L)
    )
    washer = (
        cq.Workplane("YZ")
        .workplane(offset=SMA_WASHER_OUTER_X)
        .center(0, SMA_Z)
        .circle(SMA_WASHER_OD / 2)
        .extrude(SMA_WASHER_T)
    )
    nut = (
        cq.Workplane("YZ")
        .workplane(offset=SMA_WASHER_OUTER_X + SMA_WASHER_T)
        .center(0, SMA_Z)
        .polygon(6, SMA_NUT_AF / math.cos(math.pi / 6))
        .extrude(SMA_NUT_T)
    )
    stub = (
        cq.Workplane("YZ")
        .workplane(offset=SMA_WASHER_OUTER_X + SMA_WASHER_T + SMA_NUT_T)
        .center(0, SMA_Z)
        .circle(SMA_PIGTAIL_D / 2)
        .extrude(SMA_PIGTAIL_L)
    )
    return barrel.union(nut).union(washer).union(stub)


def build_retainer():
    """Separate printed retainer plank -- the second half of board retention
    alongside the plate's registration shoulder (see build_plate()). Global
    coordinates, like the other real (printable or mock) parts.

    Installed after the board is lifted into the shoulder: held up by hand
    against the GPS and battery/solar connector housings on the board's
    underside, then screwed to the two boss pairs hanging off the shoulder.
    Two ears per connector position reach out from the plank's own body to
    the mounting bosses, each carrying a clearance hole for the screw.
    """
    top_z = BOARD_UNDER_Z - CONN_H
    plank = (
        cq.Workplane("XY")
        .workplane(offset=top_z - RETAINER_THICKNESS)
        .center((RETAINER_X0 + RETAINER_X1) / 2, 0)
        .rect(RETAINER_X1 - RETAINER_X0, RETAINER_WIDTH)
        .extrude(RETAINER_THICKNESS)
        .edges("|Z")
        .fillet(RETAINER_EAR_FILLET)
    )
    # Ears reach from the boss out at RETAINER_BOSS_Y1 back in to just past
    # the plank's own edge -- a 1mm overlap into the plank body guarantees a
    # fused connection (the same disconnection bug the old rail/lip design
    # had) without making the ear as wide as the whole half-plate the way
    # reaching all the way back to the centreline would. RETAINER_BOSS_Y1
    # (not the bare wall face SHOULDER_OUTER_Y) is what actually matters
    # here: it is what gives the ear's own clearance hole a real wall on
    # its outboard side (see RETAINER_BOSS_RECESS).
    ear_y0 = RETAINER_WIDTH / 2 - 1.0
    ear_y1 = RETAINER_BOSS_Y1
    ear_cy = (ear_y0 + ear_y1) / 2
    ear_w = ear_y1 - ear_y0
    for conn_x, _merge_corner in RETAINER_CONNECTORS:
        # Deliberately ignores _merge_corner: this ear is part of the
        # RETAINER, a separate physical part from the plate. The plate's
        # own boss is safe to stretch out and merge into the corner screw
        # post (same part, unions cleanly) -- but if this ear did the same,
        # it would try to occupy the same space as that post once both
        # parts are assembled, which is a real collision between two
        # different solids, not a harmless union.
        ex0, ex1 = _retainer_ear_x_range(conn_x, False)
        ecx = (ex0 + ex1) / 2
        elen = ex1 - ex0
        for sign in (1, -1):
            ear = (
                cq.Workplane("XY")
                .workplane(offset=top_z - RETAINER_THICKNESS)
                .center(ecx, sign * ear_cy)
                .rect(elen, ear_w)
                .extrude(RETAINER_THICKNESS)
                .edges("|Z")
                .fillet(RETAINER_EAR_FILLET)
            )
            plank = plank.union(ear)
            plank = plank.cut(
                cq.Workplane("XY")
                .workplane(offset=top_z - RETAINER_THICKNESS - 0.5)
                .center(conn_x, sign * RETAINER_BOSS_CY)
                .circle(RETAINER_SCREW_SHAFT_D / 2)
                .extrude(RETAINER_THICKNESS + 1.0)
            )
    return plank


def build_button_bridge():
    """Separate printed part carrying both button actuators, joined under
    the lid instead of two loose pieces. Global coordinates, like the other
    real (printable or mock) parts -- both real hole positions are baked in
    directly, so this is built once, not mirrored at use time.

    Round posts pass through the plate's ceiling holes (build_plate()) down
    to a flat bracket that reaches the real buttons. The bracket is routed
    in a C: two arms run in X from the spine out to each button position at
    Y = +-BUTTON_Y, clear of the USB-C connector the whole way since the
    connector's Y half-span (USB_W/2 = 4.5) never reaches BUTTON_Y (8.15);
    the spine then joins the two arms at X = BUTTON_SPINE_X, inboard of
    (and BUTTON_BRIDGE_CLEARANCE clear of) the connector's own footprint.
    A straight Y-running bridge between the buttons would cut right through
    the connector -- it sits flush against the ceiling with zero spare
    headroom (CEILING_CLEARANCE == USB_H), so it can only be dodged
    in-plane, not stepped over.

    Dropped straight down as one rigid motion during assembly: both posts
    are vertical and parallel, so both reach the outer face at the same
    moment the arms sweep down into the open ceiling cavity. Simplest done
    before the board goes in, like the retainer.

    Each post is a single constant diameter (BUTTON_POST_D) from the arm's
    own bottom face up to (near) flush with the plate's outer face -- no
    wider head, no counterbore (see the config block above for why). It
    starts at BUTTON_ARM_BOTTOM_Z, the same level as the arm's own bottom
    rather than its top, so post and arm overlap through the arm's full
    thickness instead of only touching at one Z-plane.

    The two posts are NOT the same length: RST is recessed BUTTON_RST_OFFSET
    below the outer face (reachable, but not so exposed it gets pressed by
    accident), and PRG sits proud by the same amount (BUTTON_PRG_OFFSET),
    since it's the one actually reached for everyday use. Each post's
    pressable top edge gets a BUTTON_TOP_CHAMFER break.
    """
    bracket = (
        cq.Workplane("XY")
        .workplane(offset=BUTTON_ARM_BOTTOM_Z)
        .center(BUTTON_SPINE_X, 0)
        .rect(BUTTON_ARM_W, 2 * BUTTON_Y + BUTTON_ARM_W)
        .extrude(BUTTON_ARM_T)
    )
    for bx, by, top_offset in button_actuators:
        arm = (
            cq.Workplane("XY")
            .workplane(offset=BUTTON_ARM_BOTTOM_Z)
            .center((BUTTON_SPINE_X + bx) / 2, by)
            .rect(bx - BUTTON_SPINE_X, BUTTON_ARM_W)
            .extrude(BUTTON_ARM_T)
        )
        post = (
            cq.Workplane("XY")
            .workplane(offset=BUTTON_ARM_BOTTOM_Z)
            .center(bx, by)
            .circle(BUTTON_POST_D / 2)
            .extrude(BUTTON_POST_H + top_offset)
            .faces(">Z")
            .chamfer(BUTTON_TOP_CHAMFER)
        )
        bracket = bracket.union(arm).union(post)
    return bracket


def assemble():
    """All solids positioned in the assembled coordinate frame."""
    return {
        "base": build_base(),
        "plate": build_plate().translate((0, 0, PARTING_Z)),
        "cell": build_cell(),
        "board": build_board(),
        "sma": build_sma_connector(),
        "retainer": build_retainer(),
        "button_bridge": build_button_bridge(),
    }


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    parts = assemble()
    exporters.export(parts["base"], "output/heltec_v4_case_base.stl")
    exporters.export(parts["base"], "output/heltec_v4_case_base.step")
    exporters.export(build_plate(), "output/heltec_v4_case_plate.stl")
    exporters.export(build_plate(), "output/heltec_v4_case_plate.step")
    exporters.export(parts["retainer"], "output/heltec_v4_case_retainer.stl")
    exporters.export(parts["retainer"], "output/heltec_v4_case_retainer.step")
    exporters.export(parts["button_bridge"], "output/heltec_v4_case_button_bridge.stl")
    exporters.export(parts["button_bridge"], "output/heltec_v4_case_button_bridge.step")

    assy = cq.Assembly()
    assy.add(parts["base"], name="base", color=cq.Color(0.25, 0.55, 0.85, 1.0))
    assy.add(parts["plate"], name="plate", color=cq.Color(0.90, 0.60, 0.20, 0.6))
    assy.add(parts["cell"], name="cell", color=cq.Color(0.35, 0.75, 0.35, 1.0))
    assy.add(parts["board"], name="board", color=cq.Color(0.80, 0.25, 0.25, 1.0))
    assy.add(parts["sma"], name="sma", color=cq.Color(0.75, 0.75, 0.78, 1.0))
    assy.add(parts["retainer"], name="retainer", color=cq.Color(0.55, 0.55, 0.95, 1.0))
    assy.add(parts["button_bridge"], name="button_bridge", color=cq.Color(0.95, 0.85, 0.20, 1.0))
    assy.save("output/heltec_v4_case_assembly.step")
    assy.save("output/heltec_v4_case_assembly.stl")
    assy.save("output/heltec_v4_case_assembly.gltf")

    print("Exported STL/STEP/glTF to ./output/")
    print(f"Outer size    : {OUTER_L:.1f} x {OUTER_W:.1f} x {TOTAL_HEIGHT:.1f} mm")
    print(f"Insertion shaft: {SHAFT_L:.1f} x {SHAFT_W:.1f} mm, "
          f"Z {SHAFT_Z0:.2f} -> {SHAFT_Z1:.2f}")
    print(f"Bottom chamfer: run {CHAMFER_RUN:.2f} rise {CHAMFER_RISE:.2f} mm, "
          f"{CHAMFER_OVERHANG_DEG:.1f} deg overhang, stands on {BOTTOM_W:.2f} mm")
    print(f"End chamfer   : run {END_CHAMFER_RUN:.2f} rise {END_CHAMFER_RISE:.2f} mm, "
          f"{END_CHAMFER_OVERHANG_DEG:.1f} deg overhang, stands on {BOTTOM_L:.2f} mm")
    print(f"Parting line  : Z {PARTING_Z:.2f}   board underside Z {BOARD_UNDER_Z:.2f}")

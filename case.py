"""
Parametric CadQuery case for a Heltec V4 board (ESP32-S3, no GPS variant),
IPEX-to-SMA antenna pigtail, and a 26650 Li-ion cell.

Two-piece design:
  - BASE half:  battery tub -- cradle plus a straight rectangular shaft so
                the cell drops in vertically. Carries no board features.
  - PLATE half: face plate with the OLED window; carries the board on posts
                that hang from its ceiling.

The cell lies along the case's long axis, centred directly *underneath* the
board. Because the cell is both wider and longer than the board, anything
supporting the board from the base would stand inside the cell's insertion
path -- so the board hangs from the plate instead. See README.md.

Board dimensions come from a Heltec mechanical reference drawing; some
component heights are still estimates -- see README.md.

Usage:
    python3 case.py       # export STL/STEP of both halves, plus a coloured
                           # STEP/STL/glTF assembly (base, plate, cell, board,
                           # screws) for viewing
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
OLED_MODULE_THICK = 4.0      # (est) module height above the PCB top face
OLED_TOP_GAP = 0.5           # clearance between module top and window underside
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
USB_H = 3.2              # (est) connector body height above the PCB
USB_DEPTH = 7.0          # (est) how far the body extends onto the board
USB_OVERHANG = 1.0       # how far it protrudes past the board edge

# u.FL / IPEX antenna connector, near the -X end of the board
UFL_SIZE = 3.0
UFL_H = 1.6              # (est) height above the PCB
UFL_FROM_END = 4.0       # centre distance from the -X board edge

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
CONN_W = 4.8   # X extent, measured off the side-view photo
CONN_D = 4.8   # (est) Y depth -- not visible in the side view, assumed
               # square, same convention as UFL_SIZE
CONN_H = 4.0   # measured protrusion below the PCB
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

# --- Board retention (rail/lip channel on the PLATE) -------------------------
# The board has no mounting holes (confirmed off the real board photo), so it
# can't hang from screw posts. Instead it's captured by a shoulder + lip that
# runs along both long edges of the plate's cavity: the board is lifted up
# into the plate from its open underside, then slid a few mm to engage the
# lip, which hooks under its underside so it can't drop back out. The base is
# not involved -- the cell's bore underlies the board's whole length, so a
# base-side pedestal would have to clear the cell *and* poke up past the
# parting line (see the module docstring for why the board hangs from the
# plate, not the base).
M2_BOSS_D = 5.5             # case corner screw bosses (base + plate)
RAIL_SHOULDER_INNER_Y = 10.5     # inner edge of the wide registration shoulder;
                                  # clears the OLED window half-height by ~0.6mm
RAIL_OUTER_Y = BOARD_W / 2 + BOARD_CLEARANCE   # 13.2, pocket's outer edge
RAIL_LIP_WIDTH = 1.5             # how far the retaining lip overhangs inward --
                                  # short printable bridge, not a support-needing
                                  # overhang
RAIL_LIP_INNER_Y = RAIL_OUTER_Y - RAIL_LIP_WIDTH   # 11.7
BOARD_SLOT_CLEARANCE = 0.3       # Z slack the board has inside the channel
PRELOAD_BUMP_INTERFERENCE = 0.2  # local shoulder protrusion, elastically
                                  # compressed when the board seats home, so it
                                  # doesn't rattle in BOARD_SLOT_CLEARANCE
PRELOAD_BUMP_LEN = 3.0           # mm along X -- short local dimple, not a
                                  # full-length feature
LIP_LEAD_IN = 5.0                # mm of rail length left lip-free at the -X
                                  # end, as the insertion gap the board enters
                                  # through before sliding home under the lip

# --- M2 socket-head cap screw fasteners -------------------------------------
M2_SHAFT_D = 2.2           # clearance hole for the screw shaft
M2_HEAD_D = 4.0            # socket head diameter clearance
M2_PILOT_D = 1.6           # pilot hole in the boss that receives the screw

# Push the boss out into the corner as far as it can go without poking
# through the case's own outer (filleted) surface. Its closest approach to
# the outside is along the corner's 45 deg diagonal, where the outer profile
# is the CORNER_FILLET arc rather than a flat wall -- solved so the boss
# (radius M2_BOSS_D/2, plus a small BOSS_OUTER_MARGIN of backing material)
# is tangent to that arc:
#
#   inset = CORNER_FILLET*(1 - 1/sqrt(2)) + (M2_BOSS_D/2 + BOSS_OUTER_MARGIN)/sqrt(2)
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
BOSS_OUTER_MARGIN = 0.3    # backing material left outside the boss at its
                            # closest approach to the outer surface
COUNTERBORE_MARGIN = 0.2   # buffer beyond exact tangency to the face chamfer
_inset_corner = (CORNER_FILLET * (1 - 1 / math.sqrt(2))
                 + (M2_BOSS_D / 2 + BOSS_OUTER_MARGIN) / math.sqrt(2))
_inset_counterbore = M2_HEAD_D / 2 + FACE_CHAMFER + COUNTERBORE_MARGIN
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
PLATE_INNER_H = OLED_TOP_Z - PARTING_Z + OLED_TOP_GAP
PLATE_DEPTH = PLATE_INNER_H + WALL
TOTAL_HEIGHT = PARTING_Z + PLATE_DEPTH

# Case screws pass through a post in the plate (which the head seats on top
# of) and thread into the base's boss below, so they must be long enough to
# cross the post and still bite. Engagement is what is left over.
SCREW_LEN = 16.0           # M2x16 SHCS for the case halves
SCREW_ENGAGE = SCREW_LEN - PLATE_INNER_H

# --- Derived plan dimensions ------------------------------------------------
# Width is set by the cell (which is wider than the board) plus side walls.
INNER_W = max(BOARD_W + 2 * BOARD_CLEARANCE, CELL_D + CELL_CLEARANCE) + 4.0
OUTER_W = INNER_W + 2 * WALL

# Length must leave room for the corner screw bosses *beyond* the ends of the
# cell's insertion shaft -- the shaft spans most of the cavity width, so a
# boss anywhere within its length would stand in the cell's way. The shaft is
# off-centre (CELL_OFFSET_X), so CELL_FAR_HALF_LEN (the +X/USB side, which is
# now the closer one) is what sizes this -- the outer envelope is symmetric,
# so both sides grow to match the tighter one, and the -X/antenna side ends
# up with CELL_OFFSET_X of extra clearance beyond what this alone requires.
# Kept to the same order as the other minimal-but-safe clearances in this
# file (BOARD_BOSS_CLEARANCE etc.), now that the boss itself sits much
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
BOARD_BOSS_CLEARANCE = 0.3       # gap kept from the +X corner screw boss
_shift_for_usb = (INNER_L / 2 - BOARD_USB_WALL_CLEARANCE) - (BOARD_L / 2 + USB_OVERHANG)
_shift_max_boss = (OUTER_L / 2 - SCREW_INSET) - M2_BOSS_D / 2 - BOARD_BOSS_CLEARANCE \
                  - (BOARD_L / 2 + BOARD_CLEARANCE)
# Getting closer than this would mean moving/shrinking the corner boss or
# growing OUTER_L -- out of scope here.
BOARD_CENTER_X = min(_shift_for_usb, _shift_max_boss)

BOARD_CONNECTOR_END_X = BOARD_L / 2 + BOARD_CENTER_X
BOARD_FAR_END_X = -BOARD_L / 2 + BOARD_CENTER_X
OLED_CENTER_X += BOARD_CENTER_X
USB_CENTER_X = BOARD_CONNECTOR_END_X + USB_OVERHANG - USB_DEPTH / 2

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
    """
    return (
        cq.Workplane("YZ")
        .workplane(offset=OUTER_L / 2 + 2)
        .center(0, BOARD_TOP_Z + USB_H / 2)
        .rect(USB_W + 1.0, USB_H + 1.0)
        .extrude(-(WALL + 8))
    )


def _sma_cutter():
    """SMA panel hole, axial through the plate's own -X end wall at
    (Y=0, SMA_Z_LOCAL) -- plate-local coordinates (Z=0 at the parting
    line). Just the wall itself: the washer that sits flush behind it
    needs the half-lap ledge notched separately (see _sma_ledge_notch()),
    since the ledge is wider than this hole."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=-OUTER_L / 2)
        .center(0, SMA_Z_LOCAL)
        .circle(SMA_HOLE_D / 2)
        .extrude(WALL + 2)
    )


def _sma_ledge_notch():
    """Clears the half-lap ledge/plug locally where the SMA washer sits
    flush against the wall -- same pattern as the screw-boss notches
    below, just swept along X (the connector's own axis) instead of Z.
    Starts at the wall's *inner* face, not the outer one: the actual
    through-wall hole stays barrel-sized (_sma_cutter()) -- this only
    widens the ledge/plug material behind it, not the wall itself."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=-INNER_L / 2)
        .center(0, SMA_Z_LOCAL)
        .circle(SMA_NOTCH_R)
        .extrude(SMA_WASHER_T + 1.5)
    )


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

    # Screw bosses, full height, with pilot holes drilled from the top.
    # These sit beyond the ends of the shaft (enforced by OUTER_L above).
    for (x, y) in screw_positions:
        base = base.union(
            cq.Workplane("XY").center(x, y).circle(M2_BOSS_D / 2).extrude(BASE_DEPTH)
        )
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

    # Hollow the plug and the ledge above it in one cut, so the plug's inner
    # face and the ledge's inner face are the same surface -- that ledge is
    # what actually holds the plug on, since the plug is inset well clear of
    # the plate's own wall.
    plate = plate.cut(
        _rounded_box(plug_outer_l - 2 * PLUG_WALL, plug_outer_w - 2 * PLUG_WALL,
                     PLUG_DEPTH + PLUG_LEDGE + 1, -PLUG_DEPTH - 1, 0.4)
    )

    # Main cavity above the ledge, back to a thin WALL-thick outer wall.
    plate = plate.cut(
        _rounded_box(INNER_L, INNER_W, PLATE_INNER_H - PLUG_LEDGE, PLUG_LEDGE,
                     max(CORNER_FILLET - WALL, 0.5))
    )

    # Notch the plug around the base's screw bosses, which rise to the rim.
    for (x, y) in screw_positions:
        plate = plate.cut(
            cq.Workplane("XY")
            .workplane(offset=-PLUG_DEPTH - 1)
            .center(x, y)
            .circle(M2_BOSS_D / 2 + FIT_CLEARANCE)
            .extrude(PLUG_DEPTH + 1)
        )

    # Same idea, for the SMA washer sitting flush against the -X wall.
    plate = plate.cut(_sma_ledge_notch())

    # Break the top outer edge. Done here, while the top face is still a
    # plain rectangle, so the edge selection cannot pick up the window or
    # the screw counterbores cut later.
    plate = plate.faces(">Z").edges().chamfer(FACE_CHAMFER)

    # Board retention: a shoulder (Y registration + top-face contact) plus a
    # narrower lip (traps the underside) along both long edges. The board is
    # lifted up into the plate through its open underside, then slid toward
    # +X to hook under the lip -- LIP_LEAD_IN at the -X end is where it
    # enters unobstructed. The rails' +X ends double as the board's X
    # endstop, which is what keeps the USB-C connector registered against
    # the case's cutout.
    rail_x0 = BOARD_FAR_END_X - 1.0
    rail_x1 = BOARD_CONNECTOR_END_X
    rail_len = rail_x1 - rail_x0
    lip_x0 = rail_x0 + LIP_LEAD_IN
    lip_len = rail_x1 - lip_x0
    shoulder_h = PLATE_INNER_H - BOARD_TOP_LOCAL
    # The lip is a thin shelf that only occupies the slot clearance just
    # below the board's underside -- it must NOT reach up to BOARD_TOP_LOCAL,
    # or it would fill the whole board-thickness slot the board sits in.
    lip_bottom = BOARD_UNDER_LOCAL - BOARD_SLOT_CLEARANCE
    lip_h = BOARD_SLOT_CLEARANCE

    for sign in (1, -1):
        shoulder_cy = sign * (RAIL_SHOULDER_INNER_Y + RAIL_OUTER_Y) / 2
        shoulder_w = RAIL_OUTER_Y - RAIL_SHOULDER_INNER_Y
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL)
            .center((rail_x0 + rail_x1) / 2, shoulder_cy)
            .rect(rail_len, shoulder_w)
            .extrude(shoulder_h)
        )
        lip_cy = sign * (RAIL_LIP_INNER_Y + RAIL_OUTER_Y) / 2
        lip_w = RAIL_OUTER_Y - RAIL_LIP_INNER_Y
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=lip_bottom)
            .center((lip_x0 + rail_x1) / 2, lip_cy)
            .rect(lip_len, lip_w)
            .extrude(lip_h)
        )
        # Preload dimple: local interference the board elastically
        # compresses as it seats home, so it doesn't rattle in
        # BOARD_SLOT_CLEARANCE.
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL - PRELOAD_BUMP_INTERFERENCE)
            .center((rail_x0 + rail_x1) / 2, shoulder_cy)
            .rect(PRELOAD_BUMP_LEN, shoulder_w)
            .extrude(PRELOAD_BUMP_INTERFERENCE)
        )

    # Case screw posts: rise from the flange underside to the plate ceiling,
    # in line with the base's bosses. The counterbore goes clean through the
    # top wall, so it is the *top of these posts* the screw head bears on --
    # without them the head would have nothing to seat against at all.
    for (x, y) in screw_positions:
        plate = plate.union(
            cq.Workplane("XY")
            .center(x, y)
            .circle(M2_BOSS_D / 2)
            .extrude(PLATE_INNER_H)
        )

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
    gps_conn_x = BOARD_FAR_END_X + CONN_GPS_EDGE_GAP + CONN_W / 2
    gps_conn = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_UNDER_Z)
        .center(gps_conn_x, 0)
        .rect(CONN_W, CONN_D)
        .extrude(-CONN_H)
    )
    # Battery + solar panel connectors, on the underside below USB-C.
    # Position is edge-referenced (calipers, off the USB-C-end PCB edge).
    power_conn_x = BOARD_CONNECTOR_END_X - CONN_BAT_SOLAR_EDGE_GAP - CONN_W / 2
    power_conn = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_UNDER_Z)
        .center(power_conn_x, 0)
        .rect(CONN_W, CONN_D)
        .extrude(-CONN_H)
    )
    return pcb.union(oled).union(usb).union(ufl).union(gps_conn).union(power_conn)


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


def assemble():
    """All solids positioned in the assembled coordinate frame."""
    return {
        "base": build_base(),
        "plate": build_plate().translate((0, 0, PARTING_Z)),
        "cell": build_cell(),
        "board": build_board(),
        "sma": build_sma_connector(),
    }


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    parts = assemble()
    exporters.export(parts["base"], "output/heltec_v4_case_base.stl")
    exporters.export(parts["base"], "output/heltec_v4_case_base.step")
    exporters.export(build_plate(), "output/heltec_v4_case_plate.stl")
    exporters.export(build_plate(), "output/heltec_v4_case_plate.step")

    assy = cq.Assembly()
    assy.add(parts["base"], name="base", color=cq.Color(0.25, 0.55, 0.85, 1.0))
    assy.add(parts["plate"], name="plate", color=cq.Color(0.90, 0.60, 0.20, 0.6))
    assy.add(parts["cell"], name="cell", color=cq.Color(0.35, 0.75, 0.35, 1.0))
    assy.add(parts["board"], name="board", color=cq.Color(0.80, 0.25, 0.25, 1.0))
    assy.add(parts["sma"], name="sma", color=cq.Color(0.75, 0.75, 0.78, 1.0))
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

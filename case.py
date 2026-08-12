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
    python3 case.py       # export STL/STEP of both halves + components
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
# Outline, header pitch and OLED widths are dimensioned in the Heltec
# reference drawing. Heights/thicknesses are not, and are marked (est).
BOARD_L = 50.2           # board length, along the cell axis
BOARD_W = 25.5           # board width
BOARD_T = 1.6            # PCB thickness (est -- standard 1.6mm FR4)
BOARD_CORNER_CHAMFER = 2.0   # angled corners shown on the drawing
BOARD_CLEARANCE = 0.4    # slack around the board footprint

# Mounting holes flanking the USB-C end (est -- the reference drawing does
# not dimension them). The OLED module covers most of the rest of the board,
# so this is the only end with room for screw posts.
BOARD_HOLE_D = 2.2
BOARD_HOLE_Y = 9.25
BOARD_HOLE_FROM_END = 3.5
BOARD_SCREW_LEN = 6.0    # M2x6 SHCS, board -> plate posts

# OLED module. Active width 27.28 and module width 33.28 are dimensioned;
# module height 18.56 is taken from the drawing's side view. Active height
# is derived from a 128x64 panel at the dimensioned active width.
OLED_ACTIVE_W = 27.28
OLED_ACTIVE_H = OLED_ACTIVE_W * 64.0 / 128.0    # = 13.64
OLED_MODULE_W = 33.28
OLED_MODULE_H = 18.56
OLED_MODULE_THICK = 4.0      # (est) module height above the PCB top face
OLED_TOP_GAP = 0.5           # clearance between module top and window underside
OLED_WINDOW_MARGIN = 0.6     # window is cut this much larger than the active area
OLED_W = OLED_ACTIVE_W + 2 * OLED_WINDOW_MARGIN
OLED_H = OLED_ACTIVE_H + 2 * OLED_WINDOW_MARGIN
# Module sits toward the u.FL (-X) end, ~1mm in from that board edge.
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

# IPEX-to-SMA pigtail: bulkhead SMA passes through the end wall, secured
# with its own nut outside. Standard jam-nut panel mount needs ~8.4mm.
SMA_HOLE_D = 8.4
SMA_NUT_AF = 9.5             # nut across-flats, for an optional recess
SMA_BODY_D = 6.5             # (est) body diameter inside the case
SMA_INNER_DEPTH = 7.0        # (est) how far the connector body protrudes inward

# --- 26650 cell -------------------------------------------------------------
CELL_D = 26.5             # actual cell diameter incl. wrap
CELL_L = 65.0             # actual cell length
CELL_CLEARANCE = 0.6      # diametral slack in the cradle bore
CELL_END_CLEARANCE = 1.0  # axial slack

CELL_BORE_R = (CELL_D + CELL_CLEARANCE) / 2
CELL_BORE_L = CELL_L + CELL_END_CLEARANCE

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
CELL_TO_BOARD_GAP = 3.5    # cell top -> board underside (also clears screw heads)
PARTING_ABOVE_CELL = 1.0   # parting line sits this far above the cell bore
CORNER_FILLET = 2.5

# --- Face plate chamfers ----------------------------------------------------
# Break the face plate's top outer edge so the case does not read as a slab.
FACE_CHAMFER = 1.5
# The display cutout is bevelled on its *face* side, matching FACE_CHAMFER's
# 45 deg. The aperture stays OLED_W x OLED_H at the inside face and opens out
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

# --- Board support posts (on the PLATE) -------------------------------------
POST_D = M2_BOSS_D = 5.5   # screw posts, at the board's mounting holes
BEAR_POST_D = 3.0          # bearing posts at the far end, no screw
BEAR_POST_Y = 11.0         # outboard of the OLED module, inboard of the board edge

# --- M2 socket-head cap screw fasteners -------------------------------------
M2_SHAFT_D = 2.2           # clearance hole for the screw shaft
M2_HEAD_D = 4.0            # socket head diameter clearance
M2_HEAD_H = 2.2            # socket head height clearance
M2_PILOT_D = 1.6           # pilot hole in the boss that receives the screw
SCREW_INSET = 6.0          # boss centre inset from the outer corner

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
# boss anywhere within its length would stand in the cell's way.
BOSS_END_MARGIN = 1.5
_min_half_len = CELL_BORE_L / 2 + BOSS_END_MARGIN + M2_BOSS_D / 2 + SCREW_INSET
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
    extent is constant, so the pinch is at the lowest height it reaches."""
    bore_lo = CELL_AXIS_Z - CELL_BORE_R
    bore_hi = CELL_AXIS_Z + CELL_BORE_R

    def wall_ok(run):
        rise = run * END_CHAMFER_ASPECT
        for i in range(201):
            z = rise * i / 200.0
            if not (bore_lo <= z <= bore_hi):
                continue          # no bore at this height, nothing to clear
            outer = OUTER_L / 2 - run * (1.0 - (z / rise if rise else 1.0))
            if outer - CELL_BORE_L / 2 < MIN_END_CHAMFER_WALL:
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

# Board and cell are both centred at X=0, Y=0. USB-C faces +X, antenna -X.
BOARD_CONNECTOR_END_X = BOARD_L / 2
BOARD_FAR_END_X = -BOARD_L / 2
BOARD_HOLE_X = BOARD_CONNECTOR_END_X - BOARD_HOLE_FROM_END
BEAR_POST_X = BOARD_FAR_END_X + BOARD_HOLE_FROM_END

# --- Cell insertion shaft ---------------------------------------------------
# Straight rectangular prism, from the widest point of the cradle bore up
# through the top of the base. The cell drops in vertically along this.
SHAFT_W = 2 * CELL_BORE_R      # = cell dia + clearance
SHAFT_L = CELL_BORE_L
SHAFT_Z0 = CELL_AXIS_Z         # cradle's widest point
SHAFT_Z1 = BASE_DEPTH          # open at the top of the base

# SMA bulkhead sits in the -X end wall, above the cradle and below the
# parting line, and stops short of the cell's end.
SMA_Z = (CELL_AXIS_Z + PARTING_Z) / 2
SMA_CLEAR_DEPTH = (INNER_L / 2) - (SHAFT_L / 2)


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
    """Cylindrical pocket for the cell, axis along X at the cradle height."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=-CELL_BORE_L / 2)
        .center(0, CELL_AXIS_Z)
        .circle(CELL_BORE_R)
        .extrude(CELL_BORE_L)
    )


def insertion_shaft():
    """The volume the cell sweeps as it is lowered into the cradle."""
    return (
        cq.Workplane("XY")
        .workplane(offset=SHAFT_Z0)
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
        .rect(OLED_W, OLED_H)
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

    # SMA antenna bulkhead hole through the -X end wall
    base = base.cut(
        cq.Workplane("YZ")
        .workplane(offset=-OUTER_L / 2)
        .center(0, SMA_Z)
        .circle(SMA_HOLE_D / 2)
        .extrude(WALL + 2)
    )

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

    # Break the top outer edge. Done here, while the top face is still a
    # plain rectangle, so the edge selection cannot pick up the window or
    # the screw counterbores cut later.
    plate = plate.faces(">Z").edges().chamfer(FACE_CHAMFER)

    post_h = PLATE_INNER_H - BOARD_TOP_LOCAL

    # Screw posts at the board's mounting holes (USB-C end), tapped for M2
    # screws driven up through the board from below.
    for y in (BOARD_HOLE_Y, -BOARD_HOLE_Y):
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL)
            .center(BOARD_HOLE_X, y)
            .circle(POST_D / 2)
            .extrude(post_h)
        )
    for y in (BOARD_HOLE_Y, -BOARD_HOLE_Y):
        plate = plate.cut(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL)
            .center(BOARD_HOLE_X, y)
            .circle(M2_PILOT_D / 2)
            .extrude(min(BOARD_SCREW_LEN - BOARD_T + 0.5, post_h - 0.8))
        )

    # Bearing posts at the far end -- no screw, they just locate the board's
    # far edge. Placed outboard of the OLED module, inboard of the board edge.
    for y in (BEAR_POST_Y, -BEAR_POST_Y):
        plate = plate.union(
            cq.Workplane("XY")
            .workplane(offset=BOARD_TOP_LOCAL)
            .center(BEAR_POST_X, y)
            .circle(BEAR_POST_D / 2)
            .extrude(post_h)
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
    # the aperture stays exactly OLED_W x OLED_H at its narrowest.
    #
    # .faces(">Z").edges() would also pick up the plate's outer perimeter, so
    # the window's four edges are isolated with a box selector around them.
    plate = plate.cut(_oled_window_cutter())
    _pad = WINDOW_CHAMFER + 1.0
    plate = (
        plate.faces(">Z")
        .edges(
            cq.selectors.BoxSelector(
                (OLED_CENTER_X - OLED_W / 2 - _pad,
                 OLED_CENTER_Y - OLED_H / 2 - _pad,
                 PLATE_DEPTH - 1.0),
                (OLED_CENTER_X + OLED_W / 2 + _pad,
                 OLED_CENTER_Y + OLED_H / 2 + _pad,
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

    return plate.cut(_usb_cutter().translate((0, 0, -PARTING_Z)))


# ---------------------------------------------------------------------------
# COMPONENTS -- mock solids used to check fit, not printed
# ---------------------------------------------------------------------------

def build_cell():
    """26650 cell, lying along X, concentric with the cradle bore."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=-CELL_L / 2)
        .center(0, CELL_AXIS_Z)
        .circle(CELL_D / 2)
        .extrude(CELL_L)
    )


def build_board():
    """Simplified Heltec V4: PCB + OLED module + USB-C + u.FL connector."""
    pcb = (
        cq.Workplane("XY")
        .workplane(offset=BOARD_UNDER_Z)
        .box(BOARD_L, BOARD_W, BOARD_T, centered=(True, True, False))
        .edges("|Z")
        .chamfer(BOARD_CORNER_CHAMFER)
    )
    for y in (BOARD_HOLE_Y, -BOARD_HOLE_Y):
        pcb = pcb.cut(
            cq.Workplane("XY")
            .workplane(offset=BOARD_UNDER_Z)
            .center(BOARD_HOLE_X, y)
            .circle(BOARD_HOLE_D / 2)
            .extrude(BOARD_T)
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
        .center(BOARD_CONNECTOR_END_X + USB_OVERHANG - USB_DEPTH / 2, 0)
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
    return pcb.union(oled).union(usb).union(ufl)


def build_board_screws():
    """M2 screw heads under the board -- they must clear the cell."""
    heads = None
    for y in (BOARD_HOLE_Y, -BOARD_HOLE_Y):
        h = (
            cq.Workplane("XY")
            .workplane(offset=BOARD_UNDER_Z - M2_HEAD_H)
            .center(BOARD_HOLE_X, y)
            .circle(M2_HEAD_D / 2)
            .extrude(M2_HEAD_H)
        )
        heads = h if heads is None else heads.union(h)
    return heads


def build_sma_body():
    """Mock of the SMA bulkhead's inboard body, to check it clears the cell."""
    return (
        cq.Workplane("YZ")
        .workplane(offset=-INNER_L / 2)
        .center(0, SMA_Z)
        .circle(SMA_BODY_D / 2)
        .extrude(SMA_INNER_DEPTH)
    )


def assemble():
    """All solids positioned in the assembled coordinate frame."""
    return {
        "base": build_base(),
        "plate": build_plate().translate((0, 0, PARTING_Z)),
        "cell": build_cell(),
        "board": build_board(),
        "screws": build_board_screws(),
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
    assy.save("output/heltec_v4_case_assembly.step")

    print("Exported STL/STEP to ./output/")
    print(f"Outer size    : {OUTER_L:.1f} x {OUTER_W:.1f} x {TOTAL_HEIGHT:.1f} mm")
    print(f"Insertion shaft: {SHAFT_L:.1f} x {SHAFT_W:.1f} mm, "
          f"Z {SHAFT_Z0:.2f} -> {SHAFT_Z1:.2f}")
    print(f"Bottom chamfer: run {CHAMFER_RUN:.2f} rise {CHAMFER_RISE:.2f} mm, "
          f"{CHAMFER_OVERHANG_DEG:.1f} deg overhang, stands on {BOTTOM_W:.2f} mm")
    print(f"End chamfer   : run {END_CHAMFER_RUN:.2f} rise {END_CHAMFER_RISE:.2f} mm, "
          f"{END_CHAMFER_OVERHANG_DEG:.1f} deg overhang, stands on {BOTTOM_L:.2f} mm")
    print(f"Parting line  : Z {PARTING_Z:.2f}   board underside Z {BOARD_UNDER_Z:.2f}")

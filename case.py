"""
Parametric CadQuery case for a Heltec V4 board (ESP32-S3, no GPS variant),
IPEX-to-SMA antenna pigtail, and a 26650 Li-ion cell.

Two-piece design:
  - BASE half:  battery cradle + board support rails + cable/antenna cutouts
  - PLATE half: face plate with a cutout over the onboard OLED

The cell lies along the case's long axis, centred directly *underneath* the
board; the board rests on rails that run along both long side walls. The
two halves close over each other (a tongue on BASE seats inside a matching
skirt on PLATE) and are fastened with four M2 socket-head cap screws.

Board dimensions come from a Heltec mechanical reference drawing; some
component heights are still estimates -- see README.md.

Usage:
    python3 case.py       # export STL/STEP of both halves + components
    python3 verify.py     # collision / fit checks
"""

import cadquery as cq
from cadquery import exporters
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

# Mounting holes flanking the connector end (est -- the reference drawing
# does not dimension them). NOTE: in this stacked layout these holes sit
# directly over the cell, so they cannot take screw posts; the board is
# retained by rails below and hold-down ribs on the plate instead.
BOARD_HOLE_D = 2.2
BOARD_HOLE_Y = 9.25
BOARD_HOLE_FROM_END = 3.5

# OLED module. Active width 27.28 and module width 33.28 are dimensioned;
# module height 18.56 is taken from the drawing's side view. Active height
# is derived from a 128x64 panel at the dimensioned active width.
OLED_ACTIVE_W = 27.28
OLED_ACTIVE_H = OLED_ACTIVE_W * 64.0 / 128.0    # = 13.64
OLED_MODULE_W = 33.28
OLED_MODULE_H = 18.56
OLED_MODULE_THICK = 4.0      # (est) module height above the PCB top face
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
LID_RECESS = 5.0           # depth of the split-line tongue/skirt
TONGUE_FRAC = 0.6          # fraction of WALL removed to form the tongue
FIT_CLEARANCE = 0.15       # slack between base tongue and plate skirt
CELL_TO_BOARD_GAP = 2.0    # clear gap between cell top and board underside
CORNER_FILLET = 2.5

# Board support rails along the long side walls (the cell is wider than the
# board, so floor-mounted posts are impossible -- see README).
RAIL_BEARING = 1.5         # how far each rail reaches under the board edge
RAIL_INNER_Y = BOARD_W / 2 - RAIL_BEARING

# --- M2 socket-head cap screw fasteners -------------------------------------
M2_SHAFT_D = 2.2           # clearance hole for the screw shaft
M2_HEAD_D = 4.0            # socket head diameter clearance
M2_HEAD_H = 2.2            # socket head height clearance
M2_PILOT_D = 1.6           # pilot hole in the boss that receives the screw
M2_BOSS_D = 5.5
SCREW_LEN = 8.0            # M2x8 SHCS assumed
SCREW_INSET = 6.0          # boss centre inset from the outer corner

# --- Derived Z levels (from the outside of the base floor, Z=0) -------------
CELL_AXIS_Z = FLOOR + CELL_BORE_R
CELL_TOP_Z = FLOOR + 2 * CELL_BORE_R
BOARD_UNDER_Z = CELL_TOP_Z + CELL_TO_BOARD_GAP
BOARD_TOP_Z = BOARD_UNDER_Z + BOARD_T

BASE_DEPTH = BOARD_TOP_Z + LID_RECESS
PLATE_INNER_H = max(LID_RECESS, OLED_MODULE_THICK + 1.0)
PLATE_DEPTH = PLATE_INNER_H + WALL
TOTAL_HEIGHT = (BASE_DEPTH - LID_RECESS) + PLATE_DEPTH

# --- Derived plan dimensions ------------------------------------------------
# Width is set by the cell (which is wider than the board) plus side walls.
INNER_W = max(BOARD_W + 2 * BOARD_CLEARANCE, CELL_D + CELL_CLEARANCE) + 4.0
OUTER_W = INNER_W + 2 * WALL

# Length must leave room for the corner screw bosses *beyond* the ends of
# the cell bore -- the bore spans the full width, so a boss anywhere within
# the bore's length would be carved into by it.
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

# Board and cell are both centred at X=0, Y=0. USB-C faces +X, antenna -X.
BOARD_CONNECTOR_END_X = BOARD_L / 2
BOARD_FAR_END_X = -BOARD_L / 2

# SMA bulkhead sits in the -X end wall, above the cradle and clear of the
# cell's end, centred between the cradle top and the parting line.
SMA_Z = (CELL_AXIS_Z + BOARD_TOP_Z) / 2
# Clear axial depth available for the connector body before it meets the cell
SMA_CLEAR_DEPTH = (INNER_L / 2) - (CELL_BORE_L / 2)


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


def _cell_bore(radius=None, length=None):
    """Cylindrical pocket for the cell, axis along X at the cradle height."""
    r = CELL_BORE_R if radius is None else radius
    ln = CELL_BORE_L if length is None else length
    return (
        cq.Workplane("YZ")
        .workplane(offset=-ln / 2)
        .center(0, CELL_AXIS_Z)
        .circle(r)
        .extrude(ln)
    )


# ---------------------------------------------------------------------------
# BASE half
# ---------------------------------------------------------------------------

def build_base():
    base = _rounded_box(OUTER_L, OUTER_W, BASE_DEPTH, 0, CORNER_FILLET).cut(
        _rounded_box(INNER_L, INNER_W, BASE_DEPTH, FLOOR,
                     max(CORNER_FILLET - WALL, 0.5))
    )

    # Cradle pedestal: fills the cavity up to the cell's axis height. The
    # bore is cut from it below, leaving a half-round saddle that hugs the
    # cell, and solid blocks past each end of the bore that act as end stops.
    pedestal = _rounded_box(INNER_L, INNER_W, CELL_AXIS_Z - FLOOR, FLOOR,
                            max(CORNER_FILLET - WALL, 0.5))
    base = base.union(pedestal)

    # Board support rails along both long walls, from the pedestal top up to
    # the board underside. The bore cut below trims whatever intrudes into
    # the cell, so the rails end up hugging the cell's upper flanks.
    rail_len = min(BOARD_L + 4.0, INNER_L)
    for sign in (1, -1):
        y0 = sign * RAIL_INNER_Y
        y1 = sign * (INNER_W / 2)
        rail = (
            cq.Workplane("XY")
            .workplane(offset=FLOOR)
            .center(0, (y0 + y1) / 2)
            .rect(rail_len, abs(y1 - y0))
            .extrude(BOARD_UNDER_Z - FLOOR)
        )
        base = base.union(rail)

    # Cut the cell bore last so it trims the pedestal and the rails together
    base = base.cut(_cell_bore())

    # USB-C cutout in the +X end wall, just above the board's top face
    usb_cut = (
        cq.Workplane("YZ")
        .workplane(offset=OUTER_L / 2)
        .center(0, BOARD_TOP_Z + USB_H / 2)
        .rect(USB_W + 1.0, USB_H + 1.0)
        .extrude(-WALL - 2)
    )
    base = base.cut(usb_cut)

    # SMA antenna bulkhead hole through the -X end wall
    sma_cut = (
        cq.Workplane("YZ")
        .workplane(offset=-OUTER_L / 2)
        .center(0, SMA_Z)
        .circle(SMA_HOLE_D / 2)
        .extrude(WALL + 2)
    )
    base = base.cut(sma_cut)

    # Split-line tongue: remove the outer part of the wall over the top
    # LID_RECESS so the plate's skirt can close over it.
    step = _rounded_box(OUTER_L, OUTER_W, LID_RECESS,
                        BASE_DEPTH - LID_RECESS, CORNER_FILLET).cut(
        _rounded_box(OUTER_L - 2 * WALL * TONGUE_FRAC,
                     OUTER_W - 2 * WALL * TONGUE_FRAC,
                     LID_RECESS + 1, BASE_DEPTH - LID_RECESS,
                     max(CORNER_FILLET - WALL * TONGUE_FRAC, 0.3))
    )
    base = base.cut(step)

    # Screw bosses, full height, with pilot holes drilled from the top
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
            .extrude(-min(SCREW_LEN, BASE_DEPTH - 1.0))
        )

    return base


# ---------------------------------------------------------------------------
# PLATE half
# ---------------------------------------------------------------------------

def build_plate():
    """Face plate, modelled in its own frame with Z=0 at its underside
    (which lands on BOARD_TOP_Z when assembled)."""
    plate = _rounded_box(OUTER_L, OUTER_W, PLATE_DEPTH, 0, CORNER_FILLET)

    # Interior: a skirt pocket over the bottom LID_RECESS that swallows the
    # base's tongue, plus the main cavity above it.
    plate = plate.cut(
        _rounded_box(OUTER_L - 2 * WALL * TONGUE_FRAC + 2 * FIT_CLEARANCE,
                     OUTER_W - 2 * WALL * TONGUE_FRAC + 2 * FIT_CLEARANCE,
                     LID_RECESS, 0,
                     max(CORNER_FILLET - WALL * TONGUE_FRAC, 0.3))
    )
    plate = plate.cut(
        _rounded_box(INNER_L, INNER_W, PLATE_INNER_H, 0,
                     max(CORNER_FILLET - WALL, 0.5))
    )

    # Hold-down ribs: press on the board's long edges from above, opposite
    # the base's rails. Kept clear of the OLED module and the screw holes.
    rib_len = min(BOARD_L - 8.0, OUTER_L - 4 * SCREW_INSET)
    for sign in (1, -1):
        y0 = sign * RAIL_INNER_Y
        y1 = sign * (INNER_W / 2)
        rib = (
            cq.Workplane("XY")
            .center(0, (y0 + y1) / 2)
            .rect(rib_len, abs(y1 - y0))
            .extrude(PLATE_INNER_H)
        )
        plate = plate.union(rib)

    # OLED window through the top face
    plate = plate.cut(
        cq.Workplane("XY")
        .workplane(offset=PLATE_DEPTH - WALL - 1)
        .center(OLED_CENTER_X, OLED_CENTER_Y)
        .rect(OLED_W, OLED_H)
        .extrude(WALL + 2)
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

    return plate


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
            .center(BOARD_CONNECTOR_END_X - BOARD_HOLE_FROM_END, y)
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
    """All four solids positioned in the assembled coordinate frame."""
    return {
        "base": build_base(),
        "plate": build_plate().translate((0, 0, BOARD_TOP_Z)),
        "cell": build_cell(),
        "board": build_board(),
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
    print(f"Outer size : {OUTER_L:.1f} x {OUTER_W:.1f} x {TOTAL_HEIGHT:.1f} mm")
    print(f"Cell axis Z: {CELL_AXIS_Z:.2f}   board underside Z: {BOARD_UNDER_Z:.2f}")

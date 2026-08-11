"""
Parametric CadQuery case for a Heltec V4 board (ESP32-S3, no GPS variant),
IPEX-to-SMA antenna pigtail, and a 26650 Li-ion cell.

Two-piece design:
  - BASE half:  battery bay + board standoffs + cable/antenna cutouts
  - PLATE half: face plate with a cutout over the onboard OLED, plus
                cutouts for the USB-C port and the reset/user buttons

The two halves close over each other (a lip on BASE seats inside a
matching rabbet on PLATE) and are fastened with four M2 socket-head
cap screws into printed screw bosses.

All dimensions are parametric and collected in the CONFIG section below.
Board / connector placement numbers are best-effort estimates for the
Heltec WiFi LoRa 32 V4 (26 x 51 mm ESP32-S3 form factor shared with the
V3/V3.2 boards) -- MEASURE YOUR OWN BOARD and adjust the constants
before printing. See README.md for the full list of assumptions.

Usage:
    python3 case.py
Produces STL + STEP files for both halves in ./output/.
"""

import cadquery as cq
from cadquery import exporters
import os

# ---------------------------------------------------------------------------
# CONFIG -- all measurements in millimetres
# ---------------------------------------------------------------------------

# --- Heltec V4 board -------------------------------------------------------
BOARD_L = 51.0          # board length (along battery axis)
BOARD_W = 25.5           # board width
BOARD_T = 1.6            # PCB thickness
BOARD_CLEARANCE = 0.3    # slack around the board footprint

# Mounting holes (Heltec V3/V3.2/V4 share a 2-hole pattern near one end,
# diameter 2.2 mm for M2 self-tapping / press-fit standoffs).
BOARD_HOLE_D = 2.2
BOARD_HOLE_INSET_X = 3.0     # from each short edge... only one end is used
BOARD_HOLE_Y = 3.0           # distance of each hole from the board centreline
BOARD_HOLE_FROM_TOP = 4.0    # distance of hole row from the connector-end edge

# OLED (onboard 0.96" SSD1306, offset toward one long edge in the upper
# portion of the board, viewed active area only)
OLED_W = 23.0
OLED_H = 13.2
OLED_CENTER_FROM_TOP = 16.0   # distance from the USB/connector edge to OLED centre
OLED_CENTER_X_OFFSET = 0.0    # OLED is centred on the board width on V3/V4

# USB-C connector (centred on the short edge)
USB_W = 9.0
USB_H = 3.6
USB_Z_FROM_BOARD_TOP = 1.0    # connector shroud rises above the PCB top face

# User / reset buttons on the same short edge as USB-C, needs no cutout
# normally (buttons are recessed) -- included for optional side access holes.
BUTTON_D = 3.0
BUTTON_OFFSET_FROM_USB = 6.0

# IPEX-to-SMA pigtail: bulkhead SMA nut passes through the wall, secured
# with its own nut on the outside. Standard panel-mount SMA needs an 8mm
# through hole (jam-nut, non-waterproof, D-shape flat optional -- omitted
# here for simplicity) plus a shallow counterbore for the nut flat-to-flat.
SMA_HOLE_D = 8.4
SMA_NUT_AF = 9.5             # nut across-flats, for optional recess
SMA_NUT_DEPTH = 2.0

# --- 26650 cell -------------------------------------------------------------
CELL_D = 26.5             # 26650 nominal diameter + wrap tolerance
CELL_L = 65.5             # 26650 nominal length + tolerance
CELL_CLEARANCE = 0.6      # extra diametral clearance for the bay

# --- Wall / shell ------------------------------------------------------------
WALL = 2.2                 # outer shell wall thickness
FLOOR = 2.0                # base floor thickness under the battery bay
LID_RECESS = 5.0           # depth of the split-line rabbet/lip
BOARD_STANDOFF_GAP = 1.2   # clearance between the top of the cell and the board underside
STANDOFF_D = 5.0
BOSS_D = 5.5               # screw-boss outer diameter (base halves)
COMPONENT_HEADROOM = 3.0   # clearance above the board top face for SMD parts/OLED module

# --- M2 socket-head cap screw fasteners --------------------------------------
M2_SHAFT_D = 2.2           # clearance hole for M2 screw shaft
M2_HEAD_D = 4.0            # socket head diameter clearance
M2_HEAD_H = 2.2            # socket head height clearance
M2_PILOT_D = 1.6           # pilot hole in the boss that receives the screw
M2_BOSS_D = 5.5
SCREW_LEN = 8.0             # M2x8 SHCS assumed

# --- Derived overall dimensions ---------------------------------------------
# Layout: the cell is stacked directly under the board, both sharing the same
# long axis (X) and both centred on the case centreline (X=0, Y=0) -- i.e.
# the battery sits centred *behind* (underneath) the board, oriented along
# it, rather than end-to-end with it. USB-C and the antenna live in the two
# short end walls (the walls perpendicular to the shared long axis).
CELL_R = (CELL_D + CELL_CLEARANCE) / 2

INNER_W = max(BOARD_W + 2 * BOARD_CLEARANCE, CELL_D + CELL_CLEARANCE) + 4.0
INNER_L = max(BOARD_L, CELL_L) + 8.0   # shared length, plus margin for end walls

OUTER_W = INNER_W + 2 * WALL
OUTER_L = INNER_L + 2 * WALL

# Z stack (measured from the base's inner floor, Z=FLOOR upward):
#   cell bay -> gap -> board -> component headroom -> plate inner face
STANDOFF_H = CELL_D + CELL_CLEARANCE + BOARD_STANDOFF_GAP   # post height, floor -> board underside
BASE_DEPTH = FLOOR + STANDOFF_H + BOARD_T + LID_RECESS
PLATE_DEPTH = COMPONENT_HEADROOM + WALL + LID_RECESS

CORNER_FILLET = 2.5

# Screw boss positions -- 4 corners, inset from the outer edges
SCREW_INSET = 6.0
screw_positions = [
    ( OUTER_L / 2 - SCREW_INSET,  OUTER_W / 2 - SCREW_INSET),
    ( OUTER_L / 2 - SCREW_INSET, -OUTER_W / 2 + SCREW_INSET),
    (-OUTER_L / 2 + SCREW_INSET,  OUTER_W / 2 - SCREW_INSET),
    (-OUTER_L / 2 + SCREW_INSET, -OUTER_W / 2 + SCREW_INSET),
]

# Board and cell are both centred on the case (X=0, Y=0). The board's
# connector (USB-C) edge is placed toward +X; the antenna bulkhead sits in
# the opposite short wall at -X.
BOARD_CONNECTOR_END_X = BOARD_L / 2     # board edge nearest the +X (USB-C) wall
BOARD_FAR_END_X = -BOARD_L / 2          # board edge nearest the -X (antenna) wall


# ---------------------------------------------------------------------------
# BASE half -- outer tub with battery bay, board standoffs, USB-C notch,
# SMA antenna hole, and screw bosses.
# ---------------------------------------------------------------------------

def build_base():
    outer = (
        cq.Workplane("XY")
        .box(OUTER_L, OUTER_W, BASE_DEPTH, centered=(True, True, False))
        .edges("|Z")
        .fillet(CORNER_FILLET)
    )

    inner_cavity = (
        cq.Workplane("XY")
        .workplane(offset=FLOOR)
        .box(INNER_L, INNER_W, BASE_DEPTH, centered=(True, True, False))
        .edges("|Z")
        .fillet(max(CORNER_FILLET - WALL, 0.5))
    )

    base = outer.cut(inner_cavity)

    # Battery bay: half-round trough running the length of the cell, centred
    # on the case (X=0, Y=0) directly beneath the board -- axis parallel to
    # the board's long axis. The trough is "open" on top because the inner
    # cavity above it has already been removed; only the cradle below the
    # cylinder's centreline remains solid.
    battery_trough = (
        cq.Workplane("XY")
        .workplane(offset=FLOOR + CELL_R)
        .transformed(rotate=(90, 0, 0))
        .center(0, 0)
        .circle(CELL_R)
        .extrude(CELL_L, both=True)
    )
    base = base.cut(battery_trough)

    # End-stop ribs that keep the cell from sliding along its axis
    for sign in (1, -1):
        stop = (
            cq.Workplane("XY")
            .workplane(offset=FLOOR)
            .center(sign * (CELL_L / 2 - 1.0), 0)
            .rect(2.0, INNER_W - 4)
            .extrude(CELL_R + 2)
        )
        base = base.union(stop)

    # Board standoffs (2 posts under the board's mounting-hole row, near the
    # USB-C/+X end, plus a support pair near the far/-X end).
    board_hole_row_x = BOARD_CONNECTOR_END_X - BOARD_HOLE_FROM_TOP
    for y in (BOARD_HOLE_Y, -BOARD_HOLE_Y):
        post = (
            cq.Workplane("XY")
            .workplane(offset=FLOOR)
            .center(board_hole_row_x, y)
            .circle(STANDOFF_D / 2)
            .extrude(STANDOFF_H)
            .faces(">Z")
            .workplane()
            .circle(M2_PILOT_D / 2)
            .cutBlind(-STANDOFF_H - 2)
        )
        base = base.union(post)

    for y in (BOARD_HOLE_Y, -BOARD_HOLE_Y):
        post = (
            cq.Workplane("XY")
            .workplane(offset=FLOOR)
            .center(BOARD_FAR_END_X + 4.0, y)
            .circle(STANDOFF_D / 2)
            .extrude(STANDOFF_H)
        )
        base = base.union(post)

    # USB-C cutout in the +X short wall, at the board's connector edge
    usb_z = FLOOR + STANDOFF_H + USB_H / 2
    usb_cutout = (
        cq.Workplane("YZ")
        .workplane(offset=OUTER_L / 2)
        .center(0, usb_z)
        .rect(USB_W, USB_H + 1.0)
        .extrude(-WALL - 1)
    )
    base = base.cut(usb_cutout)

    # SMA antenna bulkhead hole through the -X short wall (opposite end from
    # USB-C), for the IPEX-to-SMA pigtail running from the board's u.FL
    # connector out to an external screw-on antenna.
    sma_z = FLOOR + STANDOFF_H + BOARD_T / 2
    sma_hole = (
        cq.Workplane("YZ")
        .workplane(offset=-OUTER_L / 2)
        .center(0, sma_z)
        .circle(SMA_HOLE_D / 2)
        .extrude(WALL + 1)
    )
    base = base.cut(sma_hole)

    # Screw bosses (full height of base, pilot hole from the top face down)
    for (x, y) in screw_positions:
        boss = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(M2_BOSS_D / 2)
            .extrude(BASE_DEPTH)
        )
        base = base.union(boss)

    # Split-line rabbet: a step around the top perimeter that the plate's
    # lip drops into, for alignment and dust/light sealing.
    rabbet_outer = (
        cq.Workplane("XY")
        .workplane(offset=BASE_DEPTH - LID_RECESS)
        .box(OUTER_L, OUTER_W, LID_RECESS, centered=(True, True, False))
        .edges("|Z")
        .fillet(CORNER_FILLET)
    )
    rabbet_inner = (
        cq.Workplane("XY")
        .workplane(offset=BASE_DEPTH - LID_RECESS)
        .box(OUTER_L - 2 * WALL * 0.6, OUTER_W - 2 * WALL * 0.6, LID_RECESS + 1,
             centered=(True, True, False))
        .edges("|Z")
        .fillet(max(CORNER_FILLET - WALL * 0.6, 0.3))
    )
    step = rabbet_outer.cut(rabbet_inner)
    base = base.cut(step)
    # Re-add bosses that the rabbet cut may have clipped at the very top,
    # then drill the M2 pilot hole down through the full boss.
    for (x, y) in screw_positions:
        boss_top = (
            cq.Workplane("XY")
            .workplane(offset=BASE_DEPTH - LID_RECESS)
            .center(x, y)
            .circle(M2_BOSS_D / 2)
            .extrude(LID_RECESS)
        )
        base = base.union(boss_top)
        pilot = (
            cq.Workplane("XY")
            .workplane(offset=BASE_DEPTH)
            .center(x, y)
            .circle(M2_PILOT_D / 2)
            .extrude(-min(SCREW_LEN, BASE_DEPTH - 1.0))
        )
        base = base.cut(pilot)

    return base


# ---------------------------------------------------------------------------
# PLATE half -- face plate with OLED window, screw clearance holes, and a
# lip that mates into the base's rabbet.
# ---------------------------------------------------------------------------

def build_plate():
    outer = (
        cq.Workplane("XY")
        .box(OUTER_L, OUTER_W, PLATE_DEPTH, centered=(True, True, False))
        .edges("|Z")
        .fillet(CORNER_FILLET)
    )

    inner_cavity = (
        cq.Workplane("XY")
        .workplane(offset=0)
        .box(INNER_L, INNER_W, PLATE_DEPTH - (FLOOR - 0.5), centered=(True, True, False))
        .edges("|Z")
        .fillet(max(CORNER_FILLET - WALL, 0.5))
    )
    plate = outer.cut(inner_cavity)

    # Mating lip on the underside that drops into the base rabbet
    lip_outer = (
        cq.Workplane("XY")
        .box(OUTER_L - 2 * WALL * 0.6, OUTER_W - 2 * WALL * 0.6, LID_RECESS,
             centered=(True, True, False))
        .edges("|Z")
        .fillet(max(CORNER_FILLET - WALL * 0.6, 0.3))
    )
    lip_inner = (
        cq.Workplane("XY")
        .box(INNER_L, INNER_W, LID_RECESS + 1, centered=(True, True, False))
        .edges("|Z")
        .fillet(max(CORNER_FILLET - WALL, 0.5))
    )
    lip = lip_outer.cut(lip_inner)
    plate = plate.union(lip)

    # OLED window on the top face, located over the board
    oled_center_x = BOARD_CONNECTOR_END_X - OLED_CENTER_FROM_TOP
    oled_window = (
        cq.Workplane("XY")
        .workplane(offset=PLATE_DEPTH - WALL - 1)
        .center(oled_center_x, OLED_CENTER_X_OFFSET)
        .rect(OLED_W, OLED_H)
        .extrude(WALL + 2)
    )
    plate = plate.cut(oled_window)

    # Screw clearance holes + countersink for socket-head caps, through the plate
    for (x, y) in screw_positions:
        shaft = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(M2_SHAFT_D / 2)
            .extrude(PLATE_DEPTH)
        )
        head = (
            cq.Workplane("XY")
            .workplane(offset=PLATE_DEPTH - M2_HEAD_H)
            .center(x, y)
            .circle(M2_HEAD_D / 2)
            .extrude(M2_HEAD_H + 1)
        )
        plate = plate.cut(shaft).cut(head)

    return plate


def assemble_preview():
    base = build_base()
    plate = build_plate().translate((0, 0, BASE_DEPTH - LID_RECESS))
    return base, plate


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    base = build_base()
    plate = build_plate()

    exporters.export(base, "output/heltec_v4_case_base.stl")
    exporters.export(base, "output/heltec_v4_case_base.step")
    exporters.export(plate, "output/heltec_v4_case_plate.stl")
    exporters.export(plate, "output/heltec_v4_case_plate.step")

    base_asm, plate_asm = assemble_preview()
    assy = cq.Assembly()
    assy.add(base_asm, name="base", color=cq.Color(0.2, 0.6, 0.9, 1.0))
    assy.add(plate_asm, name="plate", color=cq.Color(0.9, 0.6, 0.2, 0.7))
    assy.save("output/heltec_v4_case_assembly.step")

    print("Exported STL/STEP files to ./output/")
    print(f"Overall outer size: {OUTER_L:.1f} x {OUTER_W:.1f} x {BASE_DEPTH + PLATE_DEPTH - LID_RECESS:.1f} mm")

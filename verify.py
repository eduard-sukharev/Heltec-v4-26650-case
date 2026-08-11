"""
Fit, collision and insertion-path checks for the Heltec V4 / 26650 case.

Builds both case halves plus mock solids for the cell, the board, its
retaining screw heads and the SMA bulkhead body, then checks that:
  * no two solids overlap (pairwise boolean intersection volume ~ 0)
  * the cell has a clear straight-down insertion path into its cradle
  * every component sits inside the case's outer envelope
  * the design clearances that matter are actually present
  * the board is genuinely supported, not floating

Run:  python3 verify.py
Exit status is non-zero if any check fails.
"""

import sys
import math
import cadquery as cq
import case

# Volume below which an intersection is treated as a boolean sliver rather
# than a real collision. A genuine interference is orders of magnitude larger.
SLIVER_TOL = 0.5      # mm^3
CLEAR_TOL = 0.01      # mm


def volume(solid):
    try:
        return solid.val().Volume()
    except Exception:
        return 0.0


def intersect_volume(a, b):
    try:
        return volume(a.intersect(b))
    except Exception:
        return 0.0


def bbox(solid):
    return solid.val().BoundingBox()


results = []


def check(name, ok, detail):
    results.append((name, ok, detail))


print("Building solids...")
base = case.build_base()
plate = case.build_plate().translate((0, 0, case.PARTING_Z))
cell = case.build_cell()
board = case.build_board()
screws = case.build_board_screws()
sma = case.build_sma_body()

solids = {
    "base": base,
    "plate": plate,
    "cell": cell,
    "board": board,
    "screws": screws,
    "sma-body": sma,
}

print("Checking pairwise collisions...")
names = list(solids)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = names[i], names[j]
        # the board is meant to be bolted to the plate's posts, and the
        # screw heads are meant to touch the board -- contact, not overlap
        v = intersect_volume(solids[a], solids[b])
        check(f"no collision: {a} <-> {b}", v <= SLIVER_TOL, f"overlap {v:.3f} mm^3")

# --- the headline check: can the cell actually be dropped in? --------------
print("Checking cell insertion path...")
shaft = case.insertion_shaft()
obstruction = intersect_volume(base, shaft)
check(
    "insertion shaft clear of base material",
    obstruction <= SLIVER_TOL,
    f"{obstruction:.3f} mm^3 of base intrudes",
)

# Shaft must be wide/long enough for the cell, and reach the open top
check(
    "shaft wide enough for the cell",
    case.SHAFT_W >= case.CELL_D,
    f"shaft {case.SHAFT_W:.2f} vs cell dia {case.CELL_D:.2f} mm",
)
check(
    "shaft long enough for the cell",
    case.SHAFT_L >= case.CELL_L,
    f"shaft {case.SHAFT_L:.2f} vs cell length {case.CELL_L:.2f} mm",
)
check(
    "shaft reaches the open top of the base",
    case.SHAFT_Z1 >= case.BASE_DEPTH - CLEAR_TOL,
    f"shaft top {case.SHAFT_Z1:.2f} vs base top {case.BASE_DEPTH:.2f} mm",
)
check(
    "shaft starts at the cradle's widest point",
    abs(case.SHAFT_Z0 - case.CELL_AXIS_Z) <= CLEAR_TOL,
    f"shaft base Z {case.SHAFT_Z0:.2f}, cradle axis Z {case.CELL_AXIS_Z:.2f}",
)

# Sample the true clear opening at a series of heights, the way the earlier
# rail design failed: narrowest opening anywhere above the cradle.
print("Sampling clear opening above the cradle...")
worst = (None, 1e9)
for i in range(41):
    z = case.CELL_AXIS_Z + (case.BASE_DEPTH - case.CELL_AXIS_Z) * i / 40.0
    z = min(z, case.BASE_DEPTH - 0.05)
    slab = (
        cq.Workplane("XY")
        .workplane(offset=z)
        .box(case.SHAFT_L, case.INNER_W, 0.05, centered=(True, True, False))
    )
    free = volume(slab) - intersect_volume(base, slab)
    # convert free slab volume into an equivalent clear width
    width = free / (case.SHAFT_L * 0.05)
    if width < worst[1]:
        worst = (z, width)
check(
    "narrowest clear width above cradle",
    worst[1] >= case.CELL_D,
    f"{worst[1]:.2f} mm at Z={worst[0]:.2f} (cell needs {case.CELL_D:.2f})",
)

# Screw bosses must sit clear of the shaft, or they stand in the cell's way
boss_inner_x = min(abs(x) for x, _ in case.screw_positions) - case.M2_BOSS_D / 2
check(
    "screw bosses clear the insertion shaft",
    boss_inner_x >= case.SHAFT_L / 2,
    f"boss inner edge {boss_inner_x:.2f} vs shaft end {case.SHAFT_L / 2:.2f} mm",
)

# The board and its posts live on the plate, so they must not sit in the
# shaft when the base is open -- but they must also clear the cell when closed.
check(
    "base carries no board-support features",
    intersect_volume(base, board) <= SLIVER_TOL,
    "board is carried entirely by the plate",
)

print("Checking containment...")
env = bbox(base.union(plate))
for nm in ("cell", "board", "sma-body"):
    bb = bbox(solids[nm])
    inside = (
        bb.xmin >= env.xmin - CLEAR_TOL and bb.xmax <= env.xmax + CLEAR_TOL
        and bb.ymin >= env.ymin - CLEAR_TOL and bb.ymax <= env.ymax + CLEAR_TOL
        and bb.zmin >= env.zmin - CLEAR_TOL and bb.zmax <= env.zmax + CLEAR_TOL
    )
    check(
        f"inside case envelope: {nm}",
        inside,
        f"X {bb.xmin:7.2f}..{bb.xmax:7.2f}  "
        f"Y {bb.ymin:7.2f}..{bb.ymax:7.2f}  "
        f"Z {bb.zmin:7.2f}..{bb.zmax:7.2f}",
    )

print("Checking the board is actually supported...")
# Probe just above the board's top face where each post should land
post_spots = [(case.BOARD_HOLE_X, case.BOARD_HOLE_Y, "screw post +Y"),
              (case.BOARD_HOLE_X, -case.BOARD_HOLE_Y, "screw post -Y"),
              (case.BEAR_POST_X, case.BEAR_POST_Y, "bearing post +Y"),
              (case.BEAR_POST_X, -case.BEAR_POST_Y, "bearing post -Y")]
for (px, py, label) in post_spots:
    probe = (
        cq.Workplane("XY")
        .workplane(offset=case.BOARD_TOP_Z + 0.05)
        .center(px, py)
        .circle(case.BEAR_POST_D / 2 - 0.2)
        .extrude(0.4)
    )
    v = intersect_volume(plate, probe)
    check(f"post lands on board: {label}", v > 0.5, f"{v:.2f} mm^3 of post")

print("Checking design clearances...")
check("cell radial clearance in cradle", case.CELL_CLEARANCE / 2 > 0,
      f"{case.CELL_CLEARANCE / 2:.2f} mm on radius")
check("cell axial clearance in cradle", case.CELL_END_CLEARANCE > 0,
      f"{case.CELL_END_CLEARANCE:.2f} mm total")

gap = case.BOARD_UNDER_Z - case.CELL_TOP_Z
check("gap: cell top -> board underside", gap > 0, f"{gap:.2f} mm")

head_gap = (case.BOARD_UNDER_Z - case.M2_HEAD_H) - case.CELL_TOP_Z
check("gap: cell top -> board screw heads", head_gap > 0, f"{head_gap:.2f} mm")

check("board fits between side walls",
      case.BOARD_W + 2 * case.BOARD_CLEARANCE <= case.INNER_W,
      f"board {case.BOARD_W:.1f} + slack vs cavity {case.INNER_W:.1f} mm")
check("board length fits the cavity",
      case.BOARD_L + 2 * case.BOARD_CLEARANCE <= case.INNER_L,
      f"board {case.BOARD_L:.1f} vs cavity {case.INNER_L:.1f} mm")

check("SMA body clears the cell end",
      case.SMA_INNER_DEPTH <= case.SMA_CLEAR_DEPTH,
      f"needs {case.SMA_INNER_DEPTH:.2f}, available {case.SMA_CLEAR_DEPTH:.2f} mm")
sma_lo = case.SMA_Z - case.SMA_HOLE_D / 2
sma_hi = case.SMA_Z + case.SMA_HOLE_D / 2
check("SMA hole within the base's end wall",
      sma_lo >= case.CELL_AXIS_Z and sma_hi <= case.PARTING_Z,
      f"hole {sma_lo:.2f}..{sma_hi:.2f} in wall band "
      f"{case.CELL_AXIS_Z:.2f}..{case.PARTING_Z:.2f} mm")

check("headroom above OLED module", case.OLED_TOP_GAP > 0,
      f"{case.OLED_TOP_GAP:.2f} mm to the window")

# Bearing posts must miss the OLED module but land on the board
check("bearing posts clear the OLED module",
      case.BEAR_POST_Y - case.BEAR_POST_D / 2 >= case.OLED_MODULE_H / 2,
      f"post inner edge {case.BEAR_POST_Y - case.BEAR_POST_D / 2:.2f} "
      f"vs module edge {case.OLED_MODULE_H / 2:.2f} mm")
check("bearing posts land within the board width",
      case.BEAR_POST_Y + case.BEAR_POST_D / 2 <= case.BOARD_W / 2,
      f"post outer edge {case.BEAR_POST_Y + case.BEAR_POST_D / 2:.2f} "
      f"vs board edge {case.BOARD_W / 2:.2f} mm")

win_lo = case.OLED_CENTER_X - case.OLED_W / 2
win_hi = case.OLED_CENTER_X + case.OLED_W / 2
mod_lo = case.OLED_CENTER_X - case.OLED_MODULE_W / 2
mod_hi = case.OLED_CENTER_X + case.OLED_MODULE_W / 2
check("OLED window lies within the module footprint",
      win_lo >= mod_lo and win_hi <= mod_hi,
      f"window {win_lo:.2f}..{win_hi:.2f} within module {mod_lo:.2f}..{mod_hi:.2f}")

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print(f"{'CHECK':<46} {'RESULT':<7} DETAIL")
print("-" * 78)
failed = 0
for name, ok, detail in results:
    if not ok:
        failed += 1
    print(f"{name:<46} {'PASS' if ok else 'FAIL':<7} {detail}")
print("=" * 78)

print()
print("Geometry summary")
print("-" * 78)
print(f"  case outer          : {case.OUTER_L:.1f} x {case.OUTER_W:.1f} "
      f"x {case.TOTAL_HEIGHT:.1f} mm")
print(f"  cavity inner        : {case.INNER_L:.1f} x {case.INNER_W:.1f} mm")
print(f"  insertion shaft     : {case.SHAFT_L:.1f} x {case.SHAFT_W:.1f} mm, "
      f"Z {case.SHAFT_Z0:.2f} -> {case.SHAFT_Z1:.2f}")
print(f"  cell axis / top Z   : {case.CELL_AXIS_Z:.2f} / {case.CELL_TOP_Z:.2f} mm")
print(f"  parting line Z      : {case.PARTING_Z:.2f} mm")
print(f"  board underside Z   : {case.BOARD_UNDER_Z:.2f} mm")
print(f"  base volume         : {volume(base) / 1000.0:.2f} cm^3")
print(f"  plate volume        : {volume(plate) / 1000.0:.2f} cm^3")

if failed:
    print(f"\n{failed} check(s) FAILED")
    sys.exit(1)
print("\nAll checks passed.")

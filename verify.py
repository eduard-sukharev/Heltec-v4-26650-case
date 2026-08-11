"""
Fit and collision checks for the Heltec V4 / 26650 case.

Builds both case halves plus mock solids for the cell, the board and the
SMA bulkhead body, then checks that:
  * no two solids overlap (pairwise boolean intersection volume ~ 0)
  * every component sits inside the case's outer envelope
  * the design clearances that matter are actually present

Run:  python3 verify.py
Exit status is non-zero if any check fails.
"""

import sys
import cadquery as cq
import case

# Volume below which an intersection is treated as a boolean sliver, not a
# real collision. Boolean ops on tangent/coincident faces can leave tiny
# artefacts; anything a real interference produces is orders of magnitude
# larger than this.
SLIVER_TOL = 0.5      # mm^3
CLEAR_TOL = 0.01      # mm, for comparing computed clearances


def volume(solid):
    try:
        return solid.val().Volume()
    except Exception:
        return 0.0


def intersect_volume(a, b):
    try:
        return volume(a.intersect(b))
    except Exception:
        # An empty intersection can raise rather than return a null shape
        return 0.0


def bbox(solid):
    return solid.val().BoundingBox()


results = []


def check(name, ok, detail):
    results.append((name, ok, detail))


print("Building solids...")
base = case.build_base()
plate = case.build_plate().translate((0, 0, case.BOARD_TOP_Z))
cell = case.build_cell()
board = case.build_board()
sma = case.build_sma_body()

solids = {
    "base": base,
    "plate": plate,
    "cell": cell,
    "board": board,
    "sma-body": sma,
}

print("Checking pairwise collisions...")
names = list(solids)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = names[i], names[j]
        v = intersect_volume(solids[a], solids[b])
        check(f"no collision: {a} <-> {b}", v <= SLIVER_TOL, f"overlap {v:.3f} mm^3")

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

print("Checking design clearances...")

# Cell sits in its bore with radial and axial slack
check(
    "cell radial clearance in cradle",
    case.CELL_CLEARANCE / 2 > 0,
    f"{case.CELL_CLEARANCE / 2:.2f} mm on radius",
)
check(
    "cell axial clearance in cradle",
    case.CELL_END_CLEARANCE > 0,
    f"{case.CELL_END_CLEARANCE:.2f} mm total",
)

# Gap between cell top and board underside
cell_top = case.CELL_AXIS_Z + case.CELL_D / 2
gap = case.BOARD_UNDER_Z - cell_top
check("gap: cell top -> board underside", gap > 0, f"{gap:.2f} mm")

# Board edges actually land on the rails
bearing = case.BOARD_W / 2 - case.RAIL_INNER_Y
check("board edge bearing on each rail", bearing > 0, f"{bearing:.2f} mm")

# Board is narrower than the cavity, and the cell is what sets the width
check(
    "board fits between side walls",
    case.BOARD_W + 2 * case.BOARD_CLEARANCE <= case.INNER_W,
    f"board {case.BOARD_W:.1f} + slack vs cavity {case.INNER_W:.1f} mm",
)

# Screw bosses must sit clear of the cell bore, or the bore carves them up
boss_inner_x = min(abs(x) for x, _ in case.screw_positions) - case.M2_BOSS_D / 2
bore_end_x = case.CELL_BORE_L / 2
check(
    "screw bosses clear the cell bore",
    boss_inner_x >= bore_end_x,
    f"boss inner edge {boss_inner_x:.2f} vs bore end {bore_end_x:.2f} mm",
)

# SMA body must reach in without hitting the cell
check(
    "SMA body clears the cell end",
    case.SMA_INNER_DEPTH <= case.SMA_CLEAR_DEPTH,
    f"needs {case.SMA_INNER_DEPTH:.2f}, available {case.SMA_CLEAR_DEPTH:.2f} mm",
)

# SMA hole must sit in solid wall: above the cradle, below the parting line
sma_lo = case.SMA_Z - case.SMA_HOLE_D / 2
sma_hi = case.SMA_Z + case.SMA_HOLE_D / 2
check(
    "SMA hole within the base's end wall",
    sma_lo >= case.CELL_AXIS_Z and sma_hi <= case.BOARD_TOP_Z,
    f"hole {sma_lo:.2f}..{sma_hi:.2f} in wall band "
    f"{case.CELL_AXIS_Z:.2f}..{case.BOARD_TOP_Z:.2f} mm",
)

# Headroom above the board for the OLED module
headroom = case.PLATE_INNER_H - case.OLED_MODULE_THICK
check("headroom above OLED module", headroom > 0, f"{headroom:.2f} mm")

# OLED window must actually sit over the module
win_lo = case.OLED_CENTER_X - case.OLED_W / 2
win_hi = case.OLED_CENTER_X + case.OLED_W / 2
mod_lo = case.OLED_CENTER_X - case.OLED_MODULE_W / 2
mod_hi = case.OLED_CENTER_X + case.OLED_MODULE_W / 2
check(
    "OLED window lies within the module footprint",
    win_lo >= mod_lo and win_hi <= mod_hi,
    f"window {win_lo:.2f}..{win_hi:.2f} within module {mod_lo:.2f}..{mod_hi:.2f}",
)

# Board must stay inside the case in X too
check(
    "board length fits the cavity",
    case.BOARD_L + 2 * case.BOARD_CLEARANCE <= case.INNER_L,
    f"board {case.BOARD_L:.1f} vs cavity {case.INNER_L:.1f} mm",
)

# ---------------------------------------------------------------------------
print()
print("=" * 72)
print(f"{'CHECK':<44} {'RESULT':<7} DETAIL")
print("-" * 72)
failed = 0
for name, ok, detail in results:
    if not ok:
        failed += 1
    print(f"{name:<44} {'PASS' if ok else 'FAIL':<7} {detail}")
print("=" * 72)

print()
print("Geometry summary")
print("-" * 72)
print(f"  case outer          : {case.OUTER_L:.1f} x {case.OUTER_W:.1f} "
      f"x {case.TOTAL_HEIGHT:.1f} mm")
print(f"  cavity inner        : {case.INNER_L:.1f} x {case.INNER_W:.1f} mm")
print(f"  cell axis Z         : {case.CELL_AXIS_Z:.2f} mm")
print(f"  cell top Z          : {cell_top:.2f} mm")
print(f"  board underside Z   : {case.BOARD_UNDER_Z:.2f} mm")
print(f"  board top Z         : {case.BOARD_TOP_Z:.2f} mm")
print(f"  parting line Z      : {case.BASE_DEPTH - case.LID_RECESS:.2f} mm")
print(f"  base volume         : {volume(base) / 1000.0:.2f} cm^3")
print(f"  plate volume        : {volume(plate) / 1000.0:.2f} cm^3")

if failed:
    print(f"\n{failed} check(s) FAILED")
    sys.exit(1)
print("\nAll checks passed.")

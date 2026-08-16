"""
Fit, collision and insertion-path checks for the Heltec V4 / 26650 case.

Builds both case halves plus mock solids for the cell, the board (which
carries its own GPS/battery/solar connector mocks) and the SMA bulkhead
connector (nut + washer + fixed pigtail stub, mounted through the plate's
top wall), then checks that:
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
plate_local = case.build_plate()          # plate frame: Z=0 at the parting line
plate = plate_local.translate((0, 0, case.PARTING_Z))
cell = case.build_cell()
board = case.build_board()
sma = case.build_sma_connector()
retainer = case.build_retainer()
button_bridge = case.build_button_bridge()

solids = {
    "base": base,
    "plate": plate,
    "cell": cell,
    "board": board,
    "sma": sma,
    "retainer": retainer,
    "button_bridge": button_bridge,
}

# The plate must come out as ONE connected solid. This is exactly the check
# that would have caught the earlier rail/lip design's retaining lip, which
# was a fully disconnected floating solid -- unioned into the same compound
# but never actually touching the rest of the plate anywhere. A pairwise
# collision/containment check alone can't see that; only a solid count can.
check("plate is a single connected solid",
      len(plate_local.val().Solids()) == 1,
      f"{len(plate_local.val().Solids())} solid(s)")
check("retainer is a single connected solid",
      len(retainer.val().Solids()) == 1,
      f"{len(retainer.val().Solids())} solid(s)")
# The button bridge is unioned from five separate primitives (spine, two
# arms, two posts, two caps) -- worth the same connectivity check for the
# same reason as the plate/retainer above.
check("button bridge is a single connected solid",
      len(button_bridge.val().Solids()) == 1,
      f"{len(button_bridge.val().Solids())} solid(s)")

# The plate's preload dimples are DESIGNED to interfere with the board by
# PRELOAD_BUMP_INTERFERENCE (elastically compressed as the retainer clamps
# the board home, so it doesn't rattle) -- that pair gets a wider,
# explicitly-bounded tolerance instead of the generic sliver check.
_expect_preload = (2 * case.PRELOAD_BUMP_LEN
                    * (case.RAIL_OUTER_Y - case.RAIL_SHOULDER_INNER_Y)
                    * case.PRELOAD_BUMP_INTERFERENCE)

print("Checking pairwise collisions...")
names = list(solids)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = names[i], names[j]
        v = intersect_volume(solids[a], solids[b])
        if {a, b} == {"plate", "board"}:
            check("plate <-> board overlap is just the preload dimples", (
                v <= _expect_preload + SLIVER_TOL),
                f"overlap {v:.3f} mm^3 (expected ~{_expect_preload:.3f} mm^3 of "
                f"designed preload interference)")
        else:
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
# rail design failed: narrowest opening anywhere above the cradle. The slab
# is centred on the shaft's own (offset) centreline, not the case's X=0.
print("Sampling clear opening above the cradle...")
worst = (None, 1e9)
for i in range(41):
    z = case.CELL_AXIS_Z + (case.BASE_DEPTH - case.CELL_AXIS_Z) * i / 40.0
    z = min(z, case.BASE_DEPTH - 0.05)
    slab = (
        cq.Workplane("XY")
        .workplane(offset=z)
        .center(case.CELL_OFFSET_X, 0)
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

# Screw bosses must sit clear of the shaft, or they stand in the cell's way.
# The shaft is offset toward +X, so that is the tighter side -- both bosses
# sit at the same |x|, so checking against CELL_FAR_HALF_LEN (rather than
# SHAFT_L/2) is what actually matches how OUTER_L was sized.
boss_inner_x = min(abs(x) for x, _ in case.screw_positions) - case.M2_BOSS_D / 2
check(
    "screw bosses clear the insertion shaft",
    boss_inner_x >= case.CELL_FAR_HALF_LEN,
    f"boss inner edge {boss_inner_x:.2f} vs shaft +X end "
    f"{case.CELL_FAR_HALF_LEN:.2f} mm",
)

# The board and its posts live on the plate, so they must not sit in the
# shaft when the base is open -- but they must also clear the cell when closed.
check(
    "base carries no board-support features",
    intersect_volume(base, board) <= SLIVER_TOL,
    "board is carried entirely by the plate",
)
check(
    "base carries no retainer-support features either",
    intersect_volume(base, retainer) <= SLIVER_TOL,
    "retainer is carried entirely by the plate, same as the board",
)

print("Checking containment...")
# "sma" is deliberately excluded: its threaded barrel is *meant* to
# protrude out through its own hole in the top wall, exactly like the
# u.FL/USB-C mocks are excluded from the board's own containment story.
# "board" gets a Z-max allowance of OLED_PROTRUSION for the same reason --
# the OLED module is meant to poke that far past the top wall's own outer
# face through the display window (see "Why the ceiling no longer clears
# the OLED module" in README.md), not a containment failure.
env = bbox(base.union(plate))
for nm in ("cell", "board", "retainer"):
    bb = bbox(solids[nm])
    zmax_allow = case.OLED_PROTRUSION if nm == "board" else 0.0
    inside = (
        bb.xmin >= env.xmin - CLEAR_TOL and bb.xmax <= env.xmax + CLEAR_TOL
        and bb.ymin >= env.ymin - CLEAR_TOL and bb.ymax <= env.ymax + CLEAR_TOL
        and bb.zmin >= env.zmin - CLEAR_TOL and bb.zmax <= env.zmax + zmax_allow + CLEAR_TOL
    )
    check(
        f"inside case envelope: {nm}",
        inside,
        f"X {bb.xmin:7.2f}..{bb.xmax:7.2f}  "
        f"Y {bb.ymin:7.2f}..{bb.ymax:7.2f}  "
        f"Z {bb.zmin:7.2f}..{bb.zmax:7.2f}",
    )

print("Checking the board is actually supported...")
# Probe along the shoulder's span, at both edges, just above the board's top
# face -- the shoulder must be present (registering the board) the whole way
# from the far end to the USB-C endstop.
_rail_x0 = case.BOARD_FAR_END_X - 1.0
_rail_x1 = case.BOARD_CONNECTOR_END_X
for frac in (0.1, 0.5, 0.9):
    px = _rail_x0 + frac * (_rail_x1 - _rail_x0)
    for sign in (1, -1):
        py = sign * (case.RAIL_SHOULDER_INNER_Y + case.SHOULDER_OUTER_Y) / 2
        probe = (
            cq.Workplane("XY")
            .workplane(offset=case.BOARD_TOP_LOCAL + case.PARTING_Z + 0.05)
            .center(px, py)
            .rect(1.0, 1.0)
            .extrude(0.4)
        )
        v = intersect_volume(plate, probe)
        check(f"shoulder present at X={px:.1f}, Y={py:.1f}", v > 0.2,
              f"{v:.2f} mm^3 of shoulder")

# What stops the board falling back out now is the retainer plank, not a
# lip -- it must actually reach up and touch both underside connectors
# (zero gap by construction), not just sit somewhere nearby with a gap.
for conn_x, name in ((case.GPS_CONN_X, "GPS"), (case.POWER_CONN_X, "battery/solar")):
    contact_z = case.BOARD_UNDER_Z - case.CONN_H
    probe = (
        cq.Workplane("XY")
        .workplane(offset=contact_z - 0.05)
        .center(conn_x, 0)
        .rect(case.CONN_W - 0.5, case.RETAINER_WIDTH - 0.5)
        .extrude(0.1)
    )
    v = intersect_volume(retainer, probe)
    check(f"retainer reaches the {name} connector's contact height", v > 0.05,
          f"{v:.3f} mm^3 of retainer at the connector's underside")

# The retainer's own mounting ears must actually have a boss to screw into
# -- same "boss intact" volume-comparison pattern used for the case screw
# bosses: build the expected solid (ear block minus the pilot bore, minus
# the four rounded corners) and compare it against what's actually there.
# Width comes from _retainer_pocket_x_range(), not a flat RETAINER_EAR_LEN:
# the boss is built to the same width as the ear-notch pocket it roofs, and
# the POWER_CONN_X one is wider still, stretched out to merge with the +X
# corner screw boss instead of leaving a gap next to it.
_boss_cy = case.RETAINER_BOSS_CY
_boss_w = case.RETAINER_BOSS_Y1 - case.RAIL_OUTER_Y
_r = case.RETAINER_EAR_FILLET
# Only the two INBOARD corners are rounded now -- the outboard pair is
# square (see _retainer_pocket_sharp_corners), so half the old corner loss.
_fillet_loss = (2 * _r * _r - math.pi * _r * _r / 2) * case.RETAINER_SCREW_ENGAGE
for conn_x, merge_corner in case.RETAINER_CONNECTORS:
    bx0, bx1 = case._retainer_pocket_x_range(conn_x, merge_corner)
    for sign in (1, -1):
        py = sign * _boss_cy
        block = (
            cq.Workplane("XY")
            .workplane(offset=case.BOARD_UNDER_Z - case.CONN_H)
            .center((bx0 + bx1) / 2, py)
            .rect(bx1 - bx0, _boss_w)
            .extrude(case.RETAINER_SCREW_ENGAGE)
        )
        want_v = (volume(block)
                  - math.pi * (case.RETAINER_SCREW_PILOT_D / 2) ** 2 * case.RETAINER_SCREW_ENGAGE
                  - _fillet_loss)
        got_v = intersect_volume(plate, block)
        # Each FREE boss end gets a concave blend fillet into the side wall
        # (RETAINER_BOSS_WALL_FILLET, see build_plate()), which *adds* a
        # cove of material inside this probe that the flat idealisation
        # above doesn't model. Bound it rather than just loosening the
        # check: the cove can't exceed the fillet's own r x r cross-section
        # swept over the probe's depth. The merged end has no such cove --
        # it runs into the corner post instead.
        _n_free = 1 if merge_corner else 2
        _cove_allow = (_n_free * case.RETAINER_BOSS_WALL_FILLET ** 2
                       * case.RETAINER_SCREW_ENGAGE)
        # One-sided above once the boss window itself already reaches the
        # corner post (merge_corner's max() becomes a no-op there, see
        # _retainer_ear_x_range): the post's own material can then spill an
        # unmodelled amount into this probe, which is a bonus, not a defect.
        # Either way a *shortfall* still fails -- that is the real failure
        # mode this guards (a boss gone thin or hollowed out).
        ok = (got_v >= want_v - 0.5 if merge_corner
              else want_v - 0.5 <= got_v <= want_v + _cove_allow + 0.5)
        check(f"retainer boss intact at X={conn_x:.1f}, Y={py:.1f}",
              ok,
              f"{got_v:.2f} of {want_v:.2f} mm^3")

# The retainer's ears are brought up from OUTSIDE the plate's open
# underside, before the plate is ever closed onto the base -- so the path
# they travel spans the full plug depth (Z < 0) as well as the ledge above
# it, not just the ledge. An earlier version of the ledge notch stopped
# exactly at the parting line, leaving the plug itself (solid there by
# design, for the half-lap fit) blocking the ears' only way in. This probes
# the whole path length, not just the ledge band, so that regression can't
# recur silently.
for conn_x in (case.GPS_CONN_X, case.POWER_CONN_X):
    for sign in (1, -1):
        py = sign * _boss_cy
        path = (
            cq.Workplane("XY")
            .workplane(offset=-case.PLUG_DEPTH - 2)
            .center(conn_x, py)
            .rect(case.RETAINER_EAR_LEN - 1.0, _boss_w - 0.5)
            .extrude((case.BOARD_UNDER_LOCAL - case.CONN_H) - (-case.PLUG_DEPTH - 2))
        )
        v = intersect_volume(plate_local, path)
        check(f"retainer ear insertion path clear at X={conn_x:.1f}, Y={py:.1f}",
              v <= SLIVER_TOL,
              f"{v:.3f} mm^3 obstructing the path from outside the plate to the boss")

print("Checking design clearances...")
check("cell radial clearance in cradle", case.CELL_CLEARANCE / 2 > 0,
      f"{case.CELL_CLEARANCE / 2:.2f} mm on radius")
check("cell axial clearance in cradle", case.CELL_END_CLEARANCE > 0,
      f"{case.CELL_END_CLEARANCE:.2f} mm total")

gap = case.BOARD_UNDER_Z - case.CELL_TOP_Z
check("gap: cell top -> board underside", gap > 0, f"{gap:.2f} mm")

conn_gap = (case.BOARD_UNDER_Z - case.CONN_H) - case.CELL_TOP_Z
check("gap: cell top -> GPS/battery/solar connectors", conn_gap > 0, f"{conn_gap:.2f} mm")

# CELL_TO_BOARD_GAP was trimmed to the underside connectors/coin-cell holder
# specifically on the assumption the board's GPIO headers are unpopulated
# (HEADER_PIN_PROTRUSION = 0). If that is ever raised, the gap formula must
# actually track it -- this is what stops someone flipping the assumption
# without the geometry responding, which is exactly the kind of thing this
# suite exists to catch.
check("cell-to-board gap accounts for header pins",
      case.CELL_TO_BOARD_GAP >= case.HEADER_PIN_PROTRUSION + 0.3 - CLEAR_TOL,
      f"gap {case.CELL_TO_BOARD_GAP:.2f} vs pins {case.HEADER_PIN_PROTRUSION:.2f} + 0.3 mm")
pin_gap = case.BOARD_UNDER_Z - case.HEADER_PIN_PROTRUSION - case.CELL_TOP_Z
check("gap: cell top -> header pin tips (if populated)",
      pin_gap > 0,
      f"{pin_gap:.2f} mm (HEADER_PIN_PROTRUSION={case.HEADER_PIN_PROTRUSION:.2f})")

check("board fits between side walls",
      case.BOARD_W + 2 * case.BOARD_CLEARANCE <= case.INNER_W,
      f"board {case.BOARD_W:.1f} + slack vs cavity {case.INNER_W:.1f} mm")
check("board length fits the cavity",
      case.BOARD_L + 2 * case.BOARD_CLEARANCE <= case.INNER_L,
      f"board {case.BOARD_L:.1f} vs cavity {case.INNER_L:.1f} mm")

# Measure the offset directly off the built bore geometry (not the formula
# used to size it). CELL_OFFSET_X is 0 by default now (the SMA mount no
# longer needs axial room past the cell -- see case.py's comment on it) --
# these checks just confirm whichever value it's set to actually produced a
# bore shifted that way and by that much, in case it's ever raised again.
_bore_bb = case.cell_bore().val().BoundingBox()
_gap_usb = case.INNER_L / 2 - _bore_bb.xmax
_gap_antenna = _bore_bb.xmin - (-case.INNER_L / 2)
check("cell offset direction matches CELL_OFFSET_X's sign",
      (case.CELL_OFFSET_X == 0 and abs(_gap_antenna - _gap_usb) <= CLEAR_TOL)
      or (case.CELL_OFFSET_X > 0 and _gap_antenna > _gap_usb)
      or (case.CELL_OFFSET_X < 0 and _gap_antenna < _gap_usb),
      f"CELL_OFFSET_X = {case.CELL_OFFSET_X:.2f} mm, "
      f"antenna {_gap_antenna:.2f} vs USB {_gap_usb:.2f} mm")
check("measured antenna clearance matches SMA_CLEAR_DEPTH",
      abs(_gap_antenna - case.SMA_CLEAR_DEPTH) <= CLEAR_TOL,
      f"measured {_gap_antenna:.2f} vs formula {case.SMA_CLEAR_DEPTH:.2f} mm")

# SMA mount: axial, through the PLATE's own -X end wall -- sits entirely
# above the cell (the plate's whole Z-band clears CELL_TOP_Z), so the only
# axial (X) limit is the board's own far edge, not SMA_CLEAR_DEPTH. The
# washer sits flush against the wall (SMA_WASHER_OUTER_X, no offset), and
# the half-lap ledge is notched locally to clear it (_sma_ledge_notch())
# rather than moving the connector to dodge the ledge.
_sma_stub_tip_x = case.SMA_WASHER_OUTER_X + case.SMA_WASHER_T + case.SMA_NUT_T + case.SMA_PIGTAIL_L
check("SMA connector clears the board's far edge",
      case.BOARD_FAR_END_X - _sma_stub_tip_x > 0,
      f"stub tip X={_sma_stub_tip_x:.2f} vs board edge X={case.BOARD_FAR_END_X:.2f}")
check("SMA washer sits flush against the wall, no gap",
      abs(case.SMA_WASHER_OUTER_X - (-case.INNER_L / 2)) <= CLEAR_TOL,
      f"washer outer X={case.SMA_WASHER_OUTER_X:.3f} vs wall inner face "
      f"X={-case.INNER_L / 2:.3f}")

# Z just needs to clear the plate's own ceiling now -- the ledge conflict
# is resolved by the notch, not by squeezing SMA_Z between it and the
# ceiling, so there's no floor-side constraint left to balance against.
_sma_wide_hi = case.SMA_Z + case.SMA_WASHER_OD / 2
check("SMA washer clears the plate ceiling",
      case.PLATE_INNER_H - (_sma_wide_hi - case.PARTING_Z) > 0,
      f"top Z(local)={_sma_wide_hi - case.PARTING_Z:.2f} vs "
      f"ceiling Z(local)={case.PLATE_INNER_H:.2f}")

# What the OLD (est) axial-through-the-BASE mount would have needed, for
# comparison -- this is the number that actually motivated moving the
# mount off the base: the real connector's nut+washer+stub (17mm) is
# deeper than SMA_CLEAR_DEPTH (10.75mm) provides there. Mounting through
# the plate's wall instead sidesteps that limit entirely, since the plate
# doesn't share the base's cell-driven constraint. Informational, not a
# pass/fail gate.
_axial_depth_needed = case.SMA_NUT_T + case.SMA_WASHER_T + case.SMA_PIGTAIL_L
check("(informational) old base-wall axial mount would no longer fit",
      True,
      f"needs {_axial_depth_needed:.1f}mm axially, SMA_CLEAR_DEPTH only "
      f"gives {case.SMA_CLEAR_DEPTH:.2f}mm -- why the mount moved to the plate's wall")

# The ceiling deliberately skips the OLED module (it pokes through its own
# window instead) and is set by the tallest of the *other* top-side
# components -- confirm that's still USB-C, not something that quietly
# became taller, and that the module actually protrudes rather than falling
# back to the old recessed-behind-the-window behaviour.
check("ceiling is set by the tallest non-OLED component",
      abs(case.PLATE_INNER_H - (case.BOARD_TOP_LOCAL + case.CEILING_CLEARANCE)) <= CLEAR_TOL,
      f"ceiling {case.PLATE_INNER_H:.2f} vs board top + clearance "
      f"{case.BOARD_TOP_LOCAL + case.CEILING_CLEARANCE:.2f} mm")
check("USB-C is actually the tallest non-OLED component",
      case.USB_H >= case.UFL_H,
      f"USB-C {case.USB_H:.2f} vs u.FL {case.UFL_H:.2f} mm")
check("OLED module protrudes past the top wall's outer face",
      case.OLED_PROTRUSION > 0,
      f"{case.OLED_PROTRUSION:.2f} mm proud of the outer face")

# Retention rails must miss the OLED window but stay within the board width
check("rail shoulder clears the OLED window",
      case.RAIL_SHOULDER_INNER_Y >= case.OLED_WINDOW_H / 2,
      f"shoulder inner edge {case.RAIL_SHOULDER_INNER_Y:.2f} "
      f"vs window edge {case.OLED_WINDOW_H / 2:.2f} mm")
check("rail outer edge lands within the board width",
      case.RAIL_OUTER_Y <= case.BOARD_W / 2 + case.BOARD_CLEARANCE + CLEAR_TOL,
      f"rail outer edge {case.RAIL_OUTER_Y:.2f} "
      f"vs board+clearance edge {case.BOARD_W / 2 + case.BOARD_CLEARANCE:.2f} mm")

# The board's shift toward the USB-C end is capped by the +X corner screw
# boss -- BOARD_CENTER_X_TANGENT puts the board's chamfered corner exactly
# tangent to its rounded (see _screw_boss_sharp_corners) SW corner arc
# (see case.py's derivation). Checked directly against the real (chamfered)
# board solid and the real boss shape, not just by trusting the closed-form
# formula: zero overlap at the actual position, and a real overlap if
# nudged 0.1mm further, confirming this is genuinely the limit rather than
# a conservative stand-off short of it.
_corner_boss_xy = [p for p in case.screw_positions if p[0] > 0 and p[1] > 0][0]
_boss_solid = case._rounded_square_boss(
    _corner_boss_xy[0], _corner_boss_xy[1], case.M2_BOSS_D / 2, case.M2_BOSS_D / 2,
    0, case.TOTAL_HEIGHT, case.BOSS_CORNER_FILLET,
    case._screw_boss_sharp_corners(*_corner_boss_xy),
)
_tangent_overlap = intersect_volume(board, _boss_solid)
check("board is tangent to the +X corner boss, not overlapping",
      _tangent_overlap <= SLIVER_TOL,
      f"{_tangent_overlap:.4f} mm^3 overlap")
_pushed_overlap = intersect_volume(board.translate((0.1, 0, 0)), _boss_solid)
check("board sits genuinely at the tangent limit, not short of it",
      # A 0.1mm nudge past a true tangent point only ever grazes a thin
      # sliver of the boss's fillet arc (radius BOSS_CORNER_FILLET) --
      # nowhere near SLIVER_TOL's boolean-noise threshold -- so this needs
      # its own, much smaller bar.
      _pushed_overlap > 0.01,
      f"pushing 0.1mm further gives {_pushed_overlap:.4f} mm^3 overlap")

# Regression guard for the whole point of the X-shift: USB-C connector face
# should sit meaningfully closer to the case's inner wall than the old,
# unshifted 17.65mm gap.
_usb_face_x = case.BOARD_CONNECTOR_END_X + case.USB_OVERHANG
_usb_wall_gap = case.INNER_L / 2 - _usb_face_x
check("USB-C connector sits close to the case's USB cutout",
      _usb_wall_gap < 10.0,
      f"{_usb_wall_gap:.2f} mm gap to the inner wall (was 17.65mm unshifted)")

print("Checking the USB-C plug recess...")
# The headline check for the recess, and the reason it exists: a cable's
# overmoulded body, pushed in until its nose is USB_PLUG_NOSE_GAP off the
# connector's face, must not touch the plate anywhere. Measured against the
# built solid, not against the constants that shaped the cutter.
_plug_env = case.usb_plug_envelope()
_plug_foul = intersect_volume(plate, _plug_env)
check("USB-C plug body reaches the connector",
      _plug_foul <= SLIVER_TOL,
      f"seated plug body fouls {_plug_foul:.3f} mm^3 of the plate")

# Without the recess the plug's body grounds out on the outer face, and only
# what is left of the shell after crossing the wall+gap gets into the
# receptacle -- state both numbers so a regression reads as a number, not
# just a boolean.
_bare_engagement = case.USB_PLUG_SHELL_L - (case.OUTER_L / 2 - _usb_face_x)
check("plug engagement is a latching depth, not a graze",
      case.USB_PLUG_ENGAGEMENT >= 0.75 * case.USB_PLUG_SHELL_L,
      f"{case.USB_PLUG_ENGAGEMENT:.2f} mm of {case.USB_PLUG_SHELL_L:.2f} mm "
      f"shell (a plain window through the face would give "
      f"{_bare_engagement:.2f} mm)")

# ... and the recess must not have paid for that by opening the cavity: the
# collar's two side walls and its floor are probed directly, over the whole
# span where the well is inboard of the wall's own inner face.
_r_x0 = case.USB_RECESS_BACK_X + 0.05
_r_x1 = case.INNER_L / 2
_r_hw = case.USB_RECESS_HALF_W
_r_w = case.USB_RECESS_WALL
_r_floor = case.USB_RECESS_FLOOR_Z
for _name, _cy, _wy, _z0, _z1 in (
    ("+Y side wall", _r_hw + _r_w / 2, _r_w - 0.1, _r_floor,
     case.PARTING_Z + case.PLATE_INNER_H),
    ("-Y side wall", -(_r_hw + _r_w / 2), _r_w - 0.1, _r_floor,
     case.PARTING_Z + case.PLATE_INNER_H),
    ("floor", 0.0, 2 * _r_hw - 0.1, _r_floor - _r_w + 0.05, _r_floor - 0.05),
):
    _probe = (
        cq.Workplane("XY")
        .workplane(offset=_z0)
        .center((_r_x0 + _r_x1) / 2, _cy)
        .box(_r_x1 - _r_x0, _wy, _z1 - _z0, centered=(True, True, False))
    )
    _got = intersect_volume(plate, _probe)
    check(f"plug recess is closed off by its {_name}",
          abs(_got - volume(_probe)) <= CLEAR_TOL * 10,
          f"{_got:.2f} of {volume(_probe):.2f} mm^3 solid")

# The well is cut between the two corner screws, and its flared mouth is its
# widest point -- that is what must clear the posts, not the well proper.
_r_mouth_hw = _r_hw + case.USB_RECESS_FLARE
_post_inner_y = abs(case.screw_positions[0][1]) - case.M2_BOSS_D / 2
check("plug recess stays between the corner screw posts",
      _r_mouth_hw + _r_w <= _post_inner_y - 0.5,
      f"collar reaches Y={_r_mouth_hw + _r_w:.2f}, posts start at "
      f"{_post_inner_y:.2f} mm")

# The recess must stay clear of the sealing half-lap: it lives in the top
# half of the plate, the ledge/plug in the bottom, and the two must not meet
# or the case gains a leak path straight into the cavity.
_r_floor_underside = _r_floor - _r_w - case.PARTING_Z
check("plug recess clears the half-lap ledge",
      _r_floor_underside > case.PLUG_LEDGE,
      f"collar bottoms out {_r_floor_underside:.2f} mm above the parting "
      f"line, ledge tops out at {case.PLUG_LEDGE:.2f} mm")

# The septum -- USB_SEPTUM_T of the collar deliberately left standing
# between the connector's own face and the wide cable mouth -- is what
# actually separates the well from the board and the rest of the cavity
# behind it. Checked on all four sides of its own connector-sized window:
# above, below, and to either side must be solid; the window itself must
# be open.
_sep_x0 = case.USB_RECESS_BACK_X + 0.05
_sep_x1 = case.USB_RECESS_MOUTH_X0 - 0.05
_sep_cx = (_sep_x0 + _sep_x1) / 2
_sep_dx = _sep_x1 - _sep_x0
_conn_cz = case.BOARD_TOP_Z + case.USB_H / 2
_conn_hw = case.USB_W / 2 + 0.5   # same margin _usb_septum_window_cutter() uses
_conn_hh = case.USB_H / 2 + 0.5
for _name, _cy, _wy, _z0, _z1 in (
    ("above its connector window", 0.0, 2 * _r_hw - 0.1,
     _conn_cz + _conn_hh + 0.1, case.PARTING_Z + case.PLATE_DEPTH - 0.5),
    ("below its connector window", 0.0, 2 * _r_hw - 0.1,
     _r_floor, _conn_cz - _conn_hh - 0.1),
    ("beside (+Y) its connector window", _conn_hw + (_r_hw - _conn_hw) / 2,
     _r_hw - _conn_hw - 0.1, _conn_cz - _conn_hh, _conn_cz + _conn_hh),
    ("beside (-Y) its connector window", -(_conn_hw + (_r_hw - _conn_hw) / 2),
     _r_hw - _conn_hw - 0.1, _conn_cz - _conn_hh, _conn_cz + _conn_hh),
):
    _probe = (
        cq.Workplane("XY")
        .workplane(offset=_z0)
        .center(_sep_cx, _cy)
        .box(_sep_dx, _wy, _z1 - _z0, centered=(True, True, False))
    )
    _got = intersect_volume(plate, _probe)
    check(f"USB septum is solid {_name}",
          abs(_got - volume(_probe)) <= CLEAR_TOL * 10,
          f"{_got:.2f} of {volume(_probe):.2f} mm^3 solid")

_window_probe = (
    cq.Workplane("XY")
    .workplane(offset=_conn_cz - _conn_hh + 0.1)
    .center(_sep_cx, 0)
    .box(_sep_dx, case.USB_W, 2 * _conn_hh - 0.2, centered=(True, True, False))
)
_window_foul = intersect_volume(plate, _window_probe)
check("septum window admits the bare connector",
      _window_foul <= SLIVER_TOL,
      f"{_window_foul:.3f} mm^3 blocking the window")

print("Checking the button bridge...")
# Post/arm max Y-reach must stay clear of the registration shoulder. The
# post (BUTTON_POST_D) is the widest feature at the button end now that
# there's no separate, wider cap.
_button_post_reach = case.BUTTON_Y + case.BUTTON_POST_D / 2
check("button post clears the registration shoulder",
      _button_post_reach < case.RAIL_SHOULDER_INNER_Y,
      f"post reaches Y={_button_post_reach:.2f} vs shoulder at "
      f"{case.RAIL_SHOULDER_INNER_Y:.2f} mm")
_button_arm_reach = case.BUTTON_Y + case.BUTTON_ARM_W / 2
check("button arm clears the registration shoulder",
      _button_arm_reach < case.RAIL_SHOULDER_INNER_Y,
      f"arm reaches Y={_button_arm_reach:.2f} vs shoulder at "
      f"{case.RAIL_SHOULDER_INNER_Y:.2f} mm")

# The spine (plus half its own width) must stay BUTTON_BRIDGE_CLEARANCE
# clear of the USB-C connector's own (board-centre-side) inner edge -- the
# whole reason the bridge is C-routed instead of running straight between
# the two buttons.
_usb_inner_x = case.USB_CENTER_X - case.USB_DEPTH / 2
_spine_gap = _usb_inner_x - (case.BUTTON_SPINE_X + case.BUTTON_ARM_W / 2)
check("button bridge spine clears the USB-C connector",
      _spine_gap >= case.BUTTON_BRIDGE_CLEARANCE - CLEAR_TOL,
      f"{_spine_gap:.2f} mm clear of the connector's inner edge "
      f"(want >= {case.BUTTON_BRIDGE_CLEARANCE:.2f})")

# Direct geometric confirmation, not just the formula above: the bridge
# (which includes both arms sweeping straight through the connector's own
# X span at Y=+-BUTTON_Y) must still have zero real overlap with the board
# -- which carries the USB-C mock -- proving the C-route actually clears it
# in practice, not just on paper.
_bridge_board_overlap = intersect_volume(button_bridge, board)
check("button bridge clears the board (incl. the USB-C connector)",
      _bridge_board_overlap <= SLIVER_TOL,
      f"{_bridge_board_overlap:.3f} mm^3 overlap")

# Each arm's foot should sit a small, bounded gap above the real button
# mock -- present (not touching/preloading the switch) but not so far off
# that the bridge never actually reaches it.
_button_top_z = case.BOARD_TOP_Z + case.BUTTON_H
_travel_gap = case.BUTTON_ARM_BOTTOM_Z - _button_top_z
check("button bridge foot sits just above the real button (dead travel)",
      0 < _travel_gap <= case.BUTTON_PLUNGER_TRAVEL + CLEAR_TOL,
      f"{_travel_gap:.2f} mm gap (target {case.BUTTON_PLUNGER_TRAVEL:.2f} mm)")

# Check the SHORTER post (RST, recessed by BUTTON_RST_OFFSET) since that's
# the binding case -- if it's still positive, PRG's longer post trivially is.
_shortest_post_h = case.BUTTON_POST_H + min(o for _, _, o in case.button_actuators)
check("shortest button post is long enough to cross the ceiling wall",
      _shortest_post_h > 0,
      f"{_shortest_post_h:.2f} mm (RST recessed {-case.BUTTON_RST_OFFSET:.2f}mm)")

print("Checking the bottom chamfer...")
# Printability: the sloped face must not exceed a 45 deg overhang off the bed
check("chamfer overhang is printable",
      case.CHAMFER_OVERHANG_DEG <= 45.0 + 1e-6,
      f"{case.CHAMFER_OVERHANG_DEG:.2f} deg from vertical (limit 45)")

# The chamfer must not eat into the cell bore
worst_wall = (None, 1e9)
for i in range(401):
    z = case.CHAMFER_RISE * i / 400.0
    w = case.chamfer_outer_half_width(z) - case._bore_half_width(z)
    if w < worst_wall[1]:
        worst_wall = (z, w)
check("chamfer leaves wall over the cell bore",
      worst_wall[1] >= case.MIN_CHAMFER_WALL - CLEAR_TOL,
      f"min {worst_wall[1]:.2f} mm at Z={worst_wall[0]:.2f} "
      f"(limit {case.MIN_CHAMFER_WALL:.2f})")

check("case stands on a usable flat",
      case.BOTTOM_W >= case.MIN_BOTTOM_W - CLEAR_TOL,
      f"{case.BOTTOM_W:.2f} mm flat (limit {case.MIN_BOTTOM_W:.2f})")

# The chamfer must stay clear of the features it could plausibly clip.
# (The SMA hole is no longer in this wall -- it moved to the plate's top --
# so there's nothing SMA-specific to check here any more.)
check("screw boss pilot holes above the chamfer",
      case.CHAMFER_RISE <= case.BASE_DEPTH - min(case.SCREW_LEN, case.BASE_DEPTH - 1.0),
      f"chamfer tops out at {case.CHAMFER_RISE:.2f}, pilots start at "
      f"{case.BASE_DEPTH - min(case.SCREW_LEN, case.BASE_DEPTH - 1.0):.2f} mm")

# Confirm the solid really follows the intended profile, by sampling the
# actual base rather than trusting the formula.
SLAB_T = 0.02
for zs in (0.5, case.CHAMFER_RISE / 2, case.CHAMFER_RISE + 2.0):
    slab = (
        cq.Workplane("XY")
        .workplane(offset=zs)
        .box(1.0, case.OUTER_W + 4, SLAB_T, centered=(True, True, False))
    )
    got = intersect_volume(base, slab)
    bb = bbox(base.intersect(slab)) if got > 0 else None
    # the slab spans [zs, zs+SLAB_T] and the flank widens with height, so the
    # bounding box records the half-width at the slab's top face
    want = case.chamfer_outer_half_width(zs + SLAB_T)
    got_hw = max(abs(bb.ymin), abs(bb.ymax)) if bb else None
    ok = got_hw is not None and abs(got_hw - want) <= 0.03
    check(f"solid matches profile at Z={zs:.2f}", ok,
          f"half-width {got_hw:.3f} vs expected {want:.3f}"
          if bb else "no material found")

print("Checking the end chamfers...")
# The large flank belongs on the long edges only -- the round cell only
# leaves dead corners along its length, not past its flat ends.
check("large chamfer is confined to the long edges",
      case.END_CHAMFER_RUN < case.CHAMFER_RUN,
      f"long {case.CHAMFER_RUN:.2f} mm vs end {case.END_CHAMFER_RUN:.2f} mm")
check("end chamfer is a small break",
      case.END_CHAMFER_RUN <= case.FACE_CHAMFER + CLEAR_TOL,
      f"{case.END_CHAMFER_RUN:.2f} mm (face chamfer {case.FACE_CHAMFER:.2f} mm)")

# The four flank/end-wall junctions must actually be broken, not just
# assumed -- rebuild without the break and compare.
_unbroken = case.build_base(break_runout=False)
_removed = volume(_unbroken) - volume(base)
check("flank runout junctions are broken",
      _removed > 1.0,
      f"{_removed:.1f} mm^3 removed by the {case.PROFILE_EDGE_CHAMFER:.1f} mm break")
check("runout break did not fragment the base",
      len(base.val().Solids()) == 1,
      f"{len(base.val().Solids())} solid(s)")

check("end chamfer overhang is printable",
      case.END_CHAMFER_OVERHANG_DEG <= 45.0 + 1e-6,
      f"{case.END_CHAMFER_OVERHANG_DEG:.2f} deg from vertical (limit 45)")

# Wall left between the end chamfer and the end of the cell bore
_bore_lo = case.CELL_AXIS_Z - case.CELL_BORE_R
_bore_hi = case.CELL_AXIS_Z + case.CELL_BORE_R
worst_end = (None, 1e9)
for i in range(401):
    z = case.END_CHAMFER_RISE * i / 400.0
    if not (_bore_lo <= z <= _bore_hi):
        continue
    w = case.end_chamfer_outer_half_length(z) - case.CELL_BORE_L / 2
    if w < worst_end[1]:
        worst_end = (z, w)
check("end chamfer leaves wall over the bore end",
      worst_end[0] is None or worst_end[1] >= case.MIN_END_CHAMFER_WALL - CLEAR_TOL,
      f"min {worst_end[1]:.2f} mm at Z={worst_end[0]:.2f} "
      f"(limit {case.MIN_END_CHAMFER_WALL:.2f})" if worst_end[0] is not None
      else "bore does not reach the chamfer")


check("case stands on a usable flat (length)",
      case.BOTTOM_L >= case.MIN_BOTTOM_L - CLEAR_TOL,
      f"{case.BOTTOM_L:.2f} mm (limit {case.MIN_BOTTOM_L:.2f})")

# The bottom face should now be the full chamfered rectangle
_bot = base.faces("<Z").val().BoundingBox()
check("bottom face matches both chamfers",
      abs(_bot.xlen - case.BOTTOM_L) <= 0.05 and abs(_bot.ylen - case.BOTTOM_W) <= 0.05,
      f"{_bot.xlen:.2f} x {_bot.ylen:.2f} vs "
      f"{case.BOTTOM_L:.2f} x {case.BOTTOM_W:.2f} mm")

# Sample the real solid against the intended end profile
for zs in (0.5, case.END_CHAMFER_RISE / 2, case.END_CHAMFER_RISE + 2.0):
    slab = (
        cq.Workplane("XY")
        .workplane(offset=zs)
        .box(case.OUTER_L + 4, 1.0, 0.02, centered=(True, True, False))
    )
    got = intersect_volume(base, slab)
    bb = bbox(base.intersect(slab)) if got > 0 else None
    want = case.end_chamfer_outer_half_length(zs + 0.02)
    got_hl = max(abs(bb.xmin), abs(bb.xmax)) if bb else None
    check(f"solid matches end profile at Z={zs:.2f}",
          got_hl is not None and abs(got_hl - want) <= 0.03,
          f"half-length {got_hl:.3f} vs expected {want:.3f}" if bb else "no material")

# The chamfers eat the bosses' lower corners; the pilot holes must survive
for (x, y) in case.screw_positions:
    ring = (
        cq.Workplane("XY")
        .workplane(offset=case.BASE_DEPTH - 2.0)
        .center(x, y)
        .circle(case.M2_BOSS_D / 2)
        .extrude(1.5)
    )
    want_v = volume(ring) - math.pi * (case.M2_PILOT_D / 2) ** 2 * 1.5
    got_v = intersect_volume(base, ring)
    check(f"boss intact at ({x:.1f},{y:.1f})",
          abs(got_v - want_v) <= 0.5,
          f"{got_v:.2f} of {want_v:.2f} mm^3")

# SCREW_INSET was pushed in to the corner as far as BOSS_OUTER_MARGIN allows
# without poking through the outer (filleted) surface -- confirm that
# directly against the built solid, not just the formula that placed it.
# Only the *outward* diagonal direction (toward the true corner) matters --
# the inward side of this same margin band is legitimately open cavity, not
# a protrusion, so a full-ring probe would be the wrong test.
for (x, y) in case.screw_positions:
    # The boss's own reach along this diagonal is a rounded square's corner
    # distance (_boss_diag_reach), not the flat half-width -- see case.py's
    # SCREW_INSET derivation, which this check mirrors.
    r = case._boss_diag_reach + case.BOSS_OUTER_MARGIN
    px = x + math.copysign(r / math.sqrt(2), x)
    py = y + math.copysign(r / math.sqrt(2), y)
    probe = (
        cq.Workplane("XY")
        .workplane(offset=case.BASE_DEPTH - 2.0)
        .center(px, py)
        .circle(0.1)
        .extrude(1.5)
    )
    v = intersect_volume(base, probe)
    check(f"boss + margin backed by material at corner ({x:.1f},{y:.1f})",
          abs(v - volume(probe)) <= 0.02,
          f"{v:.4f} of {volume(probe):.4f} mm^3")

print("Checking the face plate chamfers...")
top_wall = case.PLATE_DEPTH - case.PLATE_INNER_H
check("window bevel leaves a straight land",
      case.WINDOW_CHAMFER < top_wall,
      f"bevel {case.WINDOW_CHAMFER:.2f} of {top_wall:.2f} mm wall, "
      f"land {top_wall - case.WINDOW_CHAMFER:.2f} mm")

# Measure the real opening at the outer face and at the ceiling. Padding
# only needs to be generous enough to catch the bevel's growth
# (2*WINDOW_CHAMFER per side) with margin -- a flat +20/+12 used to be safe
# when nothing else was ever near the window, but it now reaches far enough
# in +X to pick up the button actuator holes (BUTTON_CENTER_X ~ 30mm) as
# stray open material, inflating this probe's own bounding box.
def _window_opening(z, t=0.02):
    slab = (
        cq.Workplane("XY")
        .workplane(offset=z)
        .center(case.OLED_CENTER_X, case.OLED_CENTER_Y)
        .box(case.OLED_WINDOW_W + 10, case.OLED_WINDOW_H + 10, t, centered=(True, True, False))
    )
    hole = slab.cut(case.build_plate())
    return hole.val().BoundingBox() if volume(hole) > 0 else None

# The bevel is on the face side, so the aperture is the *inside* face and
# the opening only ever widens toward the viewer.
_inner = _window_opening(case.PLATE_INNER_H + 0.01)
check("aperture is nominal at the inside face",
      _inner is not None and abs(_inner.xlen - case.OLED_WINDOW_W) <= 0.05
      and abs(_inner.ylen - case.OLED_WINDOW_H) <= 0.05,
      f"{_inner.xlen:.2f} x {_inner.ylen:.2f} vs "
      f"{case.OLED_WINDOW_W:.2f} x {case.OLED_WINDOW_H:.2f}" if _inner else "no opening")

_outer = _window_opening(case.PLATE_DEPTH - 0.03)
_want_w = case.OLED_WINDOW_W + 2 * case.WINDOW_CHAMFER
_want_h = case.OLED_WINDOW_H + 2 * case.WINDOW_CHAMFER
check("window is bevelled open at the face",
      _outer is not None and abs(_outer.xlen - (_want_w - 0.02)) <= 0.05
      and abs(_outer.ylen - (_want_h - 0.02)) <= 0.05,
      f"{_outer.xlen:.2f} x {_outer.ylen:.2f} vs "
      f"{_want_w:.2f} x {_want_h:.2f}" if _outer else "no opening")

# Printed window-up the hole must never narrow with height, or the bevel
# would be an overhang. This is the property the face-side bevel buys us.
_prev = None
_monotonic = True
for i in range(21):
    _z = case.PLATE_INNER_H + (top_wall - 0.02) * i / 20.0
    _bb = _window_opening(_z)
    if _bb is None:
        _monotonic = False
        break
    if _prev is not None and (_bb.xlen < _prev[0] - 1e-6 or _bb.ylen < _prev[1] - 1e-6):
        _monotonic = False
        break
    _prev = (_bb.xlen, _bb.ylen)
check("window never narrows with height (no overhang)", _monotonic,
      "opening widens monotonically from inside face to outer face")

# The window is meant to open onto the whole module now, not just the glass
check("window is sized to the whole module, not just the glass",
      case.OLED_WINDOW_W >= case.OLED_MODULE_W and case.OLED_WINDOW_H >= case.OLED_MODULE_H,
      f"window {case.OLED_WINDOW_W:.2f} x {case.OLED_WINDOW_H:.2f} vs "
      f"module {case.OLED_MODULE_W:.2f} x {case.OLED_MODULE_H:.2f}")

# The aperture is the widest thing the window presents to the board side
check("window clears the retention rails",
      case.OLED_WINDOW_H / 2 <= case.RAIL_SHOULDER_INNER_Y,
      f"aperture reaches Y {case.OLED_WINDOW_H / 2:.2f}, rails start at "
      f"{case.RAIL_SHOULDER_INNER_Y:.2f} mm")

# The bevelled opening must stay on the top face, clear of the face chamfer
_top_face_bb = case.build_plate().faces(">Z").val().BoundingBox()
check("bevelled window stays within the top face",
      _want_h / 2 <= _top_face_bb.ylen / 2 - CLEAR_TOL
      and _want_w / 2 <= _top_face_bb.xlen / 2 - CLEAR_TOL,
      f"window {_want_w:.2f} x {_want_h:.2f} within top face "
      f"{_top_face_bb.xlen:.2f} x {_top_face_bb.ylen:.2f} mm")

# Face chamfer must leave the counterbores fully on the flat top face
top_face = case.build_plate().faces(">Z").val().BoundingBox()
cb_edge = case.OUTER_W / 2 - case.SCREW_INSET + case.M2_HEAD_D / 2
check("face chamfer clears the screw counterbores",
      cb_edge <= top_face.ylen / 2,
      f"counterbore edge {cb_edge:.2f} vs top face half-width "
      f"{top_face.ylen / 2:.2f} mm")
check("face chamfer does not breach the plate ceiling",
      case.OUTER_W / 2 - case.FACE_CHAMFER >= case.INNER_W / 2,
      f"chamfer reaches in to {case.OUTER_W / 2 - case.FACE_CHAMFER:.2f}, "
      f"cavity wall at {case.INNER_W / 2:.2f} mm")

print("Checking the half-lap interface and the screw stack...")

# The base must end flat -- no lip rising above the parting line at all.
_base_top = bbox(base).zmax
check("base has no lip above the parting line",
      abs(_base_top - case.PARTING_Z) <= CLEAR_TOL,
      f"base tops out at {_base_top:.2f}, parting line {case.PARTING_Z:.2f} mm")

# The plug replaces a tongue that was thinner than two extrusion widths.
_aspect = case.PLUG_DEPTH / case.PLUG_WALL
check("plug wall is printable",
      case.PLUG_WALL >= 1.2 and _aspect <= 3.0,
      f"{case.PLUG_WALL:.2f} mm thick x {case.PLUG_DEPTH:.2f} tall "
      f"({_aspect:.1f}:1, {case.PLUG_WALL / 0.4:.1f} extrusion widths)")

check("plug is a slip fit in the base cavity",
      0.05 <= case.FIT_CLEARANCE <= 0.4,
      f"{case.FIT_CLEARANCE:.2f} mm per side")

# Whether the plug fouls the SMA connector's stub (which now hangs down
# from the plate, past the parting line, rather than sitting in the end
# wall) is covered by the general "no collision: plate <-> sma" pairwise
# check above -- against the real solid, not a formula.

# The ledge that carries the plug has to sit below the board
check("plug ledge stays below the board",
      case.PLUG_LEDGE <= case.BOARD_UNDER_LOCAL,
      f"ledge {case.PLUG_LEDGE:.2f} vs board underside "
      f"{case.BOARD_UNDER_LOCAL:.2f} mm above the parting line")

# THE regression this suite previously missed: the counterbore is exactly as
# deep as the plate's top wall, so without a post beneath it the screw head
# has nothing at all to bear on and would pull straight through.
for (x, y) in case.screw_positions:
    seat = (
        cq.Workplane("XY")
        .workplane(offset=case.PLATE_DEPTH - case.M2_HEAD_H - 0.3)
        .center(x, y)
        .circle(case.M2_HEAD_D / 2)
        .extrude(0.3)
    )
    v = intersect_volume(plate_local, seat)
    check(f"screw head has a seat at ({x:.1f},{y:.1f})", v > 0.5,
          f"{v:.2f} mm^3 of post under the head")

# The screw must cross the plate's post and still bite into the base's boss
check("case screw reaches the base boss",
      case.SCREW_ENGAGE >= 4.0,
      f"M2x{case.SCREW_LEN:.0f} through a {case.PLATE_INNER_H:.2f} mm post "
      f"-> {case.SCREW_ENGAGE:.2f} mm engagement")
check("boss pilot hole is deep enough for that engagement",
      min(case.SCREW_ENGAGE + 1.5, case.BASE_DEPTH - 1.0) >= case.SCREW_ENGAGE,
      f"pilot {min(case.SCREW_ENGAGE + 1.5, case.BASE_DEPTH - 1.0):.2f} mm "
      f"vs engagement {case.SCREW_ENGAGE:.2f} mm")

win_lo = case.OLED_CENTER_X - case.OLED_WINDOW_W / 2
win_hi = case.OLED_CENTER_X + case.OLED_WINDOW_W / 2
mod_lo = case.OLED_CENTER_X - case.OLED_MODULE_W / 2
mod_hi = case.OLED_CENTER_X + case.OLED_MODULE_W / 2
check("OLED module fits within the window opening",
      mod_lo >= win_lo and mod_hi <= win_hi,
      f"module {mod_lo:.2f}..{mod_hi:.2f} within window {win_lo:.2f}..{win_hi:.2f}")

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
print(f"  bottom chamfer      : run {case.CHAMFER_RUN:.2f} / rise "
      f"{case.CHAMFER_RISE:.2f} mm @ {case.CHAMFER_OVERHANG_DEG:.1f} deg")
print(f"  end chamfer         : run {case.END_CHAMFER_RUN:.2f} / rise "
      f"{case.END_CHAMFER_RISE:.2f} mm @ {case.END_CHAMFER_OVERHANG_DEG:.1f} deg")
print(f"  stands on           : {case.BOTTOM_L:.2f} x {case.BOTTOM_W:.2f} mm")
print(f"  board underside Z   : {case.BOARD_UNDER_Z:.2f} mm")
print(f"  USB-C plug recess   : {case.USB_PLUG_W:.1f} wide x "
      f"{case.OUTER_L / 2 - case.USB_RECESS_MOUTH_X0:.2f} deep mouth "
      f"+ {case.USB_SEPTUM_T:.2f} septum, floor at Z "
      f"{case.USB_RECESS_FLOOR_Z:.2f}, open-topped")
print(f"  base volume         : {volume(base) / 1000.0:.2f} cm^3")
print(f"  plate volume        : {volume(plate) / 1000.0:.2f} cm^3")

if failed:
    print(f"\n{failed} check(s) FAILED")
    sys.exit(1)
print("\nAll checks passed.")

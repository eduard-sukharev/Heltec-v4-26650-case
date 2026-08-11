# Heltec V4 + 26650 Case

![Current state of the model](docs/preview.png)

*Regenerated from `case.py` on every change (see `make preview` below) —
this is always the actual current model, not a stale illustration.*

Parametric [CadQuery](https://cadquery.readthedocs.io/) model of a
two-piece 3D-printable enclosure for:

- A **Heltec V4** board (ESP32-S3 based Heltec WiFi LoRa 32 V4 form factor,
  **GPS-less variant**)
- An **external antenna** connected via an **IPEX-to-SMA pigtail**, with a
  panel-mount SMA bulkhead hole in the case wall
- A single **26650** Li-ion cell as the power source

Outer size **86.5 × 35.5 × 40.9 mm**.

## Files

- `case.py` — the model, including mock solids for the cell and board.
- `verify.py` — collision / fit / insertion-path checks (see below).
- `render_preview.py` — renders `docs/preview.png`, the image at the top of
  this file.
- `Makefile` — `make` / `make preview` / `make verify` / `make all` /
  `make clean` (see "Generating the model" below).
- `docs/preview.png` — **checked in**, unlike everything under `output/`.
  It exists purely so this README shows the model's current state without
  anyone having to build it themselves; `make` (the bare, no-argument form)
  regenerates it, and it should be committed alongside any change to
  `case.py`.
- `output/` — generated STL + STEP. Not checked in; regenerate with `make`.

## Design

The enclosure splits along a horizontal parting line **just above the cell**,
closed with **four M2 socket-head cap screws** (M2×8) threaded into printed
bosses. The 26650 cell lies **along the case's long axis, centred directly
underneath the board**.

The two halves divide the job cleanly:

- **Base half — a pure battery tub.** It carries *no* board features at all:
  - A **cradle** for the cell: a pedestal filling the cavity up to the
    cell's axis height, with a half-round bore cut through it. The solid
    blocks past each end of the bore act as axial end stops.
  - A **rectangular insertion shaft** (66 × 27.1 mm) running from the
    widest point of the cradle straight up through the open top, so the
    cell drops vertically into place.
  - A panel-mount **SMA bulkhead hole** (8.4 mm) centred in the −X end
    wall, between the cradle top and the parting line.
  - Four screw bosses, placed *beyond the ends of the shaft*.
  - A **tongue** around the top perimeter that the plate's skirt closes
    over, with 0.15 mm fit clearance.
  - A large **chamfer on the two long bottom edges**, plus a small break on
    the short ends and on the junctions between them (see below).

- **Plate half — the face plate, and it carries the board.** It has:
  - A **cutout over the onboard OLED**, sized from the drawing's 27.28 mm
    active width plus a 0.6 mm margin, sitting 0.5 mm above the module.
  - Two **screw posts** at the board's mounting holes (USB-C end), tapped
    for M2×6 screws driven up through the board from below.
  - Two **bearing posts** at the far end that locate the board's other
    edge — placed outboard of the OLED module (±9.28 mm) and inboard of
    the board edge (±12.75 mm), so they land in the narrow clear strip
    between the two.
  - Four M2 clearance holes with socket-head counterbores.
  - A skirt that closes over the base's tongue.
  - A **1.5 mm chamfer around the top outer edge**, and a matching **1 mm
    bevel on the face side of the display cutout** (see below).

The **USB-C opening straddles the parting line**, so it is cut from both
halves from a single shared cutter.

### The octagonal bottom profile

The **two long** bottom edges of the base are chamfered away, so its end-on
section reads as a truncated octagon: a narrow flat bottom, two sloped
flanks, two vertical sides, and a flat top where the face plate closes it
off.

The large flank is deliberately **long-edges only**. The chamfer exists to
delete material outboard of a *cylinder*, and a cylinder only leaves dead
corners along its length — past its flat end faces there is nothing to
reclaim, and cutting there would just eat into the block that acts as the
cell's axial end stop. The short ends therefore get a small 1.5 mm break
instead, and the four junctions where the large flanks run out against the
end walls get a 1.0 mm break, so nothing around the profile is left sharp.

This is not just cosmetic. The cell is round, so the corners of a
rectangular tub are dead material — the chamfer deletes exactly the wedge
that sits outboard of the cell's curve. It takes the base from **38.8 cm³
down to 28.7 cm³, a 26% saving**, without touching any clearance.

The chamfer is *derived*, not hardcoded. `_max_chamfer_run()` grows it until
one of two limits binds:

- `MIN_CHAMFER_WALL` (2.2 mm) — material left between the sloped face and
  the cell bore. The pinch is always around Z ≈ 6 mm, where the bore's
  curve outruns the 45° line.
- `MIN_BOTTOM_W` (14 mm) — the flat the case actually stands on.

At the current settings the bottom flat binds first, giving a **10.75 mm
run and rise** with **3.39 mm** of wall still over the bore. Raising
`MIN_BOTTOM_W` gives a tippier but lighter case; the hard ceiling from the
wall limit alone is 11.94 mm.

`_max_end_chamfer_run()` still exists, but as a *guard* rather than a
target: `END_CHAMFER` is a small fixed break, and the derivation only bites
if someone raises it far enough to start eating the bore's end (the pinch
would be at Z = 2.0 mm, where the bore is tangent to the floor). The case
stands on an **83.50 × 14.00 mm** flat.

The four runout junctions are broken with CadQuery's `.chamfer()` via a
`FlankRunoutSelector` — they are the only edges on the part that are
diagonal in Y/Z while holding X constant, which picks them out exactly
without indexing into an edge list that shifts whenever a feature is added.
OCC blends the break into the 2.5 mm corner fillets where the edges meet
them, which is why it removes ~86 mm³ rather than the ~19 mm³ a naive
prism estimate would suggest.

Both chamfers eat the lower corners of the screw bosses — at Z = 0 the
bosses are gone entirely, emerging from the chamfered corner as they rise
and becoming full by Z ≈ 7.5 mm. That is harmless, since the screws only
engage the top 8 mm, but `verify.py` checks the material ring around every
pilot hole anyway.

**Printability** is the reason the slope is exactly 45°. `CHAMFER_ASPECT`
is rise/run, and at 1.0 the flank is a 45° overhang off the bed — the usual
unsupported limit. Set it above 1.0 for a steeper, safer wall that saves
less. `verify.py` fails the build if the overhang ever exceeds 45°.

### Face plate chamfers

Two separate chamfers, for different reasons:

- **`FACE_CHAMFER` (1.5 mm)** breaks the plate's top outer edge so the case
  doesn't read as a slab. It is applied while the top face is still a plain
  rectangle — *before* the window and counterbores are cut — so the edge
  selection can't accidentally pick those up. It brings the top face to
  83.5 × 32.5 mm, which still leaves the M2 counterbores (outer edge at
  13.75 mm) fully on the flat, with 2.5 mm to spare.

- **`WINDOW_CHAMFER` (1.0 mm)** bevels the display cutout on its **face**
  side, at the same 45° as the perimeter chamfer. The aperture is
  28.48 × 14.84 mm at the inside face and opens out to 30.48 × 16.84 mm at
  the visible surface. With a 2.2 mm top wall that leaves a **1.2 mm
  straight land** behind the aperture.

Putting the bevel on the face side rather than the inside means the hole
**only ever widens with height**. Printed window-up, every layer is
supported by the one below, so there is no overhang anywhere in the
window — unlike an inside flare, which would have to bridge inward across
the opening. `verify.py` asserts this directly by sampling the opening
through the wall and requiring it to widen monotonically.

The bevel is produced with CadQuery's `.chamfer()` on the finished top
edge, so the cutter stays a plain rectangular prism and the aperture is
exactly `OLED_W × OLED_H` by construction. `.faces(">Z").edges()` would
also catch the plate's outer perimeter, so the window's four edges are
isolated with a `BoxSelector` around them. `verify.py` measures the real
opening at both faces rather than trusting any of that.

### Why the board hangs from the plate

This is forced by the geometry, not a style choice. The cell (26.5 mm dia.,
65.0 mm long) is both **wider and longer than the board** (25.5 × 50.2 mm),
so the board's entire footprint is shadowed by the cell — and by the cell's
vertical insertion path above it.

An earlier revision supported the board on rails along the base's side
walls. Those rails reached inward to ±11.25 mm to catch the board's edges,
which **choked the opening to 22.5 mm for a 26.5 mm cell** — the cell could
not be fitted at all without springing the case apart. Any base-side board
support has the same problem: to touch a board narrower than the cell, it
must intrude into the cell's path.

So the board is mounted to the plate, and the base is left completely
clear. `verify.py` enforces this with a `base carries no board-support
features` check.

**Consequences worth knowing:**

- Assembly order is: drop the cell into the base → bolt the board to the
  plate → lower the plate onto the base → four case screws.
- Only **two screws** retain the board (the board's real hole pattern only
  has room at the USB-C end); the far end is located by bearing posts.
- The board's screw heads sit under the PCB with **1.6 mm** of clearance to
  the cell.

### Why the case is 86.5 mm long


The insertion shaft spans most of the cavity width, so a screw boss placed
anywhere within its length would stand in the cell's way. `OUTER_L` is
therefore derived so the corner bosses clear the ends of the shaft:

```
OUTER_L = 2 × (CELL_BORE_L/2 + BOSS_END_MARGIN + M2_BOSS_D/2 + SCREW_INSET)
```

This is checked by `verify.py`, so changing the cell or screw parameters
keeps the constraint satisfied automatically.

## Verifying fit

```bash
python3 verify.py
```

This builds both halves plus mock solids for the cell, the board (PCB +
OLED module + USB-C + u.FL), the board's screw heads and the SMA bulkhead
body, then checks:

- **Pairwise collisions** — boolean intersection volume of every pair of
  solids must be ~0.
- **Insertion path** — the base must not intrude into the insertion shaft
  at all, and the shaft must be wide/long enough and reach the open top.
  The clear opening is also *sampled* at 41 heights above the cradle, so a
  feature that narrows the path anywhere is caught (this is exactly how the
  old rail design was found to be unbuildable).
- **Containment** — each component's bounding box lies inside the case.
- **Support** — a probe at each of the four post locations confirms the
  plate's posts actually land on the board, rather than the board floating.
- **Bottom and end chamfers** — the large flank stays confined to the long
  edges and the end break stays small, overhangs stay within 45°, enough
  wall is left over the cell bore, the standing flat is usable, and the
  chamfers clear the SMA hole and the boss pilot holes. The built solid is
  *sampled* at three heights against each intended profile, the bottom face
  is measured against both, the runout break is confirmed by rebuilding
  without it and comparing volumes, and the material ring around every boss
  pilot hole is checked since the chamfers cut the bosses' lower corners.
- **Face plate chamfers** — the window's real opening is measured at both
  the outer and inside faces, the opening widens monotonically through the
  wall (so the bevel is never an overhang), the aperture leaves a straight
  land and clears the bearing posts, and the face chamfer leaves the
  counterbores on the flat without breaching the plate ceiling.
- **Design clearances** — cell slack, cell-to-board gap, screw-head
  clearance over the cell, bosses clearing the shaft, SMA body clearing the
  cell end, SMA hole landing in solid wall, bearing posts threading the gap
  between the OLED module and the board edge, and the window lying within
  the module footprint.

All checks currently pass. Key measured clearances:

| Clearance | Value |
|---|---|
| Narrowest opening above cradle | 31.10 mm (cell needs 26.50) |
| Cell radial slack in cradle | 0.30 mm |
| Cell axial slack | 1.00 mm |
| Cell top → board underside | 3.80 mm |
| Cell top → board screw heads | 1.60 mm |
| Boss inner edge vs. shaft end | 34.50 vs 33.00 mm |
| SMA body depth needed / available | 7.00 / 8.05 mm |
| Bearing post inner edge vs. OLED module | 9.50 vs 9.28 mm |
| Bearing post outer edge vs. board edge | 12.50 vs 12.75 mm |
| Headroom above OLED module | 0.50 mm |
| Chamfer wall over the cell bore | 3.39 mm (min 2.20) |
| Chamfer overhang | 45.0° (limit 45°) |
| Flat the case stands on | 83.50 × 14.00 mm |
| Long-edge chamfer / end break | 10.75 / 1.50 mm |
| Window aperture (inside face) | 28.48 × 14.84 mm |
| Window at face side (bevelled) | 30.46 × 16.82 mm |
| Straight land behind the aperture | 1.20 mm |
| Face chamfer to counterbore | 16.25 vs 13.75 mm |

Note that a zero-overlap result alone would also be satisfied by a part
floating in mid-air, which is why the support probes and the
narrowest-opening sampling are there.

## ⚠️ Dimensions you should verify before printing

Board outline (50.2 × 25.5 mm), OLED active width (27.28 mm), OLED module
size (33.28 × 18.56 mm) and header pitch come from a Heltec mechanical
reference drawing. Everything marked `(est)` in `case.py` is **not**
dimensioned in that drawing and is a best-effort estimate — notably PCB
thickness, component heights, and connector positions.

| Constant | What to check |
|---|---|
| `BOARD_T` | PCB thickness (assumed 1.6 mm) |
| `OLED_MODULE_THICK` | OLED module height above the PCB (assumed 4.0 mm) |
| `OLED_CENTER_X`, `OLED_MODULE_EDGE_GAP` | Where the module sits along the board |
| `USB_W`, `USB_H`, `USB_DEPTH` | USB-C body size and position |
| `UFL_FROM_END` | u.FL connector position |
| `SMA_HOLE_D`, `SMA_INNER_DEPTH` | Your SMA bulkhead's panel hole and inboard length |
| `CELL_D`, `CELL_L` | Your actual 26650 (varies with wrap / protection PCB) |
| `BOARD_HOLE_Y`, `BOARD_HOLE_FROM_END` | Mounting holes — these now locate the plate's screw posts, so getting them right matters |
| `BEAR_POST_Y` | Bearing posts; must clear `OLED_MODULE_H/2` and stay inside `BOARD_W/2` |
| `CHAMFER_ASPECT`, `MIN_BOTTOM_W` | Bottom chamfer: slope and standing flat |
| `END_CHAMFER`, `PROFILE_EDGE_CHAMFER` | Small breaks on the short ends and the flank runouts |
| `FACE_CHAMFER`, `WINDOW_CHAMFER` | Face plate edge break and display-cutout bevel |

`OLED_ACTIVE_H` is *derived* from the dimensioned active width assuming a
128×64 panel; if your display differs, set it directly.

## Generating the model

```bash
pip install cadquery cairosvg
make            # generate STL/STEP into output/, refresh docs/preview.png
make preview    # just refresh docs/preview.png
make verify     # run verify.py
make all        # generate, refresh the preview, then verify
make clean      # remove output/ (docs/preview.png is untouched -- it's checked in)
```

(`python3 case.py` / `python3 render_preview.py` / `python3 verify.py`
directly also work — the Makefile just saves retyping them, and only
re-runs each step when its inputs have actually changed.)

If you edit `case.py`, run `make` and commit the updated
`docs/preview.png` along with it — that's what keeps the image at the top
of this README honest.

Writes to `output/`:

- `heltec_v4_case_base.stl` / `.step`
- `heltec_v4_case_plate.stl` / `.step`
- `heltec_v4_case_assembly.step` (both halves plus cell and board, for
  visual review only — not for printing)

## Printing notes

- Print the base cradle-down and the plate window-up. With the board
  support moved off the base, the cradle bore is now a plain half-round
  trough with no overhang beyond its own arc — no support needed.
- The plate's posts print as simple vertical pillars in that orientation.
- The display cutout's bevel is on the face side, so printed window-up the
  opening only widens as it rises — no overhang and no bridging anywhere in
  the window.
- The base is ~29 cm³ of enclosed volume including the cradle pedestal —
  print it with modest infill rather than solid.
- The bottom chamfers print as 45° expanding overhangs straight off the
  bed, so they need no support, but the first layer is only
  83.50 × 14.00 mm — use a brim if adhesion is marginal.
- M2 pilot holes are sized (1.6 mm) for self-tapping M2 screws into
  PLA/PETG; swap in heat-set inserts (and re-check `M2_PILOT_D` /
  `M2_BOSS_D`) for reusable fastening.
- The SMA hole assumes a jam-nut panel-mount bulkhead; add a wrench-flat
  recess (`SMA_NUT_AF`, currently unused) if yours needs anti-rotation.
- **Li-ion safety**: this case has no vent path and no provision for a
  protection circuit or BMS. Use a protected cell, and add a vent hole if
  you intend to leave it charging unattended.

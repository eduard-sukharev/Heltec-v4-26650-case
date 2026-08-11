# Heltec V4 + 26650 Case

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
- `output/` — generated STL + STEP. Not checked in; regenerate with
  `python3 case.py`.

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

The **USB-C opening straddles the parting line**, so it is cut from both
halves from a single shared cutter.

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

`OLED_ACTIVE_H` is *derived* from the dimensioned active width assuming a
128×64 panel; if your display differs, set it directly.

## Generating the model

```bash
pip install cadquery
python3 case.py
```

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
- The base is a fairly solid part (~39 cm³ of enclosed volume including the
  cradle pedestal) — print it with modest infill rather than solid.
- M2 pilot holes are sized (1.6 mm) for self-tapping M2 screws into
  PLA/PETG; swap in heat-set inserts (and re-check `M2_PILOT_D` /
  `M2_BOSS_D`) for reusable fastening.
- The SMA hole assumes a jam-nut panel-mount bulkhead; add a wrench-flat
  recess (`SMA_NUT_AF`, currently unused) if yours needs anti-rotation.
- **Li-ion safety**: this case has no vent path and no provision for a
  protection circuit or BMS. Use a protected cell, and add a vent hole if
  you intend to leave it charging unattended.

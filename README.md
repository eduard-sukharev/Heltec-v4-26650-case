# Heltec V4 + 26650 Case

Parametric [CadQuery](https://cadquery.readthedocs.io/) model of a
two-piece 3D-printable enclosure for:

- A **Heltec V4** board (ESP32-S3 based Heltec WiFi LoRa 32 V4 form factor,
  **GPS-less variant**)
- An **external antenna** connected via an **IPEX-to-SMA pigtail**, with a
  panel-mount SMA bulkhead hole in the case wall
- A single **26650** Li-ion cell as the power source

Outer size **86.5 × 35.5 × 39.9 mm**.

## Files

- `case.py` — the model, including mock solids for the cell and board.
- `verify.py` — collision / fit checks (see below).
- `output/` — generated STL + STEP. Not checked in; regenerate with
  `python3 case.py`.

## Design

The enclosure is a tub split along a horizontal parting line just above the
board, closed with **four M2 socket-head cap screws** (M2×8) threaded into
printed bosses. The 26650 cell lies **along the case's long axis, centred
directly underneath the board**.

- **Base half** — contains:
  - A **cradle** for the cell: a pedestal filling the cavity up to the
    cell's axis height, with a half-round bore cut through it. The solid
    blocks past each end of the bore act as axial end stops.
  - **Board support rails** running along both long side walls, from the
    pedestal up to the board's underside. The cell bore is cut *through*
    the rails, so they end up hugging the cell's upper flanks.
  - A **USB-C cutout** in the +X end wall, just above the board's top face.
  - A panel-mount **SMA bulkhead hole** (8.4 mm) centred in the −X end
    wall, between the cradle top and the parting line. The pigtail's IPEX
    end plugs into the board's u.FL connector; the SMA end passes through
    this hole and is secured outside with its own nut.
  - Four screw bosses, placed *beyond the ends of the cell bore* (see
    "Why the case is 86.5 mm long" below).
  - A **tongue** around the top perimeter that the plate's skirt closes
    over, with 0.15 mm fit clearance.

- **Plate half (face plate)** — contains:
  - A **cutout over the onboard OLED**, sized from the drawing's 27.28 mm
    active width plus a 0.6 mm margin.
  - **Hold-down ribs** opposite the base's rails, which press on the
    board's long edges from above.
  - Four M2 clearance holes with socket-head counterbores.
  - A skirt that closes over the base's tongue.

### Why the board sits on rails, not standoffs

The cell (26.5 mm dia., 65.0 mm long) is both **wider and longer than the
board** (25.5 × 50.2 mm). Stacking them means the board's entire footprint
is shadowed by the cell, so there is nowhere on the floor to stand a screw
post — and the board's own mounting holes (≈ ±9.25 mm off centreline) sit
directly over the cell.

The board is therefore captured as a **sandwich**: rails below, hold-down
ribs above. **The board's mounting holes are not used for screws in this
layout.** If you need positive screw retention, the alternative is the
end-to-end layout (board beside the cell rather than above it), which
trades a ~131 mm long case for a much flatter one.

### Why the case is 86.5 mm long

The cell bore spans the full cavity width, so a screw boss placed anywhere
within the bore's length would be carved into by it. `OUTER_L` is therefore
derived so the corner bosses clear the ends of the bore:

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
OLED module + USB-C + u.FL) and the SMA bulkhead body, then checks:

- **Pairwise collisions** — boolean intersection volume of every pair of
  solids must be ~0.
- **Containment** — each component's bounding box lies inside the case.
- **Design clearances** — cell slack in the cradle, cell-to-board gap,
  board bearing on the rails, bosses clearing the bore, SMA body clearing
  the cell end, SMA hole landing in solid wall, OLED headroom, and the
  window lying within the module footprint.

All checks currently pass. Key measured clearances:

| Clearance | Value |
|---|---|
| Cell radial slack in cradle | 0.30 mm |
| Cell axial slack | 1.00 mm |
| Cell top → board underside | 2.30 mm |
| Board edge bearing per rail | 1.50 mm |
| Boss inner edge vs. bore end | 34.50 vs 33.00 mm |
| SMA body depth needed / available | 7.00 / 8.05 mm |
| Headroom above OLED module | 1.00 mm |

Note that a zero-overlap result alone would also be satisfied by a part
floating in mid-air, so `verify.py` is complemented by probe checks
confirming that rail material actually exists under the board edges, that
the plate ribs reach the board's top face, and that both halves are single
connected solids.

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
| `BOARD_HOLE_*` | Mounting holes — modelled on the PCB, unused for retention |

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

- Print the base cradle-down and the plate window-up.
- The cell bore's upper flanks form a curved overhang where they meet the
  rails; this is self-supporting for most of its arc but may want a small
  amount of support near the top of the bore.
- The base is a fairly solid part (~46 cm³ of enclosed volume including the
  cradle pedestal) — print it with modest infill rather than solid.
- M2 pilot holes are sized (1.6 mm) for self-tapping M2 screws into
  PLA/PETG; swap in heat-set inserts (and re-check `M2_PILOT_D` /
  `M2_BOSS_D`) for reusable fastening.
- The SMA hole assumes a jam-nut panel-mount bulkhead; add a wrench-flat
  recess (`SMA_NUT_AF`, currently unused) if yours needs anti-rotation.
- **Li-ion safety**: this case has no vent path and no provision for a
  protection circuit or BMS. Use a protected cell, and add a vent hole if
  you intend to leave it charging unattended.

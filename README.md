# Heltec V4 + 26650 Case

Parametric [CadQuery](https://cadquery.readthedocs.io/) model of a
two-piece 3D-printable enclosure for:

- A **Heltec V4** board (ESP32-S3 based Heltec WiFi LoRa 32 V4 form factor,
  **GPS-less variant**)
- An **external antenna** connected via an **IPEX-to-SMA pigtail**, with a
  panel-mount SMA bulkhead hole in the case wall
- A single **26650** Li-ion cell as the power source

## Files

- `case.py` — the model. Run it to (re)generate the outputs.
- `output/` — generated STL + STEP files (base half, plate half, and a
  combined assembly STEP for visual inspection). Not checked in; regenerate
  with `python3 case.py`.

## Design

The enclosure is a compact tub split into two halves along a horizontal
parting line, closed with **four M2 socket-head cap screws** (M2×8
recommended) threaded into printed bosses. The 26650 cell is **stacked
directly beneath the board**, both centred on and running parallel to the
case's long axis (the cell sits centred *behind*/under the board, not
end-to-end with it) -- this keeps the footprint close to the board's own
size rather than stretching the case to fit both parts in a row.

- **Base half** — the deeper half. Contains:
  - A half-round trough sized for a 26650 cell (26.5 mm dia. tolerance,
    65.5 mm length tolerance), centred under the board, with retaining
    end-ribs.
  - Two pairs of board standoffs above the cell (sized for the Heltec V4's
    mounting-hole pattern near the USB-C end, plus a support pair at the
    far end), with pilot holes for self-tapping/press-fit into the board
    (or heat-set inserts if you prefer).
  - A USB-C cutout in the short end wall at the board's connector edge.
  - A panel-mount **SMA bulkhead hole** (8.4 mm) centred in the *opposite*
    short end wall, for the IPEX↔SMA pigtail. The pigtail's IPEX end plugs
    into the board's u.FL/IPEX antenna connector; the SMA end passes
    through this hole and is secured from outside with the connector's own
    nut, so an external screw-on antenna mounts on the case's short side,
    opposite the USB-C port.
  - Four screw bosses with M2 pilot holes.
  - A rabbet/step around the top perimeter that the plate's lip seats into,
    for alignment and a dust/light seal.

- **Plate half (face plate)** — the shallow half that closes over the base.
  Contains:
  - A rectangular **cutout over the onboard OLED** (23 × 13.2 mm), so the
    display remains visible/usable with the case closed.
  - Four M2 clearance holes with socket-head countersinks, aligned with the
    base's screw bosses.
  - A mating lip that drops into the base's rabbet.

## ⚠️ Dimensions you should verify before printing

Board outline (50.2 × 25.5 mm), OLED active width (27.28 mm), and mounting
hole placement are now taken from a Heltec mechanical reference drawing.
PCB thickness, OLED height, and connector positions are still best-effort
estimates, since the drawing doesn't dimension them and the exact board
could not be measured directly in this environment. **Before printing,
measure your actual board and update the constants at the top of
`case.py`:**

| Constant | What to check |
|---|---|
| `BOARD_L`, `BOARD_W`, `BOARD_T` | Board outline and PCB thickness |
| `BOARD_HOLE_D`, `BOARD_HOLE_Y`, `BOARD_HOLE_FROM_TOP` | Mounting-hole positions |
| `OLED_W`, `OLED_H`, `OLED_CENTER_FROM_TOP`, `OLED_CENTER_X_OFFSET` | OLED active-area position/size |
| `USB_W`, `USB_H` | USB-C shroud opening size |
| `SMA_HOLE_D` | Your specific SMA bulkhead connector's panel-hole spec |
| `CELL_D`, `CELL_L` | Your actual 26650 cell (varies with wrap/protection PCB) |

All other dimensions (wall thickness, screw bosses, fillets, etc.) are
derived from these or are independent print/assembly parameters you can
tune directly (`WALL`, `LID_RECESS`, `M2_*`, `SCREW_INSET`, ...).

## Generating the model

```bash
pip install cadquery
python3 case.py
```

This writes to `output/`:

- `heltec_v4_case_base.stl` / `.step`
- `heltec_v4_case_plate.stl` / `.step`
- `heltec_v4_case_assembly.step` (both halves positioned together, for
  visual review only — not intended for printing as one part)

## Printing notes

- Print the base half battery-bay-down; supports are not required.
- Print the plate half OLED-window-up.
- M2 pilot holes are sized (1.6 mm) for self-tapping M2 screws directly
  into PLA/PETG bosses; swap in M2 heat-set inserts (and re-check
  `M2_PILOT_D`/`M2_BOSS_D` against your insert's spec) for a more durable
  and reusable fastening.
- The SMA hole assumes a standard jam-nut panel-mount bulkhead connector;
  add a wrench-flat recess (`SMA_NUT_AF`/`SMA_NUT_DEPTH`, currently unused)
  if your connector needs anti-rotation.

# Heltec V4 + 26650 Case

![Current state of the model](docs/preview.png)

*Regenerated from `case.py` on every change (see `make preview` below) —
this is always the actual current model, not a stale illustration.*

Parametric [CadQuery](https://cadquery.readthedocs.io/) model of a
two-piece 3D-printable enclosure for:

- A **Heltec V4** board (ESP32-S3 based Heltec WiFi LoRa 32 V4 form factor,
  **GPS-less variant**)
- An **external antenna** connected via an **IPEX-to-SMA pigtail**, with a
  panel-mount SMA bulkhead hole axially through the **plate's own -X end
  wall** (see "Why the SMA mount moved to the plate" below)
- A single **26650** Li-ion cell as the power source

Outer size **80.1 × 35.7 × 43.5 mm**.

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
closed with **four M2 socket-head cap screws** (M2×16) threaded into printed
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
  - Four screw bosses, placed *beyond the ends of the shaft*.
  - **No lip at all** — the wall runs full thickness straight up to a flat
    rim (see "Half-lap interface" below).
  - A large **chamfer on the two long bottom edges**, plus a small break on
    the short ends and on the junctions between them (see below).

- **Plate half — the face plate, and it carries the board.** It has:
  - A **cutout over the whole OLED module** (frame + corner screws, not just
    the glass), sized from the module's dimensioned 33.28 × 18.56 mm
    footprint plus a 0.6 mm margin, sitting 0.5 mm above the module.
  - A **rail/lip retention channel** along both long edges instead of screw
    posts — the real board has no mounting holes anywhere (confirmed against
    the top-view reference photo), so it can't hang from screws. A wide
    shoulder registers the board's X/Y position and carries its top face; a
    narrower lip hooks under its underside so it can't drop back out, with a
    short lead-in gap at the antenna end where the board enters during
    assembly. Small preload dimples on the shoulder take up the channel's Z
    slack so the board doesn't rattle. See "Board retention" below.
  - Four M2 clearance holes with socket-head counterbores, each over a
    **post** the screw head bears on.
  - A **plug** hanging below the flange that drops into the base cavity.
  - A **panel-mount SMA bulkhead hole** (6.63 mm), axially through the
    plate's own -X end wall, above the cell and past the board's far edge
    (see "Why the SMA mount moved to the plate" below).
  - A **1.5 mm chamfer around the top outer edge**, and a matching **1 mm
    bevel on the face side of the display cutout** (see below).

The **USB-C opening** falls entirely within the plate now that the parting
line sits just above the cell, so cutting it from the base removes nothing.
It is still cut from both halves from one shared cutter, so the opening
survives if the parting line is ever moved.

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
that sits outboard of the cell's curve, without touching any clearance.
(The base is currently 30.2 cm³ with the chamfer; the exact saving vs. an
unchamfered tub shifts slightly as other constants like `CELL_OFFSET_X`
change the case's length — `make verify` prints the current base volume if
you want the live number.)

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
stands on a **77.10 × 14.00 mm** flat.

The four runout junctions are broken with CadQuery's `.chamfer()` via a
`FlankRunoutSelector` — they are the only edges on the part that are
diagonal in Y/Z while holding X constant, which picks them out exactly
without indexing into an edge list that shifts whenever a feature is added.
OCC blends the break into the 2.5 mm corner fillets where the edges meet
them, which is why it removes ~86 mm³ rather than the ~19 mm³ a naive
prism estimate would suggest.

Both chamfers eat the lower corners of the screw bosses — at Z = 0 the
bosses are gone entirely, emerging from the chamfered corner as they rise
and becoming full by Z ≈ 7.5 mm. That is harmless, since the boss pilot hole only
spans Z 21.2–30.1 mm, but `verify.py` checks the material ring around every
pilot hole anyway.

**Printability** is the reason the slope is exactly 45°. `CHAMFER_ASPECT`
is rise/run, and at 1.0 the flank is a 45° overhang off the bed — the usual
unsupported limit. Set it above 1.0 for a steeper, safer wall that saves
less. `verify.py` fails the build if the overhang ever exceeds 45°.

### How shallow can this get? (depth analysis)

*The numbers below predate the switch from screw-head-governed to
coin-cell/connector-governed `CELL_TO_BOARD_GAP` and haven't all been
refreshed to match — treat this section as historical framing of the
trade-off, not a live number source; `make verify`'s summary output has the
current figures.*

Full Z-stack, base floor to plate top, at the current settings:

| Layer | Height | Hard or soft? |
|---|---|---|
| Floor | 2.00 mm | **Hard** — minimum structural floor |
| Cradle (floor → cell axis) | 13.55 mm | **Hard** — half the cell's own diameter |
| Cell (axis → bore top) | 13.55 mm | **Hard** — the other half |
| Cell top → board underside | 5.90 mm | Soft (coin-cell holder + margin) |
| Board PCB | 1.60 mm | **Hard** — real PCB thickness |
| OLED module | 4.00 mm | Soft — **estimate**, not measured |
| Module top → window | 0.50 mm | Soft, already minimal |
| Plate top wall | 2.20 mm | **Hard** — matches `WALL` |
| **Total** | **39.90 mm** | |

**80% of the case's height (32.9 of 39.9 mm) is structurally fixed** — the
cell's own diameter plus the floor, the PCB and the top wall. That's the
real cost of stacking the cell directly under the board rather than beside
it, and it can't be trimmed without shrinking the cell, thinning the walls,
or going back to the side-by-side layout (which trades this compactness
for ~131 mm of length instead — see the design history in this file's git
log if you want that trade the other way).

Of the remaining 20%, one reduction has actually been made:

- **`CELL_TO_BOARD_GAP` was cut from 3.5 mm to 2.5 mm** (saving 1.0 mm off
  the total), sized to exactly what the board-retention screw heads need
  (`M2_HEAD_H` = 2.2 mm) plus a 0.3 mm margin — **not** to any header-pin
  protrusion. This case assumes the board's 2.54 mm GPIO header rows are
  left **unpopulated** (`HEADER_PIN_PROTRUSION = 0`). If your board has
  headers soldered, the pins typically protrude 2–3 mm below the PCB and
  would land inside this gap — raise `HEADER_PIN_PROTRUSION` before
  printing, which flows through to `CELL_TO_BOARD_GAP` automatically and is
  checked by `verify.py`.

Worth flagging: cutting this gap took the clearance between the cell and
the board's *screw heads* specifically (not just the PCB) down to
**0.60 mm** (from 1.60 mm before). That's still positive and enforced by
`verify.py`, but it's thin — if you print with looser tolerances than
`CELL_CLEARANCE` (0.6 mm total) assumes, this is the margin that goes first.

The one dimension left on the table is **`OLED_MODULE_THICK` (4.0 mm)** —
flagged `(est)` since the reference drawing doesn't dimension it, and
carried over unchanged since the very first version of this model. Many
0.96" OLED modules used on Heltec-style boards are reflow-soldered
low-profile assemblies closer to 1.5–2 mm; if you can measure your actual
module, dropping this to a real value is worth up to ~2 mm more — a bigger
lever than anything else remaining, but not one to guess at without the
part in hand.

### Half-lap interface

The two halves meet as a plain half-lap: the base is a flat-rimmed tub with
no lip whatsoever, and the plate carries a plug that drops inside it.

```
————————      plate flange, full outer footprint
——____——      plug, inset to fit the base cavity

||    ||      base wall, plain and full thickness
```

This replaced a tongue-and-skirt joint that split the 2.2 mm wall
lengthwise, and it was as bad to print as it sounds:

| | Thickness | Height | Aspect | Widths @ 0.4 mm |
|---|---|---|---|---|
| Old base tongue | 0.88 mm | 5.0 mm | 5.7:1 | 2.2 |
| Old plate skirt | 1.17 mm | 5.0 mm | 4.3:1 | 2.9 |
| **New plug** | **1.60 mm** | **3.0 mm** | **1.9:1** | **4.0** |

The base's wall is now full `WALL` thickness right to the rim, and the plug
is a free-standing wall that can be sized independently of it. Fit is
`FIT_CLEARANCE` (0.15 mm) per side.

One wrinkle worth knowing if you change these numbers: the plug is inset
well clear of the plate's own 2.2 mm wall, so it cannot hang off it — a
first attempt left the plug as a **second, disconnected solid**. It is
carried instead by a short internal ledge (`PLUG_LEDGE`, 1.5 mm) just below
the board, where the plug's inner face and the ledge's inner face are cut as
one surface. Above the ledge the plate reverts to a thin wall. The plug is
also notched around the base's four screw bosses, which rise to the rim.

### The screws actually clamp something now

The case screws pass through a post in the plate and thread into the boss
below, so the stack is:

```
head seats on the post top ─┐
   counterbore (2.2 mm, the full top wall)
   plate post 11.00 mm   ────┤ M2x16
   ── parting line ──
   base boss   5.00 mm engagement
```

The counterbore is exactly as deep as the plate's top wall, so **the head
bears on the top of the plate's post, not on the wall**. Without that post
there is nothing under the head at all — which is precisely what the
earlier revision shipped: `verify.py` measured **0.00 mm³** of material
under every screw head, and the screws would have pulled straight through
on first tightening. There is now a per-screw seat check, confirmed to fail
if the posts are removed.

The posts also set the screw length: crossing an 11.0 mm post and still
biting needs **M2×16**, not the M2×8 quoted earlier.

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
  34.48 × 19.76 mm at the inside face (the whole OLED module footprint plus
  margin, not just the glass) and opens out to 36.48 × 21.76 mm at the
  visible surface. With a 2.2 mm top wall that leaves a **1.2 mm straight
  land** behind the aperture.

Putting the bevel on the face side rather than the inside means the hole
**only ever widens with height**. Printed window-up, every layer is
supported by the one below, so there is no overhang anywhere in the
window — unlike an inside flare, which would have to bridge inward across
the opening. `verify.py` asserts this directly by sampling the opening
through the wall and requiring it to widen monotonically.

The bevel is produced with CadQuery's `.chamfer()` on the finished top
edge, so the cutter stays a plain rectangular prism and the aperture is
exactly `OLED_WINDOW_W × OLED_WINDOW_H` by construction. `.faces(">Z").edges()` would
also catch the plate's outer perimeter, so the window's four edges are
isolated with a `BoxSelector` around them. `verify.py` measures the real
opening at both faces rather than trusting any of that.

### Why the board hangs from the plate

This is forced by the geometry, not a style choice. The cell (26.7 mm dia.,
65.2 mm long) is both **wider and longer than the board** (51.0 × 25.6 mm),
so the board's entire footprint is shadowed by the cell — and by the cell's
vertical insertion path above it.

An earlier revision supported the board on rails along the base's side
walls. Those rails reached inward to catch the board's edges, which choked
the opening for the cell — the cell could not be fitted at all without
springing the case apart. Any base-side board support has the same problem:
to touch a board narrower than the cell, it must intrude into the cell's
path. This is also why the board can't be retained on **base-side**
pedestals now that it has no mounting holes (see "Board retention" below) —
the base's own top surface sits below the board's underside anyway, so a
pedestal would have to clear the cell *and* poke up past the parting line.

So the board is mounted to the plate, and the base is left completely
clear. `verify.py` enforces this with a `base carries no board-support
features` check.

**Consequences worth knowing:**

- Assembly order is: drop the cell into the base → lift the board up into
  the plate's rail channel from its open underside → lower the plate onto
  the base → four case screws.
- The board is retained by a rail/lip channel rather than screws (see below)
  — nothing threads into the PCB.
- The GPS/battery/solar connector mocks on the board's underside sit with
  **2.2 mm** of clearance to the cell, tighter than the coin-cell holder's
  6.2 mm since they protrude less.

### Board retention: rail/lip channel, no PCB holes

The real board (confirmed against `reference/heltec_v4_top.JPG`) has **no
mounting holes anywhere** — the USB-C end is just header pins, two tactile
buttons and the connector. Earlier revisions of this model assumed two
holes there (`BOARD_HOLE_*`, now removed) and hung the board from screw
posts; that assumption never had a source and turned out wrong.

Instead, the plate's cavity — open on its underside, since that's how both
the board and the base's plug get in — grows a **shoulder** and a **lip**
along both long edges:

- The **shoulder** (`RAIL_SHOULDER_INNER_Y` to `RAIL_OUTER_Y`, 10.5–13.2 mm)
  is a full-height rib the board's top face rests against, registering its
  X/Y position — this replaces what the screw posts and bearing posts used
  to do.
- The **lip** (`RAIL_LIP_INNER_Y` to `RAIL_OUTER_Y`, 11.7–13.2 mm) is a thin
  shelf just below the board's underside that hooks it in place so it can't
  drop back out. It starts `LIP_LEAD_IN` (5 mm) in from the antenna end,
  leaving that stretch lip-free as the gap the board enters through before
  sliding home toward the USB-C end.
- Small **preload dimples** (`PRELOAD_BUMP_INTERFERENCE`, 0.2 mm) on the
  shoulder are deliberately oversized by that much and get elastically
  compressed as the board seats, taking up `BOARD_SLOT_CLEARANCE` (0.3 mm)
  so it doesn't rattle. `verify.py` gives the `plate`/`board` pair a wider,
  explicitly-bounded tolerance for exactly this designed overlap.

The rail's own +X end doubles as the board's insertion endstop, which is
what keeps the USB-C connector registered against the case's cutout (see
below) — sliding the board fully home is what closes the gap.

This is a first-pass mechanical design, not something validated by a real
print yet: the exact insertion choreography (straight press-fit vs.
slide-then-hook) and how well `RAIL_LIP_INNER_Y` biting ~1.1 mm onto the
PCB's edge strip holds up in practice are worth a test print of the plate
alone before trusting them, in the same spirit as the tongue/skirt →
half-lap plug iteration below.

### Why the case is 80.1 mm long

The insertion shaft spans most of the cavity width, so a screw boss placed
anywhere within its length would stand in the cell's way. `OUTER_L` is
therefore derived so the corner bosses clear the ends of the shaft:

```
OUTER_L = 2 × (CELL_FAR_HALF_LEN + BOSS_END_MARGIN + M2_BOSS_D/2 + SCREW_INSET)
```

This is checked by `verify.py`, so changing the cell or screw parameters
keeps the constraint satisfied automatically. (`CELL_FAR_HALF_LEN` folds in
`CELL_OFFSET_X`, currently 0 — see "The cell offset" below — so this
formula is also what shrank the case a further 6mm once the SMA connector
stopped needing that offset for axial room.)

`SCREW_INSET` itself is no longer a hand-picked constant — it's solved for
the smallest value that still keeps the boss enclosed, which is what
shrank the case from 92.7 mm (the previous, arbitrarily generous 6.0 mm
inset) down to 86.1 mm on its own, before the `CELL_OFFSET_X` change below
took it to 80.1 mm. Two independent constraints compete, and `SCREW_INSET`
takes whichever binds tighter:

- **Corner tangency**: the boss's closest approach to the outside is along
  the corner's 45° diagonal, where the outer profile is the `CORNER_FILLET`
  arc rather than a flat wall. Solving for the boss (radius `M2_BOSS_D/2`,
  plus a small `BOSS_OUTER_MARGIN` of backing material) to be tangent to
  that arc gives `inset ≈ 2.68 mm` — but the boss (5.5 mm across) is bigger
  than a single wall is thick (2.2 mm), so it can never *also* be tangent to
  the inner wall without breaching the outer one. This is inherent to the
  boss/wall proportions, not a bug.
- **Counterbore vs. face chamfer** (the one that actually wins, at
  `inset = 3.7 mm`): push the boss out any further and its M2 socket-head
  counterbore starts clipping into the top face's own `FACE_CHAMFER` edge
  break instead of landing on flat material. `verify.py`'s existing `face
  chamfer clears the screw counterbores` check is what originally caught
  this when the corner-tangency value alone was tried.

A dedicated check (`boss + margin backed by material at corner ...`) probes
the built solid directly along each boss's outward diagonal, rather than
trusting either formula.

### The cell offset -- a live parameter, currently unused

`CELL_OFFSET_X` shifts the cell, its bore and its insertion shaft along X
(positive = toward the USB-C/+X end, away from the antenna/-X end), at a
1:2 cost of case length for antenna-side clearance (every mm of offset
grows `OUTER_L` by 2mm, since the outer envelope stays symmetric). It used
to be 3.0mm, sized to give the old axially-mounted SMA connector body room
inside the -X end wall. It's **0mm now** — see "Why the SMA mount moved to
the plate" below for why that room is no longer needed — but the mechanism
is kept, not deleted, in case some future component wants the same trade.
`verify.py` measures the offset off the *built* bore geometry (not just the
formula) and checks it points whichever way `CELL_OFFSET_X`'s sign says it
should, including the degenerate "both ends equal" case at 0.

(The board's own X position moves separately, by `BOARD_CENTER_X` — see
"Board retention" above — to pull the USB-C connector close to the case's
cutout. That's an independent shift for an unrelated reason; it just
happens to use the same axis. It changes anyway when `CELL_OFFSET_X` does,
though, because the +X corner screw boss it's measured against moves with
`OUTER_L`.)

### Adding the SMA connector: real datasheet dimensions

`build_sma_connector()` models the actual bulkhead jack, outward to inward,
all measured off its datasheet rather than estimated:

| Feature | Size |
|---|---|
| Threaded barrel (1/4-36 UNS-2A), mostly exposed outside | Ø6.19–6.33mm major dia. × 13mm long |
| Washer, flush against the wall's inside face | (est) 9.5mm OD × 2mm thick |
| Fixed nut (swaged behind the washer, can't back off) | 8mm across flats × 2mm thick |
| Stiff pigtail stub (before the flexible cable) | Ø4mm × 13mm long |

`SMA_HOLE_D` (the panel clearance hole) is `SMA_THREAD_MAJOR_MAX +
SMA_HOLE_CLEARANCE` = 6.63mm — sized to the real thread, not the old flat
8.4mm guess, and the hole through the wall stays exactly that size (the
wider ledge clearance behind it, see below, is a separate cut that never
touches the wall itself). Neither the washer nor the fixed nut behind it
can pass through a hole that size, which is the point: the connector is
installed from the inside, barrel first, until the washer bottoms out
flush against the wall's inside face — `SMA_WASHER_OUTER_X` is exactly
the wall's inner-face X, zero gap, not offset inward for any reason — with
the fixed nut riding right behind it. The washer's OD isn't on the
datasheet, so it's `(est)`, sized to just clear the nut's own
corner-to-corner distance (`AF/cos(30°)` = 9.24mm for an 8mm hex) since a
narrower washer couldn't physically contact it.

### Why the SMA mount moved to the plate

The connector was originally modelled axially, through the **base's** -X
end wall, with an (est) 7mm guess for how far its body protrudes inward.
Once the real datasheet numbers went in, that guess turned out very wrong:
the connector's rigid stack — washer (2mm) + fixed nut (2mm) + stiff
pigtail stub (13mm) = **17mm** — needs far more depth than
`SMA_CLEAR_DEPTH` (4.75mm with no offset, and even the old 3.0mm offset
only bought 10.75mm) provides there. Keeping it in the base would mean
growing `CELL_OFFSET_X` to roughly 6.1mm just to fit
(`SMA_CLEAR_DEPTH = 2×CELL_OFFSET_X + 4.75`), pushing the case out to
**~92.4mm** — longer than before any of this session's other tightening.

A vertical mount through the top face was tried next and technically fit,
but was rejected in favour of keeping the connector's usual front-facing
orientation. The mount that stuck is axial, through the **plate's own**
portion of the -X end wall instead of the base's -- same orientation as
the original, just carried by the other half. That one change sidesteps
the cell entirely: the plate's whole Z-band sits above `CELL_TOP_Z`, so
unlike a base-mounted hole, axial depth here was never limited by
`SMA_CLEAR_DEPTH` or the cell's near end at all -- only by the board's own
far edge, which is much further away. That's what let `CELL_OFFSET_X` go
to **0** (see above) instead of growing to 6.1mm: **the case is 80.1mm
long now, 6mm shorter than the 86.1mm it would've been just from the other
changes this session, and 12.3mm shorter than the 92.4mm a corrected axial
base mount would have needed.**

Two real constraints replace the old cell-clearance one:

- **The half-lap ledge.** The plate's ledge (`PLUG_LEDGE` tall, `PLUG_WALL`
  thick, inset by `FIT_CLEARANCE`) is solid material right at the wall's
  inner face, for `Z <= PLUG_LEDGE` only — exactly where the washer, flush
  against the wall with no offset, would otherwise collide with it. Rather
  than move the connector to dodge it, `_sma_ledge_notch()` cuts the ledge
  back locally instead, the same pattern `build_plate()` already used to
  let the case screw bosses through the plug. That leaves `SMA_Z` free to
  sit wherever gives the most margin to the plate's own ceiling, not
  pinned between the ledge and the ceiling. (An earlier version of this
  notch started from the wall's *outer* face by mistake, washer-sizing the
  visible panel hole instead of just the ledge behind it — fixed by
  starting the notch at the wall's inner face, so the hole stays exactly
  `SMA_HOLE_D`.)
- **The board's far edge**, now the binding constraint instead of the
  cell: `BOARD_CENTER_X` itself shrank once `OUTER_L` did (it's measured
  against the same +X corner boss, which moved), which pulled the board's
  far edge toward the antenna end. Measured margin is **2.75mm** — tight
  by this file's standards, but `verify.py`'s pairwise collision check
  also confirms zero actual overlap against the real board solid, not just
  this margin number.

This is derived, not hand-tuned: every formula that has to avoid the bore
(`OUTER_L`, the screw-boss clearance check, the end chamfer's wall check)
works off `CELL_FAR_HALF_LEN` — the half-length of whichever side is
actually closer to its wall — rather than assuming the bore is centred, so
raising `CELL_OFFSET_X` again later (if some other component needs it)
flows through automatically.

## Verifying fit

```bash
python3 verify.py
```

This builds both halves plus mock solids for the cell, the board (PCB +
OLED module + USB-C + u.FL on top, GPS + battery/solar connectors on the
underside) and the SMA bulkhead connector (nut + washer + fixed pigtail
stub, mounted axially through the plate's own -X end wall), then checks:

- **Pairwise collisions** — boolean intersection volume of every pair of
  solids must be ~0.
- **Insertion path** — the base must not intrude into the insertion shaft
  at all, and the shaft must be wide/long enough and reach the open top.
  The clear opening is also *sampled* at 41 heights above the cradle, so a
  feature that narrows the path anywhere is caught (this is exactly how the
  old rail design was found to be unbuildable).
- **Containment** — each component's bounding box lies inside the case.
- **Support** — probes along the rail shoulder's span confirm it's present
  the whole way from the antenna end to the USB-C endstop, and a probe past
  the lead-in gap confirms the lip actually traps the board's underside,
  rather than the board floating or falling back out.
- **Bottom and end chamfers** — the large flank stays confined to the long
  edges and the end break stays small, overhangs stay within 45°, enough
  wall is left over the cell bore, the standing flat is usable, and the
  chamfers clear the boss pilot holes. The built solid is
  *sampled* at three heights against each intended profile, the bottom face
  is measured against both, the runout break is confirmed by rebuilding
  without it and comparing volumes, and the material ring around every boss
  pilot hole is checked since the chamfers cut the bosses' lower corners.
- **Face plate chamfers** — the window's real opening is measured at both
  the outer and inside faces, the opening widens monotonically through the
  wall (so the bevel is never an overhang), the aperture leaves a straight
  land and clears the retention rails, and the face chamfer leaves the
  counterbores on the flat without breaching the plate ceiling.
- **Half-lap interface and screw stack** — the base has no lip above the
  parting line, the plug is printable (thickness and aspect ratio) and a
  slip fit, its ledge stays below the board, every screw head has material
  to seat on, and the screw is long enough to cross the plate post and
  still bite into the boss. (Whether the plug fouls the SMA connector's
  stub is covered by the general pairwise collision check now, not a
  dedicated formula.)
- **Design clearances** — cell slack, cell-to-board gap, connector clearance
  over the cell, bosses clearing the shaft, the SMA barrel clearing the
  half-lap ledge, the SMA nut/washer/stub clearing both the ledge and the
  plate ceiling, and the whole connector clearing the board's far edge, the
  board's shifted position clearing the +X corner screw boss, the USB-C
  connector actually sitting close to the case's cutout,
  and the OLED module fitting within the (now larger) window opening.

All checks currently pass. Key measured clearances:

| Clearance | Value |
|---|---|
| Narrowest opening above cradle | 31.30 mm (cell needs 26.70) |
| Cell radial slack in cradle | 0.30 mm |
| Cell axial slack | 1.00 mm |
| Cell top → board underside | 6.20 mm |
| Cell top → GPS/battery/solar connectors | 2.20 mm |
| Boss inner edge vs. shaft +X end | 33.60 vs 33.10 mm |
| SMA washer vs. wall inner face (X) | -37.850 vs -37.850 (flush, 0 gap by design) |
| SMA washer vs. plate ceiling | Z(local)=10.25 vs 11.00 (0.75 mm clear) |
| SMA connector vs. board's far edge | X=-20.85 vs -18.10 (2.75 mm clear) |
| Rail shoulder inner edge vs. OLED window | 10.50 vs 9.88 mm |
| Rail outer edge vs. board+clearance edge | 13.20 vs 13.20 mm |
| Board pocket edge vs. +X corner boss | 33.30 vs 33.60 mm |
| USB-C connector face vs. inner wall | 3.95 mm (was 17.65 mm before any of this session) |
| Headroom above OLED module | 0.50 mm |
| Plug wall / depth | 1.60 mm × 3.00 mm (1.9:1) |
| Plug fit clearance | 0.15 mm per side |
| Material under each screw head | 2.63 mm³ |
| Case screw engagement in boss | 5.00 mm |
| Chamfer wall over the cell bore | 3.35 mm (min 2.20) |
| Chamfer overhang | 45.0° (limit 45°) |
| Flat the case stands on | 77.10 × 14.00 mm |
| Long-edge chamfer / end break | 10.85 / 1.50 mm |
| Window aperture (inside face) | 34.48 × 19.76 mm (whole OLED module + margin) |
| Window at face side (bevelled) | 36.46 × 21.74 mm |
| Straight land behind the aperture | 1.20 mm |
| Face chamfer to counterbore | 16.35 vs 16.15 mm |
| Boss + margin backed by material (corner diagonal) | tangent, by construction |

Note that a zero-overlap result alone would also be satisfied by a part
floating in mid-air, which is why the support probes and the
narrowest-opening sampling are there.

## ⚠️ Dimensions you should verify before printing

Board outline (51.0 × 25.6 mm), PCB thickness (1.6 mm), OLED active/module
width (27.28 / 33.28 mm), module height (18.56 mm) and header pitch are
measured directly off `reference/heltec_v4_top.JPG` and
`reference/heltec_v4_side.JPG` (own board, hand-annotated). Everything
marked `(est)` in `case.py` is **not** dimensioned on those photos and is a
best-effort estimate — notably component heights and some connector
positions.

| Constant | What to check |
|---|---|
| `OLED_MODULE_THICK` | OLED module height above the PCB (assumed 4.0 mm) |
| `OLED_CENTER_X`, `OLED_MODULE_EDGE_GAP` | Where the module sits along the board — cross-checked against the photo's own "17.5mm, USB edge to OLED edge" callout, but only to hand-measurement precision |
| `USB_W`, `USB_H`, `USB_DEPTH` | USB-C body size and position |
| `UFL_FROM_END` | u.FL connector position |
| `SMA_WASHER_OD` | The one connector dimension not on the datasheet — sizes `SMA_NOTCH_R` and how much margin is left to the board's far edge (2.75mm) |
| `CELL_D`, `CELL_L` | Your actual 26650 (varies with wrap / protection PCB) |
| `CONN_W`, `CONN_D`, `CONN_H` | GPS + battery/solar connector mocks — width and height are measured off the side-view photo, depth is an estimate (not visible in that photo), and the battery/solar pair is modelled as one combined footprint since the photo doesn't resolve the split |
| `RAIL_LIP_INNER_Y` | Retention lip — bites ~1.1mm onto the PCB's edge strip; assumes that strip is free of traces/components, not confirmed off the photo |
| `BOARD_CENTER_X`, `BOARD_BOSS_CLEARANCE` | How far the board is shifted toward USB-C, and the margin kept from the +X corner screw boss (currently the binding constraint, not the wall) |
| `BOSS_OUTER_MARGIN`, `COUNTERBORE_MARGIN` | How tightly `SCREW_INSET` is pushed into the corner — printers with looser tolerance than these small margins assume should grow them, which pulls the boss (and the whole case length) back out a bit |
| `CHAMFER_ASPECT`, `MIN_BOTTOM_W` | Bottom chamfer: slope and standing flat |
| `END_CHAMFER`, `PROFILE_EDGE_CHAMFER` | Small breaks on the short ends and the flank runouts |
| `FACE_CHAMFER`, `WINDOW_CHAMFER` | Face plate edge break and display-cutout bevel |
| `PLUG_DEPTH`, `PLUG_WALL`, `PLUG_LEDGE`, `FIT_CLEARANCE` | Half-lap plug geometry and fit |
| `CELL_OFFSET_X` | How far the cell is shifted toward USB-C / away from the antenna |
| `HEADER_PIN_PROTRUSION` | **Set this if your board's GPIO headers are populated** — default assumes unpopulated; see "How shallow can this get?" |

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
- The base is ~24 cm³ of enclosed volume including the cradle pedestal —
  print it with modest infill rather than solid.
- The bottom chamfers print as 45° expanding overhangs straight off the
  bed, so they need no support, but the first layer is only
  77.10 × 14.00 mm — use a brim if adhesion is marginal.
- M2 pilot holes are sized (1.6 mm) for self-tapping M2 screws into
  PLA/PETG; swap in heat-set inserts (and re-check `M2_PILOT_D` /
  `M2_BOSS_D`) for reusable fastening.
- The case screws are **M2×16** — long enough to cross the plate's post and
  bite 5.0 mm into the base boss. The board itself has no screws at all —
  see "Board retention" above.
- The SMA connector's own fixed nut clamps it to the plate from the inside
  (see "Adding the SMA connector" above) — no separate jam nut needed on
  the panel side, and `SMA_NUT_AF` is now actually used, for the nut mock's
  hex cross-section.
- **Li-ion safety**: this case has no vent path and no provision for a
  protection circuit or BMS. Use a protected cell, and add a vent hole if
  you intend to leave it charging unattended.

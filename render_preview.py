"""
Render a single isometric preview PNG of the assembled case, to a fixed
path that's checked into the repo and embedded near the top of README.md.

This is the one artefact from case.py that IS committed (everything else
under output/ is gitignored and regenerated on demand) -- its entire point
is to let the README show the current state of the model at a glance,
without anyone having to run the model themselves. That only holds if it's
regenerated every time case.py changes, which is why `make` depends on it
(see Makefile) rather than leaving it as a manual step.

Usage:
    python3 render_preview.py

Requires cadquery (for the model) and cairosvg (for SVG -> PNG). Both are
already needed to work on this repo at all; see README.md.
"""

import os
import cadquery as cq
from cadquery import exporters

import case

PREVIEW_SVG = "docs/preview.svg"
PREVIEW_PNG = "docs/preview.png"
PREVIEW_WIDTH_PX = 1400

# Isometric-ish direction chosen to show the octagonal bottom chamfer, the
# OLED window, the USB-C notch and the SMA hole all in one shot.
PROJECTION_DIR = (0.85, -0.85, 0.5)


def build_preview_assembly():
    parts = case.assemble()
    assy = cq.Assembly()
    assy.add(parts["base"], name="base", color=cq.Color(0.55, 0.60, 0.65, 1.0))
    assy.add(parts["plate"], name="plate", color=cq.Color(0.75, 0.45, 0.20, 1.0))
    return assy


def main():
    os.makedirs("docs", exist_ok=True)

    assy = build_preview_assembly()
    exporters.export(assy.toCompound(), PREVIEW_SVG, opt={"projectionDir": PROJECTION_DIR})

    try:
        import cairosvg
    except ImportError as exc:
        raise SystemExit(
            "cairosvg is required to rasterise the preview (pip install cairosvg)"
        ) from exc

    cairosvg.svg2png(
        url=PREVIEW_SVG,
        write_to=PREVIEW_PNG,
        output_width=PREVIEW_WIDTH_PX,
        background_color="white",
    )
    os.remove(PREVIEW_SVG)  # intermediate only -- keep the repo to one file

    print(f"Wrote {PREVIEW_PNG}")


if __name__ == "__main__":
    main()

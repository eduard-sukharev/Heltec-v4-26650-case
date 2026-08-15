# Regenerate the case model and check it, without retyping python one-liners.
#
#   make            - generate STL/STEP into output/, and refresh the
#                      README preview image (default)
#   make preview    - just refresh docs/preview.png from the current model
#   make verify     - run the collision / fit / insertion-path checks
#   make all        - generate, refresh the preview, then verify
#   make clean      - remove generated output/ (docs/preview.png is
#                      checked in, not generated output, so it is not
#                      touched by this)
#
# case.py, verify.py and render_preview.py all import cadquery; if that
# import fails, run `pip install cadquery` first (see README.md).
# render_preview.py additionally needs cairosvg.
#
# docs/preview.png is committed to the repo (unlike output/) specifically
# so the README always shows the current state of the model at a glance.
# That guarantee only holds if it's regenerated whenever case.py changes --
# `generate` depends on `preview` for exactly that reason. After editing
# case.py, run `make` and git-add the updated docs/preview.png along with
# your other changes.

PYTHON  ?= . ~/miniforge/bin/activate && python3
OUTDIR  := output
DOCDIR  := docs

GENERATED := \
	$(OUTDIR)/heltec_v4_case_base.stl \
	$(OUTDIR)/heltec_v4_case_base.step \
	$(OUTDIR)/heltec_v4_case_plate.stl \
	$(OUTDIR)/heltec_v4_case_plate.step \
	$(OUTDIR)/heltec_v4_case_retainer.stl \
	$(OUTDIR)/heltec_v4_case_retainer.step \
	$(OUTDIR)/heltec_v4_case_assembly.step \
	$(OUTDIR)/heltec_v4_case_assembly.stl \
	$(OUTDIR)/heltec_v4_case_assembly.gltf

.PHONY: all generate preview verify clean

# generate is first, so a bare `make` regenerates STL/STEP *and* refreshes
# the preview -- matching the header comment above -- without also running
# the (slower) checks.
generate: $(OUTDIR)/.generated preview

all: generate verify

# case.py writes all nine STL/STEP/glTF files together in one process, so
# they share a single rule with a stamp file: any of them missing, or case.py
# newer than the stamp, re-runs the whole generator exactly once.
$(OUTDIR)/.generated: case.py
	$(PYTHON) case.py
	@touch $@

$(GENERATED): $(OUTDIR)/.generated

# The preview is its own rule (not folded into the stamp above) because it
# lives outside output/ and must survive `make clean`.
preview: $(DOCDIR)/preview.png

$(DOCDIR)/preview.png: case.py render_preview.py
	$(PYTHON) render_preview.py

verify: case.py verify.py
	$(PYTHON) verify.py

clean:
	rm -rf $(OUTDIR)

# Regenerate the case model and check it, without retyping python one-liners.
#
#   make            - generate STL/STEP into output/ (default)
#   make verify     - run the collision / fit / insertion-path checks
#   make all        - generate then verify
#   make clean      - remove generated output/
#
# case.py and verify.py both import cadquery; if that import fails, run
# `pip install cadquery` first (see README.md).

PYTHON  ?= python3
OUTDIR  := output

GENERATED := \
	$(OUTDIR)/heltec_v4_case_base.stl \
	$(OUTDIR)/heltec_v4_case_base.step \
	$(OUTDIR)/heltec_v4_case_plate.stl \
	$(OUTDIR)/heltec_v4_case_plate.step \
	$(OUTDIR)/heltec_v4_case_assembly.step

.PHONY: all generate verify clean

# generate is first, so a bare `make` only regenerates -- matching the
# header comment above -- rather than also running the (slower) checks.
generate: $(OUTDIR)/.generated

all: generate verify

# case.py writes all five files together in one process, so they share a
# single rule with a stamp file: any of them missing, or case.py newer than
# the stamp, re-runs the whole generator exactly once.
$(OUTDIR)/.generated: case.py
	$(PYTHON) case.py
	@touch $@

$(GENERATED): $(OUTDIR)/.generated

verify: case.py verify.py
	$(PYTHON) verify.py

clean:
	rm -rf $(OUTDIR)

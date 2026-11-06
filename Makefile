# Cogncur -> Google Fonts pipeline. `make all` = sources, build, test, qa.
SHELL := /bin/bash
VENV  := .venv
PY    := $(VENV)/bin/python
export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

STYLE  := Regular
LAYER  := GRegOutl
FAMILY := Vtex
SFD    := upstream/sources/Cogncur.sfd
REF    := upstream/fonts/cogncur.ttf
UFO    := sources/$(FAMILY)-$(STYLE).ufo
TTF    := fonts/ttf/$(FAMILY)-$(STYLE).ttf
REPORT := tests/report

.DEFAULT_GOAL := all
.PHONY: all venv upstream sources build test selftest qa corpus serve artifact

serve:  ## live comparison tool at http://127.0.0.1:8765/tools/live.html
	@echo "Open http://127.0.0.1:8765/tools/live.html  (Ctrl+C to stop)"
	$(PY) -m http.server 8765 --bind 127.0.0.1

all: sources build test qa

venv:
	python3 -m venv $(VENV) && $(PY) -m pip install -q -r requirements.txt

upstream:  ## clone upstream at the pinned commit
	test -d upstream || git clone -q https://github.com/syboor/cogncur.git upstream
	git -C upstream checkout -q $$(cat upstream.lock)

sources:  ## .sfd -> raw UFO (FontForge) -> GF-ready UFO
	mkdir -p build sources
	rm -rf build/raw-$(STYLE).ufo build/skeleton-$(STYLE).ufo build/extra-$(STYLE).ufo
	fontforge -lang=py -script scripts/export_ufo.py $(SFD) $(LAYER) build/raw-$(STYLE).ufo build/skeleton-$(STYLE).ufo build/extra-$(STYLE).ufo 2> build/export-$(STYLE).log
	$(PY) scripts/postprocess_ufo.py build/raw-$(STYLE).ufo $(UFO) --style $(STYLE) --skeleton build/skeleton-$(STYLE).ufo --extra build/extra-$(STYLE).ufo

build:
	cd sources && PATH="$(CURDIR)/$(VENV)/bin:$$PATH" gftools builder config.yaml # sources/config.yaml

corpus:
	$(PY) scripts/make_corpus.py

test:  ## compare new build against the upstream reference + check the new letters
	$(PY) tests/compare.py $(REF) $(TTF) --out $(REPORT)
	$(PY) tests/check_composites.py $(TTF) $(UFO) build/composites.json --reference $(REF) --out $(REPORT)

selftest:  ## reference vs itself: must PASS with zero differences
	$(PY) tests/compare.py $(REF) $(REF) --out build/report-selftest

qa:  ## Google Fonts checks + GF visual diff (informational, never fails the build)
	-$(VENV)/bin/fontbakery check-googlefonts -l WARN --succinct --html $(REPORT)/fontbakery.html --ghmarkdown $(REPORT)/fontbakery.md $(TTF) > build/fontbakery.txt 2>&1; tail -1 build/fontbakery.txt
	-$(VENV)/bin/diffenator2 diff -fb $(REF) -fa $(TTF) -o $(REPORT)/diffenator > build/diffenator.log 2>&1; tail -2 build/diffenator.log

artifact:  ## package tools/live.html + fonts for the private Claude artifact (build/artifact/)
	$(PY) scripts/build_artifact.py

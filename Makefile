# Cogncur -> Google Fonts pipeline. `make all` = sources, build, test, qa.
SHELL := /bin/bash
VENV  := .venv
PY    := $(VENV)/bin/python
export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

STYLE  := Regular
LAYER  := GRegOutl
FAMILY := Cogncur
SFD    := upstream/sources/Cogncur.sfd
REF    := upstream/fonts/cogncur.ttf
UFO    := sources/$(FAMILY)-$(STYLE).ufo
TTF    := fonts/ttf/$(FAMILY)-$(STYLE).ttf
REPORT := tests/report

.DEFAULT_GOAL := all
.PHONY: all venv upstream sources build test selftest qa corpus serve designer routes web-data web release publish

serve:  ## the website with live reload at http://localhost:4321/cogncur/ (run make web-data first after a font change)
	npm --prefix web install --no-audit --no-fund
	npm --prefix web run dev

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

designer:  ## rebuild + regenerate the designer's SVG/EPS files (docs/ontwerper/); then commit + push
	$(MAKE) sources build
	$(PY) scripts/designer_files.py
	@git status --short docs/ontwerper
	@echo "Commit en push docs/ontwerper/: de links in de GitHub-issues wijzen naar main."

routes:  ## draft pen routes per glyph -> build/routes.json + tests/report/routes.html (needs sources + build)
	$(PY) scripts/routes.py

web-data:  ## fonts + data for the website -> web/public/ (commit them; CI can't run FontForge)
	$(PY) scripts/export_web.py

web: web-data  ## build the website (Astro) into web/dist/; GitHub Actions does this on every push
	npm --prefix web ci && npm --prefix web run build

release:  ## local only: new font version V=1.001 (bump, rebuild, test, archive for the website, commit + tag)
	@test -n "$(V)" || { echo "Gebruik: make release V=1.001"; exit 1; }
	$(PY) scripts/release.py check $(V) $(RELEASE_FLAGS)
	$(PY) scripts/release.py bump $(V)
	$(MAKE) sources build
	-$(MAKE) test
	$(MAKE) web-data
	$(PY) scripts/release.py prepare $(V)

publish:  ## push main + tag v$(V), GitHub Release with the font, close the milestone (ask first!)
	@test -n "$(V)" || { echo "Gebruik: make publish V=1.001"; exit 1; }
	$(PY) scripts/release.py publish $(V)

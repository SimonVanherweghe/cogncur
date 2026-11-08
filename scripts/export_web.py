"""Export the files the website needs into web/public/ (make web-data).

    python scripts/export_web.py

The website itself is the Astro project in web/; it is built and published by GitHub
Actions, which can't run FontForge. So everything that comes out of the font pipeline is
written here and committed:
  web/public/fonts/   Vtex-Regular.ttf, the original cogncur.ttf, LICENSE.txt (OFL travels with them)
  web/public/data/    tekens.json     every encoded character: group, origin (status)
                      decisions.json  decision id -> title + the characters it is about (scripts/issues.py);
                                      the website links issues to characters with it (web/scripts/fetch-issues.ts)
                      build.json      repo, font version, commit, date, counts, and the characters
                                      changed since the latest release (scripts/fontdiff.py)
                      composites.json, routes.json (make routes), cogncur_shapes.svg (stroke order)
"""
import datetime
import json
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "web" / "public"
REPO = "SimonVanherweghe/cogncur"
SITE_URL = "https://simonvanherweghe.github.io/cogncur/"
FONT = ROOT / "fonts" / "ttf" / "Vtex-Regular.ttf"
REF = ROOT / "upstream" / "fonts" / "cogncur.ttf"
COMPOSITES = ROOT / "build" / "composites.json"
ROUTES = ROOT / "build" / "routes.json"
SHAPES = ROOT / "upstream" / "webapps" / "imgen" / "cogncur_shapes.svg"
SVG = "{http://www.w3.org/2000/svg}"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


# ---------- stroke-order model
def strip_shapes(dest):
    """Upstream's stroke-order model (webapps/imgen/cogncur_shapes.svg) also holds outlines and
    comments the letter animation never uses. Write a copy that keeps only each letter's
    <g id="letter-…"> attributes and its <g class="strokes"> paths; returns the number of letters."""
    tree = ET.parse(SHAPES)
    defs = tree.getroot().find(f"{SVG}defs")
    ET.register_namespace("", SVG[1:-1])
    out = ET.Element(f"{SVG}svg", {"version": "1.1"})
    out_defs = ET.SubElement(out, f"{SVG}defs")
    n = 0
    for g in defs.iter(f"{SVG}g"):
        if not g.get("id", "").startswith("letter-"):
            continue
        letter = ET.SubElement(out_defs, f"{SVG}g", dict(g.attrib))
        strokes = g.find(f"{SVG}g[@class='strokes']")
        if strokes is not None:
            sg = ET.SubElement(letter, f"{SVG}g", {"class": "strokes"})
            for p in strokes.findall(f"{SVG}path"):
                ET.SubElement(sg, f"{SVG}path", dict(p.attrib))
        n += 1
    ET.indent(out, space=" ")
    ET.ElementTree(out).write(dest, encoding="utf-8", xml_declaration=True)
    return n


# ---------- characters
def group_of(ch):
    cat = unicodedata.category(ch)
    if cat == "Ll":
        return "lower"
    if cat in ("Lu", "Lt"):
        return "upper"
    if cat[0] == "N":
        return "digit"
    if cat[0] == "P":
        return "punct"
    if cat in ("Sk", "Lm", "Mn"):
        return "mark"
    if cat[0] in "SL":
        return "symbol"
    return None   # spaces, controls, private use: not shown


def decisions():
    """decision id -> {title, chars}, for the designer issues that list characters ("bestanden")."""
    import issues
    return {d["id"]: {"title": d["titel"], "chars": d["bestanden"]} for d in issues.DECISIONS if d.get("bestanden")}


def characters():
    cmap = TTFont(FONT).getBestCmap()
    ref = set(TTFont(REF).getBestCmap())
    comps = {int(c["unicode"], 16): c for c in json.loads(COMPOSITES.read_text())}
    drafts = {ch for d in decisions().values() for ch in d["chars"]}
    chars = []
    for cp, name in sorted(cmap.items()):
        ch = chr(cp)
        group = group_of(ch)
        if group is None:
            continue
        c = {"c": ch, "name": name, "group": group}
        comp = comps.get(cp)
        if ch in drafts:
            c["status"] = "schets"
        elif comp and comp["kind"] == "accented":
            c["status"] = "samengesteld"
        elif comp or cp not in ref:
            c["status"] = "nieuw"
        else:
            c["status"] = "origineel"
        if comp:
            c["base"] = comp.get("base")
            if comp.get("accent"):
                c["accent"] = comp["accent"]
            if comp["kind"] == "accented" and comp.get("inferred"):
                c["inferred"] = True
        chars.append(c)
    return chars


def latest_release():
    """The newest entry of web/public/data/releases.json (written by scripts/release.py), or None."""
    path = OUT / "data" / "releases.json"
    rel = json.loads(path.read_text()) if path.exists() else []
    return max(rel, key=lambda r: [int(x) for x in r["version"].split(".")], default=None)


def main():
    releases = (OUT / "data" / "releases.json").read_text() if (OUT / "data" / "releases.json").exists() else "[]\n"
    for sub in ("fonts", "data"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
        (OUT / sub).mkdir(parents=True)
    (OUT / "data" / "releases.json").write_text(releases)   # owned by release.py: keep it
    shutil.copyfile(FONT, OUT / "fonts" / "Vtex-Regular.ttf")
    shutil.copyfile(REF, OUT / "fonts" / "cogncur.ttf")
    shutil.copyfile(ROOT / "LICENSE.txt", OUT / "fonts" / "LICENSE.txt")
    shutil.copyfile(COMPOSITES, OUT / "data" / "composites.json")
    if ROUTES.exists():
        shutil.copyfile(ROUTES, OUT / "data" / "routes.json")
    else:
        print("  WARNING: build/routes.json missing (make routes); 'Woorden schrijven' won't load")
    letters = strip_shapes(OUT / "data" / "cogncur_shapes.svg")

    chars = characters()
    counts = {k: sum(1 for c in chars if c["status"] == k) for k in ("origineel", "samengesteld", "nieuw", "schets")}
    counts["total"] = len(chars)
    head = TTFont(FONT)["head"]
    commit = git("rev-parse", "--short", "HEAD")
    # uncommitted changes to the font sources; the version number (release.py bump) doesn't count
    if git("status", "--porcelain", "--", "scripts", "sources", ":!scripts/config.py"):
        commit += "+wijzigingen"
    build = {"repo": REPO, "siteUrl": SITE_URL, "version": f"{head.fontRevision:.3f}", "commit": commit,
             "date": datetime.date.today().isoformat(), "counts": counts}
    last = latest_release()
    if last:
        from fontdiff import changed
        build["changedSince"] = {"version": last["version"],
                                 "chars": changed(OUT / "versions" / last["slug"] / "fonts" / "Vtex-Regular.ttf", FONT)}
    (OUT / "data" / "tekens.json").write_text(json.dumps({"chars": chars}, ensure_ascii=False, indent=0))
    (OUT / "data" / "decisions.json").write_text(json.dumps(decisions(), ensure_ascii=False, indent=1))
    (OUT / "data" / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=1))
    print(f"web/public: {counts['total']} tekens ({counts['origineel']} origineel, "
          f"{counts['samengesteld']} samengesteld, {counts['nieuw']} nieuw, {counts['schets']} schets), "
          f"{letters} letters in het schrijfmodel, versie {build['version']} {commit}")


if __name__ == "__main__":
    main()

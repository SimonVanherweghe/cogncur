"""Build the static website in docs/ (GitHub Pages serves /docs on main).

    python scripts/build_site.py          # make site

Sources are in site/ (pages, css, js); the tools in tools/ (live, woorden, schrijven)
are copied in with the site header and a feedback button. Generated data:
  docs/data/tekens.json    every encoded character: group, origin (status), issue
  docs/data/build.json     repo, font version, commit, date, counts
plus copies of both fonts, routes.json, composites.json and the stripped stroke model.

docs/img/ and docs/ontwerper/ belong to scripts/issues.py and designer_files.py and are left alone.
"""
import datetime
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_schrijven import strip_shapes  # noqa: E402

SITE = ROOT / "site"
OUT = ROOT / "docs"
REPO = "SimonVanherweghe/cogncur-tex"
SITE_URL = "https://simonvanherweghe.github.io/cogncur-tex/"
FONT = ROOT / "fonts" / "ttf" / "Vtex-Regular.ttf"
REF = ROOT / "upstream" / "fonts" / "cogncur.ttf"
COMPOSITES = ROOT / "build" / "composites.json"
ROUTES = ROOT / "build" / "routes.json"

# Everything this script writes into docs/ (removed first, so stale files don't linger).
GENERATED = ["index.html", "tekens.html", "verbindingen.html", "proberen.html", "schrijven.html", "letters.html",
             "style.css", "nav.css", "js", "data", "fonts", ".nojekyll"]

NAV = [("index.html", "Overzicht"), ("tekens.html", "Tekens"), ("verbindingen.html", "Verbindingen"),
       ("proberen.html", "Proberen"), ("schrijven.html", "Woorden schrijven"), ("letters.html", "Letters schrijven")]

HEAD = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="nav.css">"""

# Tools copied into the site: (source, page, data-tool for js/tool-feedback.js)
TOOLS = [("live.html", "proberen.html", "live"), ("woorden.html", "schrijven.html", "woorden"),
         ("schrijven.html", "letters.html", "letters")]
LIVE_CONFIG = {"orig": "fonts/cogncur.ttf", "new": "fonts/Vtex-Regular.ttf", "manifest": "data/composites.json",
               "cacheBust": False, "canReload": False}


def nav(page):
    items = "".join(f'<li><a href="{href}"{" aria-current=\"page\"" if href == page else ""}>{label}</a></li>'
                    for href, label in NAV)
    return (f'<nav class="site-nav" aria-label="Website"><div class="in">'
            f'<a class="brand" href="index.html">Cogncur <small>voor Google Fonts</small></a>'
            f'<ul>{items}</ul>'
            f'<button type="button" class="fb-btn" id="fb-nav">💬 Feedback</button></div></nav>')


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


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


def decision_files():
    """char -> decision id, from the designer issues' "bestanden" (scripts/issues.py)."""
    import issues
    out = {}
    for d in issues.DECISIONS:
        for ch in d.get("bestanden", ""):
            out[ch] = (d["id"], d["titel"])
    return out, issues


def issue_numbers(issues):
    try:
        return issues.existing_markers()
    except Exception as e:  # offline or no gh: the site works without issue links
        print("  (no issue numbers: %s)" % e.__class__.__name__)
        return {}


def characters():
    cmap = TTFont(FONT).getBestCmap()
    ref = set(TTFont(REF).getBestCmap())
    comps = {int(c["unicode"], 16): c for c in json.loads(COMPOSITES.read_text())}
    files, issues = decision_files()
    numbers = issue_numbers(issues)
    chars = []
    for cp, name in sorted(cmap.items()):
        ch = chr(cp)
        group = group_of(ch)
        if group is None:
            continue
        c = {"c": ch, "name": name, "group": group}
        comp = comps.get(cp)
        if ch in files:
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
        if ch in files:
            did, title = files[ch]
            if did in numbers:
                n = numbers[did]
                c["issue"] = {"number": n, "title": title, "url": f"https://github.com/{REPO}/issues/{n}"}
        chars.append(c)
    return chars


def main():
    for name in GENERATED:
        p = OUT / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    (OUT / "js").mkdir(parents=True)
    (OUT / "data").mkdir()
    (OUT / "fonts").mkdir()
    (OUT / ".nojekyll").write_text("")

    # static files
    shutil.copyfile(SITE / "style.css", OUT / "style.css")
    shutil.copyfile(SITE / "nav.css", OUT / "nav.css")
    for js in (SITE / "js").glob("*.js"):
        shutil.copyfile(js, OUT / "js" / js.name)
    shutil.copyfile(FONT, OUT / "fonts" / "Vtex-Regular.ttf")
    shutil.copyfile(REF, OUT / "fonts" / "cogncur.ttf")
    shutil.copyfile(ROOT / "LICENSE.txt", OUT / "fonts" / "LICENSE.txt")   # OFL: travels with the fonts
    shutil.copyfile(COMPOSITES, OUT / "data" / "composites.json")
    if ROUTES.exists():
        shutil.copyfile(ROUTES, OUT / "data" / "routes.json")
    else:
        print("  WARNING: build/routes.json missing (make routes); 'Woorden schrijven' won't load")
    strip_shapes(OUT / "data" / "cogncur_shapes.svg")

    # data
    chars = characters()
    counts = {k: sum(1 for c in chars if c["status"] == k) for k in ("origineel", "samengesteld", "nieuw", "schets")}
    counts["total"] = len(chars)
    head = TTFont(FONT)["head"]
    commit = git("rev-parse", "--short", "HEAD")
    if git("status", "--porcelain", "--", "scripts", "sources", "site", "tools"):
        commit += "+wijzigingen"
    build = {"repo": REPO, "siteUrl": SITE_URL, "version": f"{head.fontRevision:.3f}", "commit": commit,
             "date": datetime.date.today().isoformat(), "counts": counts}
    (OUT / "data" / "tekens.json").write_text(json.dumps({"chars": chars}, ensure_ascii=False, separators=(",", ":")))
    (OUT / "data" / "build.json").write_text(json.dumps(build, ensure_ascii=False, indent=1))

    # pages
    for src in sorted(SITE.glob("*.html")):
        html = src.read_text(encoding="utf-8")
        assert "<!--HEAD-->" in html and "<!--NAV-->" in html, src
        html = html.replace("<!--HEAD-->", HEAD).replace("<!--NAV-->", nav(src.name))
        (OUT / src.name).write_text(html, encoding="utf-8")

    # tools
    for src, page, tool in TOOLS:
        html = (ROOT / "tools" / src).read_text(encoding="utf-8")
        hook = f'<script type="module" src="js/tool-feedback.js" data-tool="{tool}"></script>\n'
        if re.search(r"<!doctype html>", html, re.I):        # full document (live.html)
            cfg = f"<script>window.LIVE_CONFIG = {json.dumps(LIVE_CONFIG)};</script>\n"
            html = html.replace("</head>", HEAD + "\n</head>", 1)
            html = re.sub(r"<body>\s*", lambda m: m.group(0) + nav(page) + "\n", html, count=1)
            i = html.index("<script>")
            html = html[:i] + cfg + html[i:]
            html = html.replace("</body>", hook + "</body>", 1)
        else:                                                 # artifact fragment (woorden, schrijven)
            html = ('<!doctype html>\n<html lang="nl">\n<head>\n<meta charset="utf-8">\n'
                    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                    f"{HEAD}\n</head>\n<body>\n{nav(page)}\n"
                    + re.sub(r'<meta charset="utf-8">\s*', "", html, count=1) + "\n" + hook + "</body>\n</html>\n")
        (OUT / page).write_text(html, encoding="utf-8")

    print(f"site in {OUT.relative_to(ROOT)}/: {counts['total']} tekens "
          f"({counts['origineel']} origineel, {counts['samengesteld']} samengesteld, "
          f"{counts['nieuw']} nieuw, {counts['schets']} schets), versie {build['version']} {commit}")


if __name__ == "__main__":
    main()

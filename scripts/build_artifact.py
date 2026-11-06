"""Package tools/live.html as a Claude artifact in build/artifact/.

    python scripts/build_artifact.py

The artifact host wraps the page in its own <html>/<head>/<body>, so those
wrappers are stripped. LIVE_CONFIG points the page at files published next to
it: both fonts, the new-letter manifest and the original OFL license (which
must accompany the original Cogncur font).
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "artifact"

FILES = {
    "fonts/cogncur.ttf": ROOT / "upstream" / "fonts" / "cogncur.ttf",
    "fonts/vtex.ttf": ROOT / "fonts" / "ttf" / "Vtex-Regular.ttf",
    "composites.json": ROOT / "build" / "composites.json",
    "LICENSE.txt": ROOT / "LICENSE.txt",
}

CONFIG = {
    "orig": "fonts/cogncur.ttf",
    "new": "fonts/vtex.ttf",
    "manifest": "composites.json",
    "cacheBust": False,
    "canReload": False,
}


def main():
    html = (ROOT / "tools" / "live.html").read_text(encoding="utf-8")
    for pat in (r"<!doctype html>\s*", r"<html[^>]*>\s*", r"</html>\s*", r"<head>\s*", r"</head>\s*",
                r"<body>\s*", r"</body>\s*", r'<meta charset="utf-8">\s*', r'<meta name="viewport"[^>]*>\s*'):
        html, n = re.subn(pat, "", html, flags=re.I)
        assert n == 1, f"expected exactly one match for {pat!r}, got {n}"
    cfg = f"<script>window.LIVE_CONFIG = {json.dumps(CONFIG)};</script>\n"
    i = html.index("<script>")
    html = html[:i] + cfg + html[i:]
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "fonts").mkdir(parents=True)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    for dest, src in FILES.items():
        shutil.copyfile(src, OUT / dest)
    print("artifact files in", OUT)
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(OUT)}  {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

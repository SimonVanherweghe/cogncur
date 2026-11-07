"""Package tools/schrijven.html for the private artifact (build/schrijven/).

The page reads upstream's stroke-order model (webapps/imgen/cogncur_shapes.svg). That file also
holds outlines and comments the page never uses, so this writes a stripped copy that keeps only
each letter's <g id="letter-…"> attributes and its <g class="strokes"> paths.
"""
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "upstream/webapps/imgen/cogncur_shapes.svg"
OUT = ROOT / "build/schrijven"
SVG = "{http://www.w3.org/2000/svg}"


def strip_shapes(dest):
    """Write the stripped stroke model to dest; returns the number of letters."""
    tree = ET.parse(SRC)
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = strip_shapes(OUT / "cogncur_shapes.svg")
    shutil.copyfile(ROOT / "tools/schrijven.html", OUT / "schrijven.html")
    size = (OUT / "cogncur_shapes.svg").stat().st_size
    print(f"{n} letters, cogncur_shapes.svg {size // 1024} KB -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()

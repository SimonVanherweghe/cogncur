"""Which characters look different between two font files: outline (components decomposed)
or advance width. Used by export_web.py (changes since the latest release) and release.py.

    python scripts/fontdiff.py old.ttf new.ttf
"""
import hashlib
import sys

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont


def signatures(path):
    """character -> short hash of its default glyph's outline + advance width."""
    font = TTFont(path)
    glyphs = font.getGlyphSet()
    hmtx = font["hmtx"]
    out = {}
    for cp, name in font.getBestCmap().items():
        pen = DecomposingRecordingPen(glyphs)
        glyphs[name].draw(pen)
        data = repr((hmtx[name][0], pen.value)).encode()
        out[chr(cp)] = hashlib.sha1(data).hexdigest()[:12]
    return out


def changed(old_path, new_path):
    """Characters that are new or look different in new_path, in code point order."""
    old, new = signatures(old_path), signatures(new_path)
    return sorted((c for c, h in new.items() if old.get(c) != h), key=ord)


if __name__ == "__main__":
    print(" ".join(changed(sys.argv[1], sys.argv[2])) or "(geen verschillen)")

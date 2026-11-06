"""Find where a letter sits inside an entry-stroke ligature by matching ink.

The ligature (e.g. csh_l) is entry stroke + letter merged into one outline;
the designer sometimes nudged the letter, so we search the horizontal offset
at which the letter's ink is best covered by the ligature's ink."""
from functools import lru_cache

import numpy as np
from fontTools.pens.freetypePen import FreeTypePen
from fontTools.pens.transformPen import TransformPen

ORIGIN_X, ORIGIN_Y, W, H = 1600, 1000, 4000, 3200


def _raster(font, name, scale):
    pen = FreeTypePen(font)
    m = (scale, 0, 0, scale, ORIGIN_X * scale, ORIGIN_Y * scale)
    font[name].draw(TransformPen(pen, m))
    return pen.array(width=int(W * scale), height=int(H * scale), contain=False) > 0.5


def letter_offset(font, ligature, letter, guess):
    """Return (dx, coverage): dx in font units, coverage = share of the letter's
    ink inside the ligature's ink at that offset (1.0 = perfect)."""
    best = (None, -1.0)
    for scale, lo, hi, step in ((0.25, -900, 400, 4), (1.0, None, None, 1)):
        L = _raster(font, ligature, scale)
        B = _raster(font, letter, scale)
        ink = B.sum()
        if lo is None:
            lo, hi = best[0] - 6, best[0] + 6
        for dx in range(lo, hi + 1, step):
            s = int(round(dx * scale))
            shifted = np.zeros_like(B)
            if s >= 0:
                shifted[:, s:] = B[:, : B.shape[1] - s]
            else:
                shifted[:, :s] = B[:, -s:]
            cov = (shifted & L).sum() / ink
            # prefer the offset closest to the guess when coverage ties
            if cov > best[1] + 1e-9 or (abs(cov - best[1]) < 1e-9 and abs(dx - guess) < abs(best[0] - guess)):
                best = (dx, cov)
    return best

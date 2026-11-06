"""Infer a 'topmid' accent anchor for letters the designer never accented.

Rule: take the ink of the glyph in the top band (upper 30% of x-height for
lowercase, of cap height for capitals), find the x-centre of that band, and
express it at the anchor height. Glyphs are slanted 7.5 deg, so the band
centre is shifted along the slant to the anchor's y."""
import math

from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import DecomposingRecordingPen

TAN = math.tan(math.radians(7.5))
XH, CAP = 682, 1364


class _Sampler(BasePen):
    """Collect points densely along the outline."""
    def __init__(self, glyphset=None):
        super().__init__(glyphset)
        self.pts = []
        self._last = None

    def _moveTo(self, p):
        self._last = p
        self.pts.append(p)

    def _lineTo(self, p):
        (x0, y0), (x1, y1) = self._last, p
        for i in range(1, 21):
            t = i / 20
            self.pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        self._last = p

    def _qCurveToOne(self, p1, p2):
        (x0, y0) = self._last
        for i in range(1, 21):
            t = i / 20
            a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
            self.pts.append((a * x0 + b * p1[0] + c * p2[0], a * y0 + b * p1[1] + c * p2[1]))
        self._last = p2

    def _curveToOne(self, p1, p2, p3):
        (x0, y0) = self._last
        for i in range(1, 21):
            t = i / 20
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
            self.pts.append((a * x0 + b * p1[0] + c * p2[0] + d * p3[0], a * y0 + b * p1[1] + c * p2[1] + d * p3[1]))
        self._last = p3


def infer_topmid(glyph, font, capital):
    height = CAP if capital else XH
    anchor_y = 1330 if capital else 648
    s = _Sampler(font)
    glyph.draw(s)
    lo = height * 0.7
    band = [(x - (y - anchor_y) * TAN) for x, y in s.pts if lo <= y <= height + 5]
    if not band:
        return None
    return round((min(band) + max(band)) / 2), anchor_y

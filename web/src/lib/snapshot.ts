// An SVG on the page as a canvas (for the feedback image of the writing animations).
// A serialized SVG loses the page's stylesheet, so the computed styles that matter are inlined.
import { PAPER, drawCaption } from './sheet';

const PROPS = ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin',
  'opacity', 'fill-opacity', 'stroke-opacity', 'display', 'visibility', 'font-size', 'font-family'];

export async function svgToCanvas(svg: SVGSVGElement, { scale = 2, caption = '' } = {}): Promise<HTMLCanvasElement> {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const src = [svg, ...svg.querySelectorAll('*')];
  const dst = [clone, ...clone.querySelectorAll('*')];
  src.forEach((el, i) => {
    const cs = getComputedStyle(el);
    dst[i].setAttribute('style', PROPS.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(';'));
  });
  const box = svg.getBoundingClientRect();
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', String(box.width));
  clone.setAttribute('height', String(box.height));
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: 'image/svg+xml' }));
  try {
    const img = new Image();
    await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = url; });
    const capH = caption ? 28 : 0;
    const cv = document.createElement('canvas');
    cv.width = Math.ceil(box.width * scale);
    cv.height = Math.ceil((box.height + capH) * scale);
    const ctx = cv.getContext('2d')!;
    ctx.scale(scale, scale);
    ctx.fillStyle = PAPER;
    ctx.fillRect(0, 0, box.width, box.height + capH);
    ctx.drawImage(img, 0, 0, box.width, box.height);
    if (caption) drawCaption(ctx, caption, box.width, box.height + 18);
    return cv;
  } finally {
    URL.revokeObjectURL(url);
  }
}

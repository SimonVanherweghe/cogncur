// Playback for the writing animations: ▶/❚❚ button, restart, timeline slider, speed and loop.

export interface PlayerControls {
  play: HTMLButtonElement;
  restart: HTMLButtonElement;
  scrub: HTMLInputElement;
  time: HTMLElement;
}

export interface Player {
  t: number;
  speed: number;
  loop: boolean;
  readonly playing: boolean;
  setPlaying(on: boolean): void;
  /** New scene: start at 0 and play, or (reduced motion / autoplay off) show the finished line. */
  reset(total: number, autoplay?: boolean): void;
  draw(): void;
}

const fmt = (s: number) => s.toFixed(1).replace('.', ',');
const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export function createPlayer(c: PlayerControls, render: (t: number) => void): Player {
  let total = 0, playing = false, last = 0;
  const p: Player = {
    t: 0, speed: 1, loop: false,
    get playing() { return playing; },
    setPlaying(on) {
      playing = on;
      c.play.textContent = on ? '❚❚ Pauze' : '▶ Afspelen';
      c.play.setAttribute('aria-pressed', String(on));
      if (on) {
        if (p.t >= total) p.t = 0;
        last = performance.now();
        requestAnimationFrame(tick);
      }
    },
    reset(newTotal, autoplay = true) {
      p.setPlaying(false);
      total = newTotal;
      p.t = reduceMotion() || !autoplay ? total : 0;
      p.draw();
      if (autoplay && !reduceMotion()) p.setPlaying(true);
    },
    draw() {
      render(p.t);
      c.scrub.value = String(total ? Math.round((1000 * p.t) / total) : 0);
      c.time.textContent = `${fmt(p.t)} / ${fmt(total)} s`;
    },
  };
  function tick(now: number) {
    if (!playing) return;
    p.t += ((now - last) / 1000) * p.speed;
    last = now;
    if (p.t >= total) {
      if (p.loop) p.t = 0;
      else { p.t = total; p.setPlaying(false); }
    }
    p.draw();
    if (playing) requestAnimationFrame(tick);
  }
  c.play.addEventListener('click', () => p.setPlaying(!playing));
  c.restart.addEventListener('click', () => { p.t = 0; p.draw(); p.setPlaying(true); });
  c.scrub.addEventListener('input', () => { p.setPlaying(false); p.t = (total * +c.scrub.value) / 1000; p.draw(); });
  return p;
}

/** A row of buttons where one is pressed (aria-pressed); calls onPick with its data-v. */
export function segmented(root: HTMLElement, onPick: (v: string) => void): void {
  root.addEventListener('click', (e) => {
    const b = (e.target as HTMLElement).closest<HTMLButtonElement>('button');
    if (!b) return;
    for (const x of root.querySelectorAll('button')) x.setAttribute('aria-pressed', String(x === b));
    onPick(b.dataset.v!);
  });
}

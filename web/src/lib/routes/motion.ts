// Motion profile of the pen: accelerate from each stop, cruise, brake into the next stop.

export const SPEED = 900;     // font units per second at 1×
export const ACCEL_T = 0.22;  // seconds to reach full speed from a stop

export interface Span { L: number; a: number; vp: number; t1: number; d1: number; cruise: number; T: number }

/** Timing of one stretch of length L between two stops. */
export function spanTime(L: number): Span {
  const a = SPEED / ACCEL_T, vp = Math.min(SPEED, Math.sqrt(L * a));
  const t1 = vp / a, d1 = (vp * t1) / 2, cruise = Math.max(0, (L - 2 * d1) / vp);
  return { L, a, vp, t1, d1, cruise, T: 2 * t1 + cruise };
}

/** Distance travelled after t seconds. */
export function spanPos(sp: Span, t: number): number {
  if (t <= 0) return 0;
  if (t >= sp.T) return sp.L;
  if (t < sp.t1) return (sp.a * t * t) / 2;
  if (t < sp.t1 + sp.cruise) return sp.d1 + sp.vp * (t - sp.t1);
  const r = sp.T - t;
  return sp.L - (sp.a * r * r) / 2;
}

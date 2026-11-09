/** Number formatting shared by every view model: short, and never misleading at the extremes. */

export function fmt(p: number): string {
  if (p === 0) return "0";
  return Math.abs(p) >= 100 || Math.abs(p) < 0.01 ? p.toExponential(1) : p.toPrecision(2);
}

/** A threshold for display: +Infinity (no limit) reads as ∞. */
export function fmtThreshold(p: number): string {
  return Number.isFinite(p) ? fmt(p) : "∞";
}

/**
 * Eqs. 1-3 of Correa et al. 2011 for R = [pLo, pHi] - TypeScript twin of
 * pipeline/src/topospine/core/extremum_graph.py (both tested on the same worked example).
 *
 *   extremum u kept  <=>  pLo <= P(u)
 *   saddle s kept    <=>  pLo <= P(s) <= pHi
 *   arc (s, u) kept  <=>  P(s) <= pHi  and  P*(s) >= pLo
 */

import { EXTREMUM, Saturation, SpineData } from "./types";

export interface Visibility {
  pLo: number;
  pHi: number;
  saturation: Saturation;
  node: Uint8Array; // 1 = kept
  arc: Uint8Array;
}

export function checkRange(pLo: number, pHi: number): void {
  if (!(pLo >= 0 && pLo <= pHi)) throw new RangeError(`need 0 <= pLo <= pHi, got [${pLo}, ${pHi}]`);
}

export function filterGraph(d: SpineData, pLo: number, pHi: number, saturation: Saturation = "paper"): Visibility {
  checkRange(pLo, pHi);
  const P = d.persistence;
  const Ps = saturation === "paper" ? d.saturated : d.saturatedCancel;
  const node = new Uint8Array(d.numNodes);
  for (let i = 0; i < d.numNodes; i++) {
    node[i] = d.kind[i] === EXTREMUM ? +(P[i] >= pLo) : +(P[i] >= pLo && P[i] <= pHi);
  }
  const arc = new Uint8Array(d.numArcs);
  for (let a = 0; a < d.numArcs; a++) {
    const s = d.arcSaddle[a];
    arc[a] = +(P[s] <= pHi && Ps[s] >= pLo);
  }
  return { pLo, pHi, saturation, node, arc };
}

/** Surviving extremum each node belongs to at noise threshold pLo (saddles map to themselves). */
export function representatives(d: SpineData, pLo: number): Int32Array {
  const rep = new Int32Array(d.numNodes);
  for (let i = 0; i < d.numNodes; i++) {
    let r = i;
    let guard = d.numNodes;
    while (d.mergedInto[r] >= 0 && d.persistence[r] < pLo) {
      r = d.mergedInto[r];
      if (--guard < 0) throw new Error("cycle in mergedInto");
    }
    rep[i] = r;
  }
  return rep;
}

function sorted(xs: Iterable<number>): Float64Array {
  return Float64Array.from(xs).sort();
}

/** First index with xs[i] >= t (xs ascending). */
function lowerBound(xs: Float64Array, t: number): number {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < t) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/** First index with xs[i] > t. */
function upperBound(xs: Float64Array, t: number): number {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= t) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/** Number of extrema kept for each noise threshold (the paper's blue curve). */
export function extremaCurve(d: SpineData, thresholds: ArrayLike<number>): Int32Array {
  const p = sorted(Array.from({ length: d.numRegions }, (_, i) => d.persistence[i]));
  return Int32Array.from(thresholds, (t) => p.length - lowerBound(p, t));
}

/** Number of arcs kept for each variation threshold at pLo = 0 (the red curve). */
export function arcCurve(d: SpineData, thresholds: ArrayLike<number>): Int32Array {
  const p = sorted(Array.from(d.arcSaddle, (s) => d.persistence[s]));
  return Int32Array.from(thresholds, (t) => upperBound(p, t));
}

/** Largest finite persistence: the natural end of the slider range. */
export function maxFinitePersistence(d: SpineData): number {
  let m = 0;
  for (const p of d.persistence) if (Number.isFinite(p) && p > m) m = p;
  return m;
}

/**
 * Starting noise threshold: the middle of the widest gap between consecutive extremum
 * persistences, measured as a ratio (a long plateau of the blue curve on a log axis).
 * Noise and features usually differ by an order of magnitude, so this lands between them.
 * Falls back to 1 % of the largest persistence when no clear gap (ratio < 3) exists.
 */
export function suggestNoiseThreshold(d: SpineData, minRatio = 3): number {
  const p = sorted(Array.from({ length: d.numRegions }, (_, i) => d.persistence[i]).filter((x) => Number.isFinite(x) && x > 0));
  const top = p.length ? p[p.length - 1] : 0;
  let best = 0, at = -1;
  for (let i = 0; i + 1 < p.length; i++) {
    const r = p[i + 1] / p[i];
    if (r > best) { best = r; at = i; }
  }
  if (at < 0 || best < minRatio) return 0.01 * top;
  return Math.sqrt(p[at] * p[at + 1]);
}

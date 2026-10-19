/**
 * Region histograms -> link radii (paper Sec. 4.2):
 *   r_us(c, p) = |{x in D(u) : c < f(x) < f(p)}|
 * Merged regions (after simplification) are the sum of their members' histograms.
 * Lookups interpolate linearly inside a bin, exactly like region_stats.py.
 */

import { SpineData } from "./types";

export class MergedRegions {
  /** For each representative extremum r: suffix sums, above[r*(B+1) + k] = count in bins >= k. */
  private readonly above: Float64Array;
  readonly sizes: Float64Array;

  constructor(
    private readonly edges: Float64Array,
    counts: ArrayLike<number>,
    numRegions: number,
    rep: ArrayLike<number>,
  ) {
    const B = edges.length - 1;
    const merged = new Float64Array(numRegions * B);
    for (let r = 0; r < numRegions; r++) {
      const t = rep[r];
      for (let k = 0; k < B; k++) merged[t * B + k] += counts[r * B + k];
    }
    this.above = new Float64Array(numRegions * (B + 1));
    this.sizes = new Float64Array(numRegions);
    for (let r = 0; r < numRegions; r++) {
      const o = r * (B + 1);
      for (let k = B - 1; k >= 0; k--) this.above[o + k] = this.above[o + k + 1] + merged[r * B + k];
      this.sizes[r] = this.above[o];
    }
  }

  static fromData(d: SpineData, rep: ArrayLike<number>): MergedRegions {
    return new MergedRegions(d.binEdges, d.regionCounts, d.numRegions, rep);
  }

  /** Samples of region r with f >= c (interpolated inside the bin containing c). */
  countAtOrAbove(r: number, c: number): number {
    const e = this.edges;
    const B = e.length - 1;
    const o = r * (B + 1);
    if (c <= e[0]) return this.above[o];
    if (c >= e[B]) return 0;
    let lo = 0, hi = B; // find k with e[k] <= c < e[k+1]
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (e[mid] <= c) lo = mid; else hi = mid;
    }
    const inBin = this.above[o + lo] - this.above[o + lo + 1];
    const frac = (e[lo + 1] - c) / (e[lo + 1] - e[lo]);
    return this.above[o + lo + 1] + frac * inBin;
  }

  /** r_us: samples of region r with value between c0 and c1 (order-agnostic). */
  countBetween(r: number, c0: number, c1: number): number {
    const lo = Math.min(c0, c1), hi = Math.max(c0, c1);
    return this.countAtOrAbove(r, lo) - this.countAtOrAbove(r, hi);
  }

  get numBins(): number {
    return this.edges.length - 1;
  }
}


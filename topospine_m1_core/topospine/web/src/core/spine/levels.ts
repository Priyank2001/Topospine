/**
 * Which isovalues get a pseudo-contour (paper Sec. 4.4): "all isovalues corresponding to
 * the critical points ... [with] a minimum difference in isovalue that can be set by the user".
 *
 * Works in height g (= f for maxima, -f for minima) so "lower level = bigger shape" holds
 * for both extremum types. Levels at or above the highest drawn extremum would have zero
 * size everywhere and are dropped.
 */

export interface LevelOptions {
  /** Evenly spaced extra isovalues between the lowest candidate and the top (the paper's
   *  optional pseudo-contours, Sec. 4.1); they show nesting even when few critical values exist. */
  extraLevels?: number;
  /** Minimum gap between kept levels, as a fraction of the height range. */
  minGapFraction: number;
  /** Hard cap; extra levels are thinned evenly. Each level costs two GPU passes. */
  maxLevels: number;
}

export const DEFAULT_LEVELS: LevelOptions = { minGapFraction: 0.03, maxLevels: 24, extraLevels: 0 };

export function chooseLevels(candidates: ArrayLike<number>, gTop: number, gRange: number, opts = DEFAULT_LEVELS): Float64Array {
  const below = Array.from(candidates).filter((g) => g < gTop);
  const extra = opts.extraLevels ?? 0;
  if (extra > 0 && below.length) {
    const lo = Math.min(...below);
    for (let i = 1; i <= extra; i++) below.push(lo + ((gTop - lo) * i) / (extra + 1));
  }
  const sorted = Float64Array.from(below).sort();
  const gap = opts.minGapFraction * gRange;
  const kept: number[] = [];
  for (const g of sorted) if (kept.length === 0 || g - kept[kept.length - 1] >= gap) kept.push(g);
  if (kept.length <= opts.maxLevels) return Float64Array.from(kept);
  const thinned = new Float64Array(opts.maxLevels);
  for (let i = 0; i < opts.maxLevels; i++) {
    thinned[i] = kept[Math.round((i * (kept.length - 1)) / (opts.maxLevels - 1))];
  }
  return thinned;
}

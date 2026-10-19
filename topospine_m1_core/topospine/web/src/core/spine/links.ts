/**
 * Canonical topological links (paper Sec. 4.1-4.2) as tapered-capsule pieces per level.
 *
 * For a drawn link from extremum u to saddle s and an isovalue c, the paper's contour is the
 * union of circles centred on the u-s segment, with height g interpolated linearly from
 * g(u) at u to g(s) at s, and radius
 *     r(c, p) = | { x in D(u) : c < g(x) < g(p) } |          (only where g(p) >= c)
 * D(u) is u's region after simplification (merged histograms). So:
 *   - c >= g(s): the shape stops where g(p) = c, radius 0 there: a closed blob around u;
 *   - c == g(s): radius 0 exactly at s: the figure-eight "critical contour";
 *   - c <  g(s): radius > 0 at s: the shapes from u and from v overlap and merge.
 * We sample K knots along the covered part and join consecutive circles with tapered
 * capsules; their union approximates the Minkowski sum.
 *
 * Contour nesting (paper Sec. 4.3): for c1 < c2 every radius at c1 is >= the radius at c2,
 * because the counted interval only grows. Tested as a property.
 *
 * Radius encoding: the paper's radius is proportional to the counted volume ("linear").
 * "sqrt" makes the AREA of a circle proportional to volume instead, which keeps small
 * regions visible next to large ones (docs/DEVIATIONS.md #11).
 */

import { MergedRegions } from "../regionStats";
import { SpineData, height } from "../types";

export type RadiusMode = "linear" | "sqrt";

export interface LinkInput {
  /** Extremum and saddle node ids, parallel arrays. */
  linkExtremum: ArrayLike<number>;
  linkSaddle: ArrayLike<number>;
  /** Layout position (x, y) of a node id. */
  pos: (node: number) => [number, number];
}

export interface SpineGeometry {
  /** Ascending heights g; level i is drawn before level i+1 (bigger shapes first). */
  levels: Float64Array;
  /** Per level: pieces as [ax, ay, ra, bx, by, rb] * count. */
  pieces: Float32Array[];
  /** World units per unit of g(count); reported so the UI can show a scale. */
  radiusScale: number;
}

export interface LinkOptions {
  knots: number; // pieces per link per level
  mode: RadiusMode;
  /** Largest radius as a fraction of the median link length. */
  glyphScale: number;
}

export const DEFAULT_LINKS: LinkOptions = { knots: 8, mode: "sqrt", glyphScale: 0.6 };

/** Radius in "count units" before the global scale is applied. */
export function shapeRadius(d: SpineData, regions: MergedRegions, u: number, c: number, gp: number, mode: RadiusMode): number {
  if (gp <= c) return 0;
  // histograms are over f; convert the g-interval back to f (order doesn't matter)
  const count = regions.countBetween(u, d.sign * c, d.sign * gp);
  const v = Math.max(count, 0);
  return mode === "sqrt" ? Math.sqrt(v) : v;
}

export function buildSpineGeometry(
  d: SpineData,
  regions: MergedRegions,
  links: LinkInput,
  levels: Float64Array,
  opts: LinkOptions = DEFAULT_LINKS,
): SpineGeometry {
  const L = links.linkExtremum.length;
  const K = Math.max(1, Math.floor(opts.knots));

  // global scale: the biggest unscaled radius maps to glyphScale * median link length
  const lengths: number[] = [];
  let biggest = 0;
  for (let l = 0; l < L; l++) {
    const u = links.linkExtremum[l], s = links.linkSaddle[l];
    const [ux, uy] = links.pos(u), [sx, sy] = links.pos(s);
    lengths.push(Math.hypot(sx - ux, sy - uy));
    if (levels.length) biggest = Math.max(biggest, shapeRadius(d, regions, u, levels[0], height(d, u), opts.mode));
  }
  lengths.sort((a, b) => a - b);
  const median = lengths.length ? lengths[lengths.length >> 1] || 1 : 1;
  const scale = biggest > 0 ? (opts.glyphScale * median) / biggest : 0;

  const pieces: Float32Array[] = [];
  for (const c of levels) {
    const out: number[] = [];
    for (let l = 0; l < L; l++) {
      const u = links.linkExtremum[l], s = links.linkSaddle[l];
      const gu = height(d, u), gs = height(d, s);
      if (c >= gu) continue;
      const tEnd = c >= gs ? (gu - c) / Math.max(gu - gs, 1e-12) : 1; // where g(p) reaches c
      const [ux, uy] = links.pos(u), [sx, sy] = links.pos(s);
      let px = ux, py = uy;
      let pr = scale * shapeRadius(d, regions, u, c, gu, opts.mode);
      for (let k = 1; k <= K; k++) {
        const t = (tEnd * k) / K;
        const qx = ux + t * (sx - ux), qy = uy + t * (sy - uy);
        const gq = gu + t * (gs - gu);
        const qr = scale * shapeRadius(d, regions, u, c, gq, opts.mode);
        if (pr > 0 || qr > 0) out.push(px, py, pr, qx, qy, qr);
        px = qx; py = qy; pr = qr;
      }
    }
    pieces.push(Float32Array.from(out));
  }
  return { levels, pieces, radiusScale: scale };
}

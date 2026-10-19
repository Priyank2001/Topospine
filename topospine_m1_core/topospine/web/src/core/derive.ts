/**
 * Derived-data pipeline: SpineParams -> everything the spine view draws.
 *
 *   pLo, pHi, saturation --filterGraph--> visibility --+
 *   pLo -----------------representatives--> rep -------+--> displayGraph --> layout --+
 *   rep ------------------------------------> merged regions ----------------------+  |
 *   displayGraph, minLevelGap, maxLevels --------------> levels -------------------+--+--> spine geometry
 *   radiusMode, glyphScale -------------------------------------------------------+
 *
 * Each stage is memoised on the identity of its inputs, so e.g. moving pHi never recomputes
 * representatives or merged histograms, and changing glyphScale never re-runs the layout.
 * The layout warm-starts from the previous positions of nodes that stay visible, so the
 * spine doesn't jump when a slider moves.
 */

import { DisplayGraph, buildDisplayGraph } from "./displayGraph";
import { pca2 } from "./layout/pca";
import { DEFAULT_STRESS, pairwiseDistances, stressLayout } from "./layout/stress";
import { MergedRegions } from "./regionStats";
import { chooseLevels } from "./spine/levels";
import { SpineGeometry, buildSpineGeometry } from "./spine/links";
import { SpineParams } from "./spineState";
import { Visibility, filterGraph, representatives } from "./thresholds";
import { SpineData, height } from "./types";

export interface SpineFrame {
  visibility: Visibility;
  rep: Int32Array;
  display: DisplayGraph;
  /** node id -> layout position, for drawn nodes. */
  layout: Map<number, [number, number]>;
  geometry: SpineGeometry;
  timings: { layoutMs: number; geometryMs: number; layoutIterations: number; layoutSkipped: boolean };
}

/** Memoise a function of a few inputs by identity (Object.is on each argument). */
export function memo<A extends unknown[], R>(fn: (...args: A) => R): ((...args: A) => R) & { calls: () => number } {
  let lastArgs: A | undefined;
  let last: R;
  let calls = 0;
  const wrapped = (...args: A): R => {
    if (!lastArgs || args.length !== lastArgs.length || args.some((a, i) => !Object.is(a, lastArgs![i]))) {
      calls++;
      last = fn(...args);
      lastArgs = args;
    }
    return last;
  };
  return Object.assign(wrapped, { calls: () => calls });
}

export class SpinePipeline {
  /** PCA of every critical point, computed once: the shared frame for all thresholds. */
  private readonly pcaAll: Float64Array;
  private previous = new Map<number, [number, number]>();
  private lastLayoutStats = { layoutMs: 0, layoutIterations: 0, layoutSkipped: false };
  private readonly gRange: number;

  readonly visibility = memo((pLo: number, pHi: number, sat: SpineParams["saturation"]) => filterGraph(this.d, pLo, pHi, sat));
  readonly rep = memo((pLo: number) => representatives(this.d, pLo));
  readonly display = memo((vis: Visibility, rep: Int32Array, dedupe: boolean) => buildDisplayGraph(this.d, vis, rep, { dedupe }));
  readonly merged = memo((rep: Int32Array) => MergedRegions.fromData(this.d, rep));
  readonly layout = memo((g: DisplayGraph) => this.computeLayout(g));
  readonly levels = memo((g: DisplayGraph, gap: number, maxLevels: number, extra: number) => this.computeLevels(g, gap, maxLevels, extra));
  readonly geometry = memo(
    (g: DisplayGraph, layout: Map<number, [number, number]>, regions: MergedRegions, levels: Float64Array,
     mode: SpineParams["radiusMode"], glyphScale: number) =>
      buildSpineGeometry(this.d, regions, {
        linkExtremum: g.linkExtremum,
        linkSaddle: g.linkSaddle,
        pos: (n) => layout.get(n)!,
      }, levels, { knots: 8, mode, glyphScale }),
  );

  constructor(private readonly d: SpineData) {
    this.pcaAll = pca2(d.position, d.numNodes, d.posDim);
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < d.numNodes; i++) {
      const g = height(d, i);
      lo = Math.min(lo, g);
      hi = Math.max(hi, g);
    }
    this.gRange = Number.isFinite(hi - lo) && hi > lo ? hi - lo : 1;
  }

  frame(p: SpineParams): SpineFrame {
    const visibility = this.visibility(p.pLo, p.pHi, p.saturation);
    const rep = this.rep(p.pLo);
    const display = this.display(visibility, rep, p.dedupe);
    const layout = this.layout(display);
    const regions = this.merged(rep);
    const levels = this.levels(display, p.minLevelGap, p.maxLevels, p.extraLevels);
    const t0 = performance.now();
    const geometry = this.geometry(display, layout, regions, levels, p.radiusMode, p.glyphScale);
    const geometryMs = performance.now() - t0;
    return { visibility, rep, display, layout, geometry, timings: { ...this.lastLayoutStats, geometryMs } };
  }

  private computeLayout(g: DisplayGraph): Map<number, [number, number]> {
    const t0 = performance.now();
    const ids = g.nodes;
    const n = ids.length;
    const index = new Map<number, number>();
    ids.forEach((id, i) => index.set(id, i));
    const init = new Float64Array(n * 2);
    ids.forEach((id, i) => {
      const prev = this.previous.get(id);
      init[2 * i] = prev ? prev[0] : this.pcaAll[2 * id];
      init[2 * i + 1] = prev ? prev[1] : this.pcaAll[2 * id + 1];
    });
    const edges: [number, number][] = [];
    for (let l = 0; l < g.linkExtremum.length; l++) {
      edges.push([index.get(g.linkExtremum[l])!, index.get(g.linkSaddle[l])!]);
    }
    const target = pairwiseDistances(this.d.position, ids, this.d.posDim);
    const res = stressLayout({ n, target, edges, init }, DEFAULT_STRESS);
    const out = new Map<number, [number, number]>();
    ids.forEach((id, i) => out.set(id, [res.position[2 * i], res.position[2 * i + 1]]));
    this.previous = new Map([...this.previous, ...out]); // remember positions of nodes that disappear too
    this.lastLayoutStats = { layoutMs: performance.now() - t0, layoutIterations: res.iterations, layoutSkipped: n > DEFAULT_STRESS.maxNodes };
    return out;
  }

  private computeLevels(g: DisplayGraph, gap: number, maxLevels: number, extra: number): Float64Array {
    // candidates: heights of ALL critical points (paper Sec. 4.4), below the highest drawn extremum
    let top = -Infinity;
    for (let i = 0; i < g.numExtrema; i++) top = Math.max(top, height(this.d, g.nodes[i]));
    const candidates = Array.from({ length: this.d.numNodes }, (_, i) => height(this.d, i));
    return chooseLevels(candidates, top, this.gRange, { minGapFraction: gap, maxLevels, extraLevels: extra });
  }
}

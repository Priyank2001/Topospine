/**
 * From the thresholded extremum graph G_R to the graph the spine actually draws.
 *
 * Every visible arc (s, m) is redirected to m's representative at pLo (the surviving
 * extremum m merged into). Then, per saddle with visible arcs:
 *   - both ends map to the same extremum -> the connection collapsed inside one feature;
 *     dropped ("collapsed" mode, docs/M2_NOTES.md);
 *   - otherwise the saddle becomes a connector between two surviving extrema.
 * With `dedupe`, only the highest saddle per pair of extrema is kept: that is where the two
 * features actually join; lower parallel saddles are the "multiple connections" the paper
 * attributes to noise (Fig. 6a).
 *
 * Worked example (f = 1 5 3 4 2 9 6 8 0) at R = [1.5, inf]: s1's arcs both map to A and are
 * dropped; s2's arcs map to A and C, so the drawn spine is A - s2 - C - s3 - D.
 */

import { Visibility } from "./thresholds";
import { EXTREMUM, SpineData, height } from "./types";

export interface DisplayGraph {
  /** Node ids drawn: surviving extrema, then connector saddles. */
  nodes: Int32Array;
  /** Parallel arrays, one entry per drawn link (extremum, saddle). */
  linkExtremum: Int32Array;
  linkSaddle: Int32Array;
  numExtrema: number;
  numSaddles: number;
}

export interface DisplayOptions {
  dedupe: boolean;
}

export function buildDisplayGraph(
  d: SpineData,
  vis: Visibility,
  rep: Int32Array,
  opts: DisplayOptions = { dedupe: true },
): DisplayGraph {
  // candidate connectors: saddle -> its two surviving extrema
  const best = new Map<string, number>(); // "a|b" -> saddle (dedupe mode)
  const connectors: number[] = [];
  for (let s = 0; s < d.numNodes; s++) {
    if (d.kind[s] === EXTREMUM) continue;
    const a0 = d.saddleArcs[2 * s], a1 = d.saddleArcs[2 * s + 1];
    if (!vis.arc[a0] && !vis.arc[a1]) continue;
    const e0 = rep[d.arcExtremum[a0]], e1 = rep[d.arcExtremum[a1]];
    if (e0 === e1) continue;
    if (!opts.dedupe) {
      connectors.push(s);
      continue;
    }
    const key = e0 < e1 ? `${e0}|${e1}` : `${e1}|${e0}`;
    const cur = best.get(key);
    if (cur === undefined || height(d, s) > height(d, cur) || (height(d, s) === height(d, cur) && s < cur)) {
      best.set(key, s);
    }
  }
  if (opts.dedupe) connectors.push(...best.values());
  connectors.sort((a, b) => a - b);

  const extrema: number[] = [];
  for (let i = 0; i < d.numRegions; i++) if (vis.node[i]) extrema.push(i);

  const linkE: number[] = [];
  const linkS: number[] = [];
  for (const s of connectors) {
    for (const a of [d.saddleArcs[2 * s], d.saddleArcs[2 * s + 1]]) {
      linkE.push(rep[d.arcExtremum[a]]);
      linkS.push(s);
    }
  }
  return {
    nodes: Int32Array.from([...extrema, ...connectors]),
    linkExtremum: Int32Array.from(linkE),
    linkSaddle: Int32Array.from(linkS),
    numExtrema: extrema.length,
    numSaddles: connectors.length,
  };
}

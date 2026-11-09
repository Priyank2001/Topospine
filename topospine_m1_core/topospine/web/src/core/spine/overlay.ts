/**
 * Packs the drawn graph into the flat arrays the overlay renderer uploads: one segment per
 * link, one centre + kind per node. Pure, so the packing order is tested without a GPU.
 */

import { DisplayGraph } from "../displayGraph";
import { EXTREMUM, SpineData } from "../types";

export interface OverlayData {
  /** Pairs of points, [x0, y0, x1, y1] per link. */
  segments: Float32Array;
  /** [x, y] per node, and its kind (0 extremum, 1 saddle). */
  centers: Float32Array;
  kinds: Float32Array;
}

export function buildOverlay(d: SpineData, g: DisplayGraph, layout: ReadonlyMap<number, [number, number]>): OverlayData {
  const at = (id: number): [number, number] => {
    const p = layout.get(id);
    if (!p) throw new Error(`node ${id} is drawn but has no layout position`);
    return p;
  };
  const segments = new Float32Array(g.linkExtremum.length * 4);
  for (let l = 0; l < g.linkExtremum.length; l++) {
    const a = at(g.linkExtremum[l]), b = at(g.linkSaddle[l]);
    segments.set([a[0], a[1], b[0], b[1]], 4 * l);
  }
  const centers = new Float32Array(g.nodes.length * 2);
  const kinds = new Float32Array(g.nodes.length);
  g.nodes.forEach((id, i) => {
    const [x, y] = at(id);
    centers[2 * i] = x;
    centers[2 * i + 1] = y;
    kinds[i] = d.kind[id] === EXTREMUM ? 0 : 1;
  });
  return { segments, centers, kinds };
}

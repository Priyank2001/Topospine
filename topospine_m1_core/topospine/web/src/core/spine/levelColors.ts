/**
 * Fill colour of each contour level: viridis over the dataset's value range, in the ORIGINAL
 * f (levels are heights g = sign * f, so minimum graphs are flipped back first).
 * Outline colours depend on the theme and are mixed in by the view.
 */

import { viridis } from "../colormap";
import { SpineData } from "../types";

export type RGB = [number, number, number];

export function levelFills(d: SpineData, levels: ArrayLike<number>): RGB[] {
  const [lo, hi] = d.meta.valueRange;
  return Array.from(levels, (g) => viridis((d.sign * g - lo) / (hi - lo || 1)));
}

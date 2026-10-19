/**
 * In-memory form of one exported dataset (pipeline/schema/spine.schema.json).
 *
 * Everything is a typed array indexed by node id, arc id or sample index, so the
 * pure functions in core/ never touch JSON objects or the DOM.
 *
 * Value conventions
 *  - `value` is the ORIGINAL f. For a minimum graph, the code that needs "height"
 *    (levels, link radii) works with g = sign * f, where sign = -1 for minima, so the
 *    same formulas serve both extremum types.
 *  - persistence: +Infinity = never cancelled. saturated*: NaN for extrema.
 */

export const EXTREMUM = 0;
export const SADDLE = 1;

export type Extremum = "maxima" | "minima";
export type Saturation = "paper" | "cancel";

export interface DatasetMeta {
  name: string;
  kind: "grid" | "points";
  extremum: Extremum;
  numSamples: number;
  valueName: string;
  valueRange: [number, number];
  grid?: { dimsXYZ: number[]; spacingXYZ: number[]; originXYZ: number[] };
  points?: { dim: number; featureNames: string[]; offset: number[]; scale: number[] };
  source?: string;
  config?: string;
}

export interface SpineData {
  meta: DatasetMeta;
  /** +1 for maxima, -1 for minima: g = sign * f is "height" for the graph's extrema. */
  sign: 1 | -1;
  numNodes: number;
  kind: Uint8Array;
  value: Float64Array;
  sample: Uint32Array;
  /** numNodes * posDim, row-major. */
  position: Float64Array;
  posDim: number;
  persistence: Float64Array;
  saturated: Float64Array;
  saturatedCancel: Float64Array;
  mergedInto: Int32Array;
  numArcs: number;
  arcSaddle: Uint32Array;
  arcExtremum: Uint32Array;
  /** numNodes * 2 arc ids per saddle, -1 for extrema. */
  saddleArcs: Int32Array;
  /** Extrema are nodes 0..numRegions-1; region r belongs to extremum node r. */
  numRegions: number;
  binEdges: Float64Array;
  /** numRegions * numBins sample counts. */
  regionCounts: Uint32Array;
  labels: Uint16Array | Uint32Array;
  field?: Uint8Array | Float32Array;
  points?: Float32Array;
}

export function numBins(d: SpineData): number {
  return d.binEdges.length - 1;
}

/** Height in the graph's own sense: larger = closer to the extremum. */
export function height(d: SpineData, node: number): number {
  return d.sign * d.value[node];
}

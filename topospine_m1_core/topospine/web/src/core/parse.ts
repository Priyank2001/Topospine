/**
 * graph.json + binary buffers -> SpineData, with the same checks Python's read_export does.
 *
 * Pure: takes already-fetched JSON and ArrayBuffers, so it is unit-tested in Node and the
 * browser loader (data/DatasetLoader.ts) only does I/O.
 */

import { DatasetMeta, EXTREMUM, SADDLE, SpineData } from "./types";

export const FORMAT_VERSION = 1;

export interface BinEntry {
  path: string;
  dtype: "uint8" | "uint16" | "uint32" | "float32";
  shape: number[];
  bytes: number;
}

export class ExportFormatError extends Error {}

function fail(msg: string): never {
  throw new ExportFormatError(msg);
}

const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

export function decodeBin(entry: BinEntry, buf: ArrayBuffer): Uint8Array | Uint16Array | Uint32Array | Float32Array {
  if (!LITTLE_ENDIAN) fail("big-endian hosts are not supported (exports are little-endian)");
  if (buf.byteLength !== entry.bytes) {
    fail(`${entry.path}: ${buf.byteLength} bytes received, index says ${entry.bytes}`);
  }
  const count = entry.shape.reduce((a, b) => a * b, 1);
  const arr =
    entry.dtype === "uint8" ? new Uint8Array(buf)
    : entry.dtype === "uint16" ? new Uint16Array(buf)
    : entry.dtype === "uint32" ? new Uint32Array(buf)
    : entry.dtype === "float32" ? new Float32Array(buf)
    : fail(`${entry.path}: unsupported dtype ${String(entry.dtype)}`);
  if (arr.length !== count) fail(`${entry.path}: ${arr.length} values, shape ${entry.shape} needs ${count}`);
  return arr;
}

const nullable = (xs: (number | null)[], fill: number): Float64Array =>
  Float64Array.from(xs, (x) => (x === null ? fill : x));

/** Files the parser needs, keyed by the names used in graph.json["files"]. */
export function requiredFiles(doc: any): Record<string, BinEntry> {
  if (!doc || doc.version !== FORMAT_VERSION) fail(`unsupported export version ${doc?.version}`);
  return doc.files as Record<string, BinEntry>;
}

export function parseExport(doc: any, buffers: Record<string, ArrayBuffer>): SpineData {
  const files = requiredFiles(doc);
  const meta = doc.dataset as DatasetMeta;
  const nodes = doc.nodes;
  const n: number = nodes.kind.length;
  for (const key of ["value", "sample", "position", "persistence", "saturated", "saturatedCancel", "mergedInto"]) {
    if (!Array.isArray(nodes[key]) || nodes[key].length !== n) fail(`nodes.${key} must have ${n} entries`);
  }

  const kind = Uint8Array.from(nodes.kind as number[]);
  const posDim: number = n ? (nodes.position[0] as number[]).length : 0;
  const position = new Float64Array(n * posDim);
  (nodes.position as number[][]).forEach((p, i) => position.set(p, i * posDim));

  const arcs = doc.arcs as number[][];
  const numArcs = arcs.length;
  const arcSaddle = new Uint32Array(numArcs);
  const arcExtremum = new Uint32Array(numArcs);
  const saddleArcs = new Int32Array(n * 2).fill(-1);
  arcs.forEach(([s, e], a) => {
    if (!(s >= 0 && s < n && e >= 0 && e < n)) fail(`arc ${a} endpoint out of range`);
    if (kind[s] !== SADDLE || kind[e] !== EXTREMUM) fail(`arc ${a} must go saddle -> extremum`);
    arcSaddle[a] = s;
    arcExtremum[a] = e;
    if (saddleArcs[2 * s] === -1) saddleArcs[2 * s] = a;
    else if (saddleArcs[2 * s + 1] === -1) saddleArcs[2 * s + 1] = a;
    else fail(`saddle ${s} has more than two arcs`);
  });
  for (let i = 0; i < n; i++) {
    if (kind[i] === SADDLE && saddleArcs[2 * i + 1] === -1) fail(`saddle ${i} has fewer than two arcs`);
  }

  const numRegions: number = doc.regions.numRegions;
  for (let i = 0; i < numRegions; i++) if (kind[i] !== EXTREMUM) fail("extrema must be nodes 0..numRegions-1");
  const binEdges = Float64Array.from(doc.regions.binEdges as number[]);

  const get = (name: string) => {
    const entry = files[name];
    if (!entry) return undefined;
    const buf = buffers[name];
    if (!buf) fail(`missing buffer for ${name}`);
    return decodeBin(entry, buf);
  };
  const labels = get("labels");
  const regions = get("regions");
  if (!(labels instanceof Uint16Array || labels instanceof Uint32Array)) fail("labels must be uint16 or uint32");
  if (!(regions instanceof Uint32Array)) fail("regions must be uint32");
  if (labels.length !== meta.numSamples) fail("one label per sample required");
  if (regions.length !== numRegions * (binEdges.length - 1)) fail("regions.bin shape mismatch");
  const field = get("field") as Uint8Array | Float32Array | undefined;
  const points = get("points") as Float32Array | undefined;

  return {
    meta,
    sign: meta.extremum === "minima" ? -1 : 1,
    numNodes: n,
    kind,
    value: Float64Array.from(nodes.value as number[]),
    sample: Uint32Array.from(nodes.sample as number[]),
    position,
    posDim,
    persistence: nullable(nodes.persistence, Infinity),
    saturated: nullable(nodes.saturated, NaN),
    saturatedCancel: nullable(nodes.saturatedCancel, NaN),
    mergedInto: Int32Array.from(nodes.mergedInto as number[]),
    numArcs,
    arcSaddle,
    arcExtremum,
    saddleArcs,
    numRegions,
    binEdges,
    regionCounts: regions,
    labels,
    field,
    points,
  };
}

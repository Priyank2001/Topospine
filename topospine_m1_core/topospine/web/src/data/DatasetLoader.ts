/**
 * Fetches exported datasets from public/data (filled by `npm run sync-data`).
 * Only I/O lives here; validation and decoding are in core/parse.ts.
 */

import { parseExport, requiredFiles } from "../core/parse";
import { SpineData } from "../core/types";

export interface DatasetEntry {
  name: string;
  kind: "grid" | "points";
  extremum: "maxima" | "minima";
  numSamples: number;
  numExtrema: number;
  numSaddles: number;
}

export class DatasetLoader {
  constructor(private readonly base = `${import.meta.env.BASE_URL}data/`) {}

  async index(): Promise<DatasetEntry[]> {
    const res = await fetch(`${this.base}index.json`);
    if (!res.ok) return [];
    return (await res.json()) as DatasetEntry[];
  }

  async load(name: string): Promise<SpineData> {
    const dir = `${this.base}${encodeURIComponent(name)}/`;
    const res = await fetch(`${dir}graph.json`);
    if (!res.ok) throw new Error(`${name}/graph.json: HTTP ${res.status}`);
    const doc = await res.json();
    const entries = Object.entries(requiredFiles(doc));
    const buffers: Record<string, ArrayBuffer> = {};
    await Promise.all(
      entries.map(async ([key, entry]) => {
        const r = await fetch(dir + entry.path);
        if (!r.ok) throw new Error(`${name}/${entry.path}: HTTP ${r.status}`);
        buffers[key] = await r.arrayBuffer();
      }),
    );
    return parseExport(doc, buffers);
  }
}

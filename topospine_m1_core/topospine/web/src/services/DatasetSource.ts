/** Where datasets come from. The app depends on this interface; tests pass an in-memory fake. */

import { SpineData } from "../core/types";

/** One row of public/data/index.json (written by scripts/sync-data.mjs). */
export interface DatasetEntry {
  name: string;
  kind: "grid" | "points";
  extremum: "maxima" | "minima";
  numSamples: number;
  numExtrema: number;
  numSaddles: number;
}

export interface DatasetSource {
  index(): Promise<DatasetEntry[]>;
  load(name: string): Promise<SpineData>;
}

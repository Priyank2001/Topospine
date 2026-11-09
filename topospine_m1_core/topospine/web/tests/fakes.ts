/** Test doubles shared by model and presenter tests. */

import { SpineData } from "../src/core/types";
import { DatasetEntry, DatasetSource } from "../src/services/DatasetSource";

/** Lets all pending microtasks and promise continuations run. */
export const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

export function entry(name: string, numExtrema = 3): DatasetEntry {
  return { name, kind: "grid", extremum: "maxima", numSamples: 9, numExtrema, numSaddles: 2 };
}

interface Pending {
  resolve(d: SpineData): void;
  reject(e: Error): void;
}

/** A DatasetSource whose loads finish only when the test says so. */
export class ControlledSource implements DatasetSource {
  readonly pending = new Map<string, Pending>();
  constructor(private readonly entries: DatasetEntry[], private readonly failIndex = false) {}

  async index(): Promise<DatasetEntry[]> {
    if (this.failIndex) throw new Error("index unreachable");
    return this.entries;
  }

  load(name: string): Promise<SpineData> {
    return new Promise((resolve, reject) => this.pending.set(name, { resolve, reject }));
  }

  resolve(name: string, d: SpineData): void {
    this.take(name).resolve(d);
  }

  reject(name: string, message: string): void {
    this.take(name).reject(new Error(message));
  }

  private take(name: string): Pending {
    const p = this.pending.get(name);
    if (!p) throw new Error(`no pending load for ${name}`);
    this.pending.delete(name);
    return p;
  }
}

/**
 * Which datasets exist and which one is open, as two explicit state machines:
 *
 *   index: loading -> ready(entries) | error
 *   load:  idle -> loading(name, requestId) -> ready(name, data) | error(name, message)
 *
 * Synchronous on purpose: the async work (fetching) lives in Workspace, which reports back
 * through these transitions. Every load gets a request id; finishing or failing a request
 * that is no longer the newest is ignored, so a slow first dataset can never replace the
 * one the user picked after it.
 */

import { SpineData } from "../core/types";
import { DatasetEntry } from "../services/DatasetSource";
import { Listener, Store } from "./Store";

export type IndexState =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly entries: readonly DatasetEntry[] }
  | { readonly status: "error"; readonly message: string };

export type LoadState =
  | { readonly status: "idle" }
  | { readonly status: "loading"; readonly name: string; readonly requestId: number }
  | { readonly status: "ready"; readonly name: string; readonly data: SpineData }
  | { readonly status: "error"; readonly name: string; readonly message: string };

export interface SessionState {
  index: IndexState;
  load: LoadState;
}

export class SessionModel {
  private readonly store = new Store<SessionState>({ index: { status: "loading" }, load: { status: "idle" } });
  private latestRequest = 0;

  get state(): Readonly<SessionState> {
    return this.store.get();
  }

  subscribe(fn: Listener<SessionState>): () => void {
    return this.store.subscribe(fn);
  }

  /** The open dataset, if one is fully loaded. */
  get data(): SpineData | undefined {
    const load = this.state.load;
    return load.status === "ready" ? load.data : undefined;
  }

  get entries(): readonly DatasetEntry[] {
    const index = this.state.index;
    return index.status === "ready" ? index.entries : [];
  }

  entry(name: string): DatasetEntry | undefined {
    return this.entries.find((e) => e.name === name);
  }

  /** The dataset to open first: the requested one if it exists, else the first listed. */
  initialDataset(wanted?: string | null): string | undefined {
    return (this.entries.find((e) => e.name === wanted) ?? this.entries[0])?.name;
  }

  setIndex(entries: readonly DatasetEntry[]): void {
    this.store.set({ index: { status: "ready", entries: [...entries] } });
  }

  failIndex(message: string): void {
    this.store.set({ index: { status: "error", message } });
  }

  /** Start loading `name`; returns the id to finish or fail this request with. */
  beginLoad(name: string): number {
    const requestId = ++this.latestRequest;
    this.store.set({ load: { status: "loading", name, requestId } });
    return requestId;
  }

  isCurrent(requestId: number): boolean {
    return requestId === this.latestRequest;
  }

  /** Returns false (and changes nothing) if a newer request has started since. */
  finishLoad(requestId: number, data: SpineData): boolean {
    const load = this.state.load;
    if (!this.isCurrent(requestId) || load.status !== "loading") return false;
    this.store.set({ load: { status: "ready", name: load.name, data } });
    return true;
  }

  failLoad(requestId: number, message: string): boolean {
    const load = this.state.load;
    if (!this.isCurrent(requestId) || load.status !== "loading") return false;
    this.store.set({ load: { status: "error", name: load.name, message } });
    return true;
  }
}

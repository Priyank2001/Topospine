/**
 * The live spine parameters and the rules that keep them valid:
 *   0 <= pLo <= pHi   (pHi = +Infinity means "no variation limit")
 * Every threshold change in the app goes through these methods, so no view or presenter
 * clamps anything itself. Options without cross-field rules go through `setOptions`.
 */

import { DEFAULT_PARAMS, SpineOptions, SpineParams } from "../core/spineState";
import { suggestNoiseThreshold } from "../core/thresholds";
import { SpineData } from "../core/types";
import { Listener, Store } from "./Store";

export class SpineParamsModel {
  private readonly store: Store<SpineParams>;

  constructor(initial: SpineParams = DEFAULT_PARAMS) {
    this.store = new Store(initial);
  }

  get state(): Readonly<SpineParams> {
    return this.store.get();
  }

  subscribe(fn: Listener<SpineParams>): () => void {
    return this.store.subscribe(fn);
  }

  /** Both thresholds at once; pHi is raised to pLo if needed. */
  setThresholds(pLo: number, pHi: number): void {
    const lo = clampNonNegative(pLo);
    this.store.set({ pLo: lo, pHi: Math.max(Number.isNaN(pHi) ? lo : pHi, lo) });
  }

  /** Noise threshold alone: it may not pass the variation threshold. */
  setNoise(pLo: number): void {
    this.store.set({ pLo: Math.min(clampNonNegative(pLo), this.state.pHi) });
  }

  /** Variation threshold alone: it may not drop below the noise threshold. +Infinity = no limit. */
  setVariation(pHi: number): void {
    this.setThresholds(this.state.pLo, pHi);
  }

  unlimitVariation(): void {
    this.store.set({ pHi: Infinity });
  }

  setOptions(patch: Partial<SpineOptions>): void {
    this.store.set(patch);
  }

  /** A freshly opened dataset starts in the widest gap between noise and features. */
  resetForDataset(data: SpineData): void {
    this.setThresholds(suggestNoiseThreshold(data), Infinity);
  }
}

function clampNonNegative(p: number): number {
  return Number.isFinite(p) || p === Infinity ? Math.max(0, p) : 0;
}

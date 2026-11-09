/** The persistence plot: two sampled step curves and two draggable thresholds. */

export interface PlotViewModel {
  /** Sample positions on the persistence axis, and the curve values at each. */
  readonly t: Float64Array;
  readonly extrema: Int32Array;
  readonly arcs: Int32Array;
  readonly xMax: number;
  readonly pLo: number;
  /** +Infinity = no variation limit (the line sits at the right edge). */
  readonly pHi: number;
  readonly loLabel: string;
  readonly hiLabel: string;
  /** Ticks on the persistence axis at P of selected / hovered nodes (+Infinity at the right edge). */
  readonly marks: readonly PlotMark[];
}

export interface PlotMark {
  readonly p: number;
  readonly kind: "selected" | "hovered";
}

/** Raw user intents; the model applies the threshold rules. */
export interface PlotViewEvents {
  noiseDragged(pLo: number): void;
  /** +Infinity when dragged to the right edge. */
  variationDragged(pHi: number): void;
}

export interface IPlotView {
  bind(events: PlotViewEvents): void;
  render(vm: PlotViewModel): void;
  dispose(): void;
}

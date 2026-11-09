/** The parameter panel: dataset picker, thresholds, spine options, "fit view". */

import { SpineOptions, SpineParams } from "../../core/spineState";

export interface PanelViewModel {
  readonly datasets: readonly string[];
  readonly dataset: string;
  /** Slider range for both thresholds. */
  readonly maxP: number;
  readonly params: Readonly<SpineParams>;
}

export interface PanelViewEvents {
  datasetChosen(name: string): void;
  noiseChanged(pLo: number): void;
  variationChanged(pHi: number): void;
  variationLimitToggled(on: boolean): void;
  optionsChanged(patch: Partial<SpineOptions>): void;
  fitRequested(): void;
}

export interface IPanelView {
  bind(events: PanelViewEvents): void;
  render(vm: PanelViewModel): void;
  dispose(): void;
}

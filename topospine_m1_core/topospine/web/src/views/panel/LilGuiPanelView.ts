/**
 * lil-gui parameter panel. Passive (MVP): `render` copies the view model into lil-gui's
 * bound object, and every widget reports a raw intent through PanelViewEvents. No rules here
 * (e.g. "pHi >= pLo" is SpineParamsModel's job); lil-gui's onChange fires only on user input,
 * never on updateDisplay, so rendering can't loop back into events.
 */

import GUI, { Controller } from "lil-gui";
import { DEFAULT_PARAMS, SpineOptions, SpineParams } from "../../core/spineState";
import { IPanelView, PanelViewEvents, PanelViewModel } from "./contract";

/** The object lil-gui binds to: one field per widget. */
interface Widgets extends SpineParams {
  dataset: string;
  limitVariation: boolean;
  fit: () => void;
}

export class LilGuiPanelView implements IPanelView {
  private readonly gui: GUI;
  private readonly widgets: Widgets;
  private events?: PanelViewEvents;
  private thresholdCtrls: Controller[] = [];
  private built = false;
  private maxP = 1;

  constructor(container: HTMLElement) {
    this.gui = new GUI({ container, autoPlace: false, title: "Parameters", width: 320 });
    this.widgets = { dataset: "", limitVariation: false, fit: () => this.events?.fitRequested(), ...DEFAULT_PARAMS, pHi: 0 };
  }

  bind(events: PanelViewEvents): void {
    this.events = events;
  }

  render(vm: PanelViewModel): void {
    if (!this.built && vm.datasets.length) this.build(vm.datasets); // the dataset list is fixed for a session
    const w = this.widgets, p = vm.params;
    Object.assign(w, p);
    w.dataset = vm.dataset;
    w.limitVariation = Number.isFinite(p.pHi);
    w.pHi = Number.isFinite(p.pHi) ? p.pHi : vm.maxP; // unlimited: park the slider at the right end
    if (vm.maxP !== this.maxP) {
      this.maxP = vm.maxP;
      for (const c of this.thresholdCtrls) c.max(vm.maxP).step(vm.maxP / 500);
    }
    this.gui.controllersRecursive().forEach((c) => c.updateDisplay());
  }

  private build(datasets: readonly string[]): void {
    const w = this.widgets;
    const option = (patch: Partial<SpineOptions>) => this.events?.optionsChanged(patch);
    this.gui.add(w, "dataset", [...datasets]).name("Dataset").onChange((v: string) => this.events?.datasetChosen(v));

    const th = this.gui.addFolder("Thresholds");
    const lo = th.add(w, "pLo", 0, this.maxP, this.maxP / 500).name("Noise (p lo)").onChange((v: number) => this.events?.noiseChanged(v));
    th.add(w, "limitVariation").name("Limit variation").onChange((on: boolean) => this.events?.variationLimitToggled(on));
    const hi = th.add(w, "pHi", 0, this.maxP, this.maxP / 500).name("Variation (p hi)").onChange((v: number) => this.events?.variationChanged(v));
    th.add(w, "saturation", { "Algorithm 1 (paper)": "paper", "Cancellations only": "cancel" })
      .name("Saturated persistence").onChange((v: SpineParams["saturation"]) => option({ saturation: v }));
    this.thresholdCtrls = [lo, hi];

    const sp = this.gui.addFolder("Spine");
    sp.add(w, "radiusMode", { "Area ∝ volume": "sqrt", "Radius ∝ volume (paper)": "linear" })
      .name("Size encoding").onChange((v: SpineParams["radiusMode"]) => option({ radiusMode: v }));
    sp.add(w, "glyphScale", 0.1, 2, 0.05).name("Glyph size").onChange((v: number) => option({ glyphScale: v }));
    sp.add(w, "minLevelGap", 0, 0.2, 0.005).name("Min. level gap").onChange((v: number) => option({ minLevelGap: v }));
    sp.add(w, "extraLevels", 0, 16, 1).name("Extra contours").onChange((v: number) => option({ extraLevels: v }));
    sp.add(w, "maxLevels", 1, 48, 1).name("Max. levels").onChange((v: number) => option({ maxLevels: v }));
    sp.add(w, "dedupe").name("One saddle per pair").onChange((v: boolean) => option({ dedupe: v }));
    sp.add(w, "showSkeleton").name("Show links").onChange((v: boolean) => option({ showSkeleton: v }));
    sp.add(w, "showNodes").name("Show critical points").onChange((v: boolean) => option({ showNodes: v }));
    this.gui.add(w, "fit").name("Fit view");
    this.built = true;
  }

  dispose(): void {
    this.gui.destroy();
  }
}


/**
 * lil-gui panel bound to the store. It only reads state and calls store.set; it never
 * touches the view or the pipeline (the App routes changes), so the UI can be swapped.
 */

import GUI from "lil-gui";
import { SpineParams } from "../core/spineState";
import { Store } from "../core/store";

export class Panel {
  private readonly gui: GUI;
  private readonly model: Record<string, unknown>;
  private datasetCtrl?: ReturnType<GUI["add"]>;
  private maxP = 1;

  constructor(
    container: HTMLElement,
    private readonly store: Store<SpineParams>,
    private readonly actions: { fit: () => void; open: (name: string) => void },
  ) {
    this.gui = new GUI({ container, autoPlace: false, title: "Parameters", width: 320 });
    const s = store.get();
    this.model = {
      dataset: "",
      pLo: s.pLo,
      pHi: Number.isFinite(s.pHi) ? s.pHi : 0,
      limitVariation: Number.isFinite(s.pHi),
      saturation: s.saturation,
      dedupe: s.dedupe,
      radiusMode: s.radiusMode,
      glyphScale: s.glyphScale,
      minLevelGap: s.minLevelGap,
      maxLevels: s.maxLevels,
      extraLevels: s.extraLevels,
      showSkeleton: s.showSkeleton,
      showNodes: s.showNodes,
      fit: () => actions.fit(),
    };
  }

  build(datasets: string[], maxP: number): void {
    const m = this.model;
    const set = (patch: Partial<SpineParams>) => this.store.set(patch);
    this.datasetCtrl = this.gui.add(m, "dataset", datasets).name("Dataset").onChange((v: string) => this.actions.open(v));

    const th = this.gui.addFolder("Thresholds");
    th.add(m, "pLo", 0, maxP, maxP / 500).name("Noise (p lo)").onChange((v: number) => set({ pLo: v }));
    th.add(m, "limitVariation").name("Limit variation").onChange((on: boolean) =>
      set({ pHi: on ? Math.max(m.pHi as number, this.store.get().pLo) : Infinity }));
    th.add(m, "pHi", 0, maxP, maxP / 500).name("Variation (p hi)").onChange((v: number) => {
      m.limitVariation = true;
      set({ pHi: Math.max(v, this.store.get().pLo) });
    });
    th.add(m, "saturation", { "Algorithm 1 (paper)": "paper", "Cancellations only": "cancel" })
      .name("Saturated persistence").onChange((v: SpineParams["saturation"]) => set({ saturation: v }));

    const sp = this.gui.addFolder("Spine");
    sp.add(m, "radiusMode", { "Area ∝ volume": "sqrt", "Radius ∝ volume (paper)": "linear" })
      .name("Size encoding").onChange((v: SpineParams["radiusMode"]) => set({ radiusMode: v }));
    sp.add(m, "glyphScale", 0.1, 2, 0.05).name("Glyph size").onChange((v: number) => set({ glyphScale: v }));
    sp.add(m, "minLevelGap", 0, 0.2, 0.005).name("Min. level gap").onChange((v: number) => set({ minLevelGap: v }));
    sp.add(m, "extraLevels", 0, 16, 1).name("Extra contours").onChange((v: number) => set({ extraLevels: v }));
    sp.add(m, "maxLevels", 1, 48, 1).name("Max. levels").onChange((v: number) => set({ maxLevels: v }));
    sp.add(m, "dedupe").name("One saddle per pair").onChange((v: boolean) => set({ dedupe: v }));
    sp.add(m, "showSkeleton").name("Show links").onChange((v: boolean) => set({ showSkeleton: v }));
    sp.add(m, "showNodes").name("Show critical points").onChange((v: boolean) => set({ showNodes: v }));
    this.gui.add(m, "fit").name("Fit view");
  }

  /** Reflect store changes made elsewhere (e.g. dragging in the plot). */
  sync(datasetName?: string, maxP?: number): void {
    const s = this.store.get();
    const m = this.model;
    if (datasetName !== undefined) m.dataset = datasetName;
    m.pLo = s.pLo;
    m.limitVariation = Number.isFinite(s.pHi);
    if (maxP !== undefined) this.maxP = maxP;
    m.pHi = Number.isFinite(s.pHi) ? s.pHi : this.maxP; // unlimited: park the slider at the right end
    m.saturation = s.saturation;
    if (maxP !== undefined) {
      for (const c of this.gui.controllersRecursive()) {
        if (c.property === "pLo" || c.property === "pHi") (c as any).max(maxP).step(maxP / 500);
      }
    }
    this.gui.controllersRecursive().forEach((c) => c.updateDisplay());
    this.datasetCtrl?.updateDisplay();
  }

  dispose(): void {
    this.gui.destroy();
  }
}

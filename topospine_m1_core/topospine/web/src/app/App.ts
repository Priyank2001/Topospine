/**
 * Composition of the spine screen: loader -> pipeline -> view, with the store in the middle.
 *
 *   Panel / PersistencePlot --set--> Store --subscribe--> App.update()
 *   App.update(): SpinePipeline.frame(params) -> SpineView.setContent(...) + plot + stats
 *
 * The App is the only module that knows all the others.
 */

import { viridis } from "../core/colormap";
import { SpineFrame, SpinePipeline } from "../core/derive";
import { DEFAULT_PARAMS, SpineParams } from "../core/spineState";
import { Store } from "../core/store";
import { maxFinitePersistence, suggestNoiseThreshold } from "../core/thresholds";
import { EXTREMUM, SpineData } from "../core/types";
import { DatasetEntry, DatasetLoader } from "../data/DatasetLoader";
import { OverlayData } from "../render/Overlay";
import { LevelStyle } from "../render/SpineSdfRenderer";
import { Panel } from "../ui/Panel";
import { PersistencePlot, fmt } from "../ui/PersistencePlot";
import { SpineView, readTheme } from "../view/SpineView";

export interface AppElements {
  canvas: HTMLCanvasElement;
  plot: HTMLCanvasElement;
  panel: HTMLElement;
  stats: HTMLElement;
  status: HTMLElement;
  datasetLine: HTMLElement;
}

export class App {
  private readonly store = new Store<SpineParams>(DEFAULT_PARAMS);
  private readonly loader = new DatasetLoader();
  private readonly view: SpineView;
  private readonly plot: PersistencePlot;
  private readonly panel: Panel;
  private readonly unsubscribe: () => void;
  private data?: SpineData;
  private pipeline?: SpinePipeline;
  private entries: DatasetEntry[] = [];
  private needsFit = false;

  constructor(private readonly el: AppElements) {
    this.view = new SpineView(el.canvas);
    this.plot = new PersistencePlot(el.plot, (pLo, pHi) => this.store.set({ pLo, pHi }));
    this.panel = new Panel(el.panel, this.store, { fit: () => this.view.fit(), open: (n) => void this.open(n) });
    this.unsubscribe = this.store.subscribe(() => this.update());
  }

  async start(): Promise<void> {
    this.entries = await this.loader.index();
    if (!this.entries.length) {
      this.status("No datasets yet. Export one with the pipeline, then run `npm run sync-data` and reload.");
      return;
    }
    this.panel.build(this.entries.map((e) => e.name), 1);
    // ?dataset=name opens a specific dataset (handy for demos and screenshots)
    const wanted = new URLSearchParams(location.search).get("dataset");
    const first = this.entries.find((e) => e.name === wanted) ?? this.entries[0];
    await this.open(first.name);
  }

  async open(name: string): Promise<void> {
    this.status(`Loading ${name}…`);
    try {
      this.data = await this.loader.load(name);
    } catch (err) {
      this.status(`Could not load ${name}: ${(err as Error).message}`);
      return;
    }
    const d = this.data;
    this.pipeline = new SpinePipeline(d);
    const maxP = maxFinitePersistence(d) || 1;
    this.plot.setData(d);
    const e = this.entries.find((x) => x.name === name);
    this.el.datasetLine.textContent =
      `${d.meta.name}: ${d.meta.kind === "grid" ? d.meta.grid!.dimsXYZ.join(" × ") + " grid" : `${d.meta.numSamples} points in ${d.meta.points!.dim}-D`}, ` +
      `${d.meta.extremum} graph${e ? `, ${e.numExtrema} extrema before simplification` : ""}`;
    this.needsFit = true;
    // start in the widest gap between noise and features (see suggestNoiseThreshold)
    this.store.set({ pLo: suggestNoiseThreshold(d), pHi: Infinity });
    this.panel.sync(name, maxP);
    this.update();
    this.status("");
  }

  private update(): void {
    if (!this.data || !this.pipeline) return;
    const p = this.store.get();
    let frame: SpineFrame;
    try {
      frame = this.pipeline.frame(p);
    } catch (err) {
      this.status((err as Error).message);
      return;
    }
    this.view.setContent(frame.geometry, this.levelStyles(frame), this.overlayData(frame), p.showSkeleton, p.showNodes);
    if (this.needsFit) {
      this.view.fit();
      this.needsFit = false;
    }
    this.plot.setThresholds(p.pLo, p.pHi);
    this.panel.sync();
    this.showStats(frame);
  }

  private levelStyles(frame: SpineFrame): LevelStyle[] {
    const d = this.data!;
    const [lo, hi] = d.meta.valueRange;
    const ink = readTheme().ink;
    return Array.from(frame.geometry.levels, (g) => {
      const f = d.sign * g;
      const fill = viridis((f - lo) / (hi - lo || 1));
      const line = fill.map((c, i) => 0.5 * c + 0.5 * ink[i]) as [number, number, number];
      return { fill, line };
    });
  }

  private overlayData(frame: SpineFrame): OverlayData {
    const d = this.data!;
    const g = frame.display;
    const segments = new Float32Array(g.linkExtremum.length * 4);
    for (let l = 0; l < g.linkExtremum.length; l++) {
      const a = frame.layout.get(g.linkExtremum[l])!, b = frame.layout.get(g.linkSaddle[l])!;
      segments.set([a[0], a[1], b[0], b[1]], 4 * l);
    }
    const centers = new Float32Array(g.nodes.length * 2);
    const kinds = new Float32Array(g.nodes.length);
    g.nodes.forEach((id, i) => {
      const [x, y] = frame.layout.get(id)!;
      centers[2 * i] = x;
      centers[2 * i + 1] = y;
      kinds[i] = d.kind[id] === EXTREMUM ? 0 : 1;
    });
    return { segments, centers, kinds };
  }

  private showStats(frame: SpineFrame): void {
    const t = frame.timings;
    const rows: [string, string][] = [
      ["Extrema shown", String(frame.display.numExtrema)],
      ["Connecting saddles", String(frame.display.numSaddles)],
      ["Contour levels", String(frame.geometry.levels.length)],
      ["Layout", t.layoutSkipped ? "PCA only (too many nodes; raise the noise threshold)" : `${t.layoutMs.toFixed(0)} ms, ${t.layoutIterations} iterations`],
      ["Radius scale", fmt(frame.geometry.radiusScale)],
    ];
    this.el.stats.replaceChildren(
      ...rows.flatMap(([k, v]) => {
        const dt = document.createElement("dt");
        dt.textContent = k;
        const dd = document.createElement("dd");
        dd.textContent = v;
        return [dt, dd];
      }),
    );
  }

  private status(msg: string): void {
    this.el.status.textContent = msg;
    this.el.status.hidden = !msg;
  }

  dispose(): void {
    this.unsubscribe();
    this.view.dispose();
    this.plot.dispose();
    this.panel.dispose();
  }
}

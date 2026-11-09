/**
 * Persistence plot: sampled curves of the open dataset + current thresholds -> PlotViewModel;
 * drags -> SpineParamsModel. Curves are computed once per dataset. Selected and hovered nodes
 * appear as ticks at their persistence, so you can see which threshold would hide them.
 */

import { memo } from "../core/derive";
import { fmt, fmtThreshold } from "../core/format";
import { arcCurve, extremaCurve, maxFinitePersistence } from "../core/thresholds";
import { SpineData } from "../core/types";
import { SelectionModel, SelectionState } from "../model/SelectionModel";
import { SessionModel } from "../model/SessionModel";
import { SpineParamsModel } from "../model/SpineParamsModel";
import { IPlotView, PlotMark } from "../views/plot/contract";
import { Presenter } from "./Presenter";

/** Samples along the persistence axis; the curves are step functions, so this is plenty. */
const SAMPLES = 400;
/** Head-room right of the largest finite persistence, so its step is visible. */
const X_MARGIN = 1.05;

export function plotCurves(d: SpineData): { t: Float64Array; extrema: Int32Array; arcs: Int32Array; xMax: number } {
  const xMax = (maxFinitePersistence(d) || 1) * X_MARGIN;
  const t = Float64Array.from({ length: SAMPLES }, (_, i) => (i / (SAMPLES - 1)) * xMax);
  return { t, extrema: extremaCurve(d, t), arcs: arcCurve(d, t), xMax };
}

/** One tick per selected node, plus the hovered one if it isn't selected. */
export function plotMarks(d: SpineData, s: Readonly<SelectionState>): PlotMark[] {
  const marks: PlotMark[] = [...s.selected].map((id) => ({ p: d.persistence[id], kind: "selected" }));
  if (s.hovered !== null && !s.selected.has(s.hovered)) marks.push({ p: d.persistence[s.hovered], kind: "hovered" });
  return marks;
}

export class PlotPresenter extends Presenter {
  private readonly curves = memo(plotCurves);

  constructor(
    private readonly view: IPlotView,
    private readonly session: SessionModel,
    private readonly params: SpineParamsModel,
    private readonly selection: SelectionModel,
  ) {
    super(view);
    view.bind({
      noiseDragged: (p) => params.setNoise(p),
      variationDragged: (p) => params.setVariation(p),
    });
    const changed = () => this.invalidate();
    this.listen(session.subscribe(changed), params.subscribe(changed), selection.subscribe(changed));
    this.invalidate();
  }

  protected present(): void {
    const d = this.session.data;
    if (!d) return;
    const { pLo, pHi } = this.params.state;
    this.view.render({
      ...this.curves(d), pLo, pHi, loLabel: `noise ${fmt(pLo)}`, hiLabel: `variation ${fmtThreshold(pHi)}`,
      marks: plotMarks(d, this.selection.state),
    });
  }
}

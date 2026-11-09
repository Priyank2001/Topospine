/** Stats list: the current frame -> formatted rows. */

import { fmt } from "../core/format";
import { SpineFrame } from "../core/derive";
import { SessionModel } from "../model/SessionModel";
import { SpineFrames } from "../model/SpineFrames";
import { SpineParamsModel } from "../model/SpineParamsModel";
import { IStatsView, StatRow } from "../views/stats/contract";
import { Presenter } from "./Presenter";

export function statsRows(frame: SpineFrame): StatRow[] {
  const t = frame.timings;
  return [
    ["Extrema shown", String(frame.display.numExtrema)],
    ["Connecting saddles", String(frame.display.numSaddles)],
    ["Contour levels", String(frame.geometry.levels.length)],
    ["Layout", t.layoutSkipped ? "PCA only (too many nodes; raise the noise threshold)" : `${t.layoutMs.toFixed(0)} ms, ${t.layoutIterations} iterations`],
    ["Radius scale", fmt(frame.geometry.radiusScale)],
  ];
}

export class StatsPresenter extends Presenter {
  constructor(
    private readonly view: IStatsView,
    private readonly frames: SpineFrames,
    session: SessionModel,
    params: SpineParamsModel,
  ) {
    super(view);
    this.listen(session.subscribe(() => this.invalidate()), params.subscribe(() => this.invalidate()));
    this.invalidate();
  }

  protected present(): void {
    const r = this.frames.current();
    if (r.status === "ok") this.view.render(statsRows(r.frame));
  }
}

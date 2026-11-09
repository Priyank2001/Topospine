/**
 * Status overlay and dataset description line: session + frame state -> two lines of text.
 * Every state of the index and load machines has exactly one message here.
 */

import { SpineData } from "../core/types";
import { DatasetEntry } from "../services/DatasetSource";
import { SessionModel } from "../model/SessionModel";
import { SpineFrames } from "../model/SpineFrames";
import { SpineParamsModel } from "../model/SpineParamsModel";
import { ITextView } from "../views/text/contract";
import { Presenter } from "./Presenter";

export const NO_DATASETS = "No datasets yet. Export one with the pipeline, then run `npm run sync-data` and reload.";

export function statusMessage(session: SessionModel, frames: SpineFrames): string {
  const { index, load } = session.state;
  if (index.status === "error") return `Startup failed: ${index.message}`;
  if (index.status === "ready" && !index.entries.length) return NO_DATASETS;
  switch (load.status) {
    case "idle": return "";
    case "loading": return `Loading ${load.name}…`;
    case "error": return `Could not load ${load.name}: ${load.message}`;
    case "ready": {
      const r = frames.current();
      return r.status === "error" ? r.message : "";
    }
  }
}

export function datasetLine(d: SpineData, entry?: DatasetEntry): string {
  const m = d.meta;
  const domain = m.grid ? `${m.grid.dimsXYZ.join(" × ")} grid` : `${m.numSamples} points in ${m.points?.dim ?? "?"}-D`;
  const before = entry ? `, ${entry.numExtrema} extrema before simplification` : "";
  return `${m.name}: ${domain}, ${m.extremum} graph${before}`;
}

export class StatusPresenter extends Presenter {
  private readonly lineView: ITextView;

  constructor(
    private readonly statusView: ITextView,
    lineView: ITextView,
    private readonly frames: SpineFrames,
    private readonly session: SessionModel,
    params: SpineParamsModel,
  ) {
    super(statusView);
    this.lineView = lineView;
    this.listen(session.subscribe(() => this.invalidate()), params.subscribe(() => this.invalidate()));
    this.invalidate();
  }

  protected present(): void {
    this.statusView.render(statusMessage(this.session, this.frames));
    const load = this.session.state.load;
    if (load.status === "ready") this.lineView.render(datasetLine(load.data, this.session.entry(load.name)));
  }

  dispose(): void {
    super.dispose();
    this.lineView.dispose();
  }
}

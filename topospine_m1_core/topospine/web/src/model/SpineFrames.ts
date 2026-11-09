/**
 * Derived state: the SpineFrame for the open dataset and the current parameters.
 *
 * Never stored, only cached: one SpinePipeline per dataset, one frame per (dataset, params
 * snapshot), and one SelectionContext per frame. Several presenters (spine, stats, status,
 * selection) ask for the same frame in the same tick and get the same object, so the layout
 * runs once and warm-starts correctly.
 */

import { SpineFrame, SpinePipeline, memo } from "../core/derive";
import { SelectionContext, drawnNodes } from "../core/selection";
import { SpineParams } from "../core/spineState";
import { SpineData } from "../core/types";
import { SessionModel } from "./SessionModel";
import { SpineParamsModel } from "./SpineParamsModel";

export type FrameResult =
  | { readonly status: "none" }
  | { readonly status: "ok"; readonly data: SpineData; readonly params: Readonly<SpineParams>; readonly frame: SpineFrame }
  | { readonly status: "error"; readonly message: string };

const NONE: FrameResult = { status: "none" };

export class SpineFrames {
  private readonly pipelineFor = memo((d: SpineData) => new SpinePipeline(d));
  private readonly compute = memo((data: SpineData, params: Readonly<SpineParams>): FrameResult => {
    try {
      return { status: "ok", data, params, frame: this.pipelineFor(data).frame(params) };
    } catch (err) {
      return { status: "error", message: err instanceof Error ? err.message : String(err) };
    }
  });

  private readonly contextFor = memo((data: SpineData, frame: SpineFrame): SelectionContext => ({
    data, rep: frame.rep, regions: frame.regions, drawn: drawnNodes(frame.display),
  }));

  constructor(
    private readonly session: SessionModel,
    private readonly params: SpineParamsModel,
  ) {}

  current(): FrameResult {
    const data = this.session.data;
    return data ? this.compute(data, this.params.state) : NONE;
  }

  /** What selection lookups need for the current frame (shared, built once per frame). */
  selectionContext(): SelectionContext | null {
    const r = this.current();
    return r.status === "ok" ? this.contextFor(r.data, r.frame) : null;
  }
}

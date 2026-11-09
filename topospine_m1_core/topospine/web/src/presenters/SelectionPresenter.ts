/**
 * Selection details: the hovered and selected nodes, described under the current thresholds
 * (core/selection.ts), formatted into rows. A merged pick says what it merged into; a hidden
 * one says so, instead of silently disappearing.
 */

import { fmt, fmtThreshold } from "../core/format";
import { NodeInfo, SelectionContext, describeNode, nodeLabel } from "../core/selection";
import { SelectionModel } from "../model/SelectionModel";
import { SessionModel } from "../model/SessionModel";
import { SpineFrames } from "../model/SpineFrames";
import { SpineParamsModel } from "../model/SpineParamsModel";
import { ISelectionView, NodeRow } from "../views/selection/contract";
import { Presenter } from "./Presenter";

export const HINT_EMPTY = "Click a node to select it. Shift-click adds, Esc clears.";

export function nodeRow(ctx: SelectionContext, info: NodeInfo): NodeRow {
  const parts = [`f ${fmt(info.value)}`, `P ${fmtThreshold(info.persistence)}`];
  if (info.samples !== null) parts.push(`${Math.round(info.samples).toLocaleString("en-US")} samples`);
  const s = info.status;
  const note =
    s.kind === "visible" ? "" :
    s.kind === "merged" ? `merged into ${nodeLabel(ctx.data, s.into)} at this noise threshold` :
    "hidden at current thresholds";
  return { title: nodeLabel(ctx.data, info.id), detail: parts.join(" · "), note };
}

export class SelectionPresenter extends Presenter {
  constructor(
    private readonly view: ISelectionView,
    private readonly frames: SpineFrames,
    session: SessionModel,
    params: SpineParamsModel,
    private readonly selection: SelectionModel,
  ) {
    super(view);
    const changed = () => this.invalidate();
    this.listen(session.subscribe(changed), params.subscribe(changed), selection.subscribe(changed));
    this.invalidate();
  }

  protected present(): void {
    const ctx = this.frames.selectionContext();
    const { hovered, selected } = this.selection.state;
    if (!ctx) {
      this.view.render({ hovered: null, selected: [], hint: HINT_EMPTY });
      return;
    }
    const describe = (id: number) => nodeRow(ctx, describeNode(ctx, id));
    this.view.render({
      hovered: hovered === null ? null : describe(hovered),
      selected: [...selected].map(describe),
      hint: selected.size ? `${selected.size} selected. Shift-click adds or removes, Esc clears.` : HINT_EMPTY,
    });
  }
}

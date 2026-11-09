/**
 * Spine canvas: frame of the open dataset -> SpineViewModel; selection -> highlight rings;
 * hover/click intents -> SelectionModel.
 *
 * Content and highlights are presented separately: a selection change sends only rings, and
 * the spine is re-sent only when the content view model changes (it is cached on its inputs,
 * so toggling "show nodes" doesn't repack the overlay either). Fits the camera when a new
 * dataset is first shown.
 */

import { SpineFrame, memo } from "../core/derive";
import { DisplayGraph } from "../core/displayGraph";
import { highlightFor } from "../core/selection";
import { levelFills } from "../core/spine/levelColors";
import { buildOverlay } from "../core/spine/overlay";
import { SpineData } from "../core/types";
import { SelectionModel } from "../model/SelectionModel";
import { SessionModel } from "../model/SessionModel";
import { SpineFrames } from "../model/SpineFrames";
import { SpineParamsModel } from "../model/SpineParamsModel";
import { ISpineView, SpineViewModel } from "../views/spine/contract";
import { Presenter } from "./Presenter";

export class SpinePresenter extends Presenter {
  private readonly fills = memo((d: SpineData, levels: Float64Array) => levelFills(d, levels));
  private readonly overlay = memo((d: SpineData, g: DisplayGraph, layout: Map<number, [number, number]>) => buildOverlay(d, g, layout));
  private readonly content = memo((d: SpineData, frame: SpineFrame, showSkeleton: boolean, showNodes: boolean): SpineViewModel => ({
    geometry: frame.geometry,
    levelFills: this.fills(d, frame.geometry.levels),
    overlay: this.overlay(d, frame.display, frame.layout),
    nodeIds: frame.display.nodes,
    showSkeleton,
    showNodes,
  }));
  private rendered?: SpineViewModel;
  private fittedTo?: SpineData;

  constructor(
    private readonly view: ISpineView,
    private readonly frames: SpineFrames,
    session: SessionModel,
    params: SpineParamsModel,
    private readonly selection: SelectionModel,
  ) {
    super(view);
    view.bind({
      nodeHovered: (id) => selection.hover(id),
      nodeClicked: (id, additive) => (additive ? selection.toggle(id) : selection.selectOnly(id)),
      cleared: () => selection.clear(),
    });
    const changed = () => this.invalidate();
    this.listen(session.subscribe(changed), params.subscribe(changed), selection.subscribe(changed));
    this.invalidate();
  }

  /** "Fit view" command from elsewhere in the UI. */
  fitView(): void {
    this.view.fit();
  }

  protected present(): void {
    const r = this.frames.current();
    const ctx = this.frames.selectionContext();
    if (r.status !== "ok" || !ctx) return; // keep showing the last good frame while loading or on error
    const vm = this.content(r.data, r.frame, r.params.showSkeleton, r.params.showNodes);
    if (vm !== this.rendered) {
      this.view.render(vm);
      this.rendered = vm;
    }
    if (this.fittedTo !== r.data) {
      this.view.fit();
      this.fittedTo = r.data;
    }
    const { hovered, selected } = this.selection.state;
    this.view.highlight(highlightFor(ctx, hovered, selected));
  }
}

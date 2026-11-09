/** Fake views: record what presenters render and let tests fire user intents. */

import { IPanelView, PanelViewEvents, PanelViewModel } from "../../src/views/panel/contract";
import { IPlotView, PlotViewEvents, PlotViewModel } from "../../src/views/plot/contract";
import { HighlightItem } from "../../src/core/selection";
import { ISelectionView, SelectionViewModel } from "../../src/views/selection/contract";
import { ISpineView, SpineViewEvents, SpineViewModel } from "../../src/views/spine/contract";
import { IStatsView, StatRow } from "../../src/views/stats/contract";
import { ITextView } from "../../src/views/text/contract";

abstract class Recorder<VM> {
  readonly renders: VM[] = [];
  disposed = false;
  get last(): VM | undefined {
    return this.renders[this.renders.length - 1];
  }
  render(vm: VM): void {
    this.renders.push(vm);
  }
  dispose(): void {
    this.disposed = true;
  }
}

export class FakeSpineView extends Recorder<SpineViewModel> implements ISpineView {
  events!: SpineViewEvents;
  highlights: (readonly HighlightItem[])[] = [];
  fits = 0;
  bind(e: SpineViewEvents): void {
    this.events = e;
  }
  highlight(items: readonly HighlightItem[]): void {
    this.highlights.push(items);
  }
  fit(): void {
    this.fits++;
  }
}

export class FakePlotView extends Recorder<PlotViewModel> implements IPlotView {
  events!: PlotViewEvents;
  bind(e: PlotViewEvents): void {
    this.events = e;
  }
}

export class FakePanelView extends Recorder<PanelViewModel> implements IPanelView {
  events!: PanelViewEvents;
  bind(e: PanelViewEvents): void {
    this.events = e;
  }
}

export class FakeStatsView extends Recorder<readonly StatRow[]> implements IStatsView {}

export class FakeTextView extends Recorder<string> implements ITextView {}

export class FakeSelectionView extends Recorder<SelectionViewModel> implements ISelectionView {}

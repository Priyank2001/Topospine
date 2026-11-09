/**
 * Parameter panel: session + params -> PanelViewModel; widget intents -> model methods.
 * "Fit view" is a command on another presenter, injected so this one doesn't know it.
 */

import { maxFinitePersistence } from "../core/thresholds";
import { Workspace } from "../model/Workspace";
import { IPanelView } from "../views/panel/contract";
import { Presenter } from "./Presenter";

export interface PanelCommands {
  fitView(): void;
}

export class PanelPresenter extends Presenter {
  /** Slider range of the last loaded dataset, kept while the next one loads. */
  private maxP = 1;

  constructor(
    private readonly view: IPanelView,
    private readonly workspace: Workspace,
    commands: PanelCommands,
  ) {
    super(view);
    const { session, params } = workspace;
    view.bind({
      datasetChosen: (name) => void workspace.open(name),
      noiseChanged: (p) => params.setNoise(p),
      variationChanged: (p) => params.setVariation(p),
      variationLimitToggled: (on) => (on ? params.setVariation(this.maxP) : params.unlimitVariation()),
      optionsChanged: (patch) => params.setOptions(patch),
      fitRequested: () => commands.fitView(),
    });
    this.listen(session.subscribe(() => this.invalidate()), params.subscribe(() => this.invalidate()));
    this.invalidate();
  }

  protected present(): void {
    const { session, params } = this.workspace;
    const data = session.data;
    if (data) this.maxP = maxFinitePersistence(data) || 1;
    const load = session.state.load;
    this.view.render({
      datasets: session.entries.map((e) => e.name),
      dataset: load.status === "idle" ? "" : load.name,
      maxP: this.maxP,
      params: params.state,
    });
  }
}

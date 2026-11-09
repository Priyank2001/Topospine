/**
 * Composition root: the only module that knows every concrete class. It builds models,
 * services, views and presenters, wires them, starts the workspace, and disposes everything
 * on hot reload. No logic lives here.
 *
 *   views --intents--> presenters --methods--> models (Session, SpineParams, Selection)
 *   models --change--> presenters --view models--> views
 */

import "./styles.css";
import { SelectionModel } from "./model/SelectionModel";
import { SessionModel } from "./model/SessionModel";
import { SpineFrames } from "./model/SpineFrames";
import { SpineParamsModel } from "./model/SpineParamsModel";
import { Workspace } from "./model/Workspace";
import { PanelPresenter } from "./presenters/PanelPresenter";
import { PlotPresenter } from "./presenters/PlotPresenter";
import { Disposable } from "./presenters/Presenter";
import { SelectionPresenter } from "./presenters/SelectionPresenter";
import { SpinePresenter } from "./presenters/SpinePresenter";
import { StatsPresenter } from "./presenters/StatsPresenter";
import { StatusPresenter } from "./presenters/StatusPresenter";
import { HttpDatasetSource } from "./services/HttpDatasetSource";
import { LilGuiPanelView } from "./views/panel/LilGuiPanelView";
import { PersistencePlotView } from "./views/plot/PersistencePlotView";
import { SelectionListView } from "./views/selection/SelectionListView";
import { SpineView } from "./views/spine/SpineView";
import { StatsListView } from "./views/stats/StatsListView";
import { TextView } from "./views/text/TextView";

const byId = <T extends HTMLElement>(id: string) => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id} missing from index.html`);
  return el as T;
};

function compose(): { workspace: Workspace; presenters: Disposable[] } {
  const session = new SessionModel();
  const params = new SpineParamsModel();
  const selection = new SelectionModel();
  const workspace = new Workspace(new HttpDatasetSource(`${import.meta.env.BASE_URL}data/`), session, params, selection);
  const frames = new SpineFrames(session, params);

  const spine = new SpinePresenter(new SpineView(byId<HTMLCanvasElement>("spine-canvas")), frames, session, params, selection);
  const presenters: Disposable[] = [
    spine,
    new PlotPresenter(new PersistencePlotView(byId<HTMLCanvasElement>("persistence-plot")), session, params, selection),
    new SelectionPresenter(new SelectionListView(byId("selection")), frames, session, params, selection),
    new PanelPresenter(new LilGuiPanelView(byId("panel")), workspace, { fitView: () => spine.fitView() }),
    new StatsPresenter(new StatsListView(byId("stats")), frames, session, params),
    new StatusPresenter(new TextView(byId("status"), true), new TextView(byId("dataset-line")), frames, session, params),
  ];
  return { workspace, presenters };
}

try {
  const { workspace, presenters } = compose();
  // ?dataset=name opens a specific dataset (handy for demos and screenshots)
  void workspace.start(new URLSearchParams(location.search).get("dataset"));
  if (import.meta.hot) import.meta.hot.dispose(() => presenters.forEach((p) => p.dispose())); // no GPU leaks during development
} catch (err) {
  byId("status").textContent = `Startup failed: ${err instanceof Error ? err.message : String(err)}`;
  byId("status").hidden = false;
  console.error(err);
}

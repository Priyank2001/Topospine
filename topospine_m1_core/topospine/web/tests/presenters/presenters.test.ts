import { describe, expect, it } from "vitest";
import { maxFinitePersistence, suggestNoiseThreshold } from "../../src/core/thresholds";
import { PanelPresenter } from "../../src/presenters/PanelPresenter";
import { PlotPresenter } from "../../src/presenters/PlotPresenter";
import { SpinePresenter } from "../../src/presenters/SpinePresenter";
import { StatsPresenter } from "../../src/presenters/StatsPresenter";
import { NO_DATASETS, StatusPresenter } from "../../src/presenters/StatusPresenter";
import { entry, flush } from "../fakes";
import { FakePanelView, FakePlotView, FakeSpineView, FakeStatsView, FakeTextView } from "./fakeViews";
import { models } from "./setup";

describe("SpinePresenter", () => {
  it("renders nothing until a dataset is ready, then renders and fits once", async () => {
    const m = models();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    await flush();
    expect(view.renders).toHaveLength(0);
    await m.open("ring");
    expect(view.renders).toHaveLength(1);
    expect(view.fits).toBe(1);
    expect(view.last!.levelFills).toHaveLength(view.last!.geometry.levels.length);
  });

  it("coalesces the dataset + threshold change of one open into a single render", async () => {
    const m = models();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    let notifications = 0;
    m.session.subscribe(() => notifications++);
    m.params.subscribe(() => notifications++);
    await m.open("ring");
    expect(notifications).toBeGreaterThanOrEqual(3); // index, loading, thresholds, ready
    expect(view.renders).toHaveLength(1);
  });

  it("toggling a display option re-renders without repacking the overlay or refitting", async () => {
    const m = models();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    await m.open("ring");
    const first = view.last!;
    m.params.setOptions({ showNodes: false });
    await flush();
    expect(view.last!.showNodes).toBe(false);
    expect(view.last!.overlay).toBe(first.overlay);
    expect(view.fits).toBe(1);
  });

  it("fits again when another dataset opens", async () => {
    const m = models();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    await m.open("ring");
    await m.open("line");
    expect(view.fits).toBe(2);
  });

  it("dispose() stops rendering and disposes the view", async () => {
    const m = models();
    const view = new FakeSpineView();
    const p = new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    p.dispose();
    await m.open("ring");
    expect(view.renders).toHaveLength(0);
    expect(view.disposed).toBe(true);
  });
});

describe("PlotPresenter", () => {
  it("shows the dataset's curves and the current thresholds with labels", async () => {
    const m = models();
    const view = new FakePlotView();
    new PlotPresenter(view, m.session, m.params, m.selection);
    await m.open("ring");
    const vm = view.last!;
    expect(vm.t).toHaveLength(vm.extrema.length);
    expect(vm.pLo).toBe(suggestNoiseThreshold(m.fixtures.ring));
    expect(vm.hiLabel).toBe("variation ∞");
  });

  it("dragging the noise line past the variation line is clamped by the model", async () => {
    const m = models();
    const view = new FakePlotView();
    new PlotPresenter(view, m.session, m.params, m.selection);
    await m.open("ring");
    view.events.variationDragged(0.2);
    view.events.noiseDragged(0.9);
    await flush();
    expect(view.last).toMatchObject({ pLo: 0.2, pHi: 0.2 });
  });

  it("reuses the curves while only thresholds change", async () => {
    const m = models();
    const view = new FakePlotView();
    new PlotPresenter(view, m.session, m.params, m.selection);
    await m.open("ring");
    const t = view.last!.t;
    view.events.noiseDragged(0.01);
    await flush();
    expect(view.last!.t).toBe(t);
  });
});

describe("PanelPresenter", () => {
  it("lists datasets and sizes the sliders to the open dataset", async () => {
    const m = models();
    const view = new FakePanelView();
    new PanelPresenter(view, m.workspace, { fitView: () => {} });
    await m.open("ring");
    expect(view.last).toMatchObject({ datasets: ["ring", "line"], dataset: "ring", maxP: maxFinitePersistence(m.fixtures.ring) || 1 });
  });

  it("turning the variation limit on puts pHi at the slider's end; off makes it unlimited", async () => {
    const m = models();
    const view = new FakePanelView();
    new PanelPresenter(view, m.workspace, { fitView: () => {} });
    await m.open("ring");
    view.events.variationLimitToggled(true);
    expect(m.params.state.pHi).toBe(view.last!.maxP);
    view.events.variationLimitToggled(false);
    expect(m.params.state.pHi).toBe(Infinity);
  });

  it("choosing a dataset opens it; fit is forwarded as a command", async () => {
    const m = models();
    const view = new FakePanelView();
    let fits = 0;
    new PanelPresenter(view, m.workspace, { fitView: () => fits++ });
    await m.open("ring");
    view.events.datasetChosen("line");
    expect(m.session.state.load).toMatchObject({ status: "loading", name: "line" });
    view.events.fitRequested();
    expect(fits).toBe(1);
  });

  it("options go straight to the model", async () => {
    const m = models();
    const view = new FakePanelView();
    new PanelPresenter(view, m.workspace, { fitView: () => {} });
    view.events.optionsChanged({ radiusMode: "linear" });
    expect(m.params.state.radiusMode).toBe("linear");
  });
});

describe("StatsPresenter", () => {
  it("renders the frame's counts as rows", async () => {
    const m = models();
    const view = new FakeStatsView();
    new StatsPresenter(view, m.frames, m.session, m.params);
    await m.open("ring");
    const r = m.frames.current();
    if (r.status !== "ok") throw new Error("frame expected");
    expect(view.last![0]).toEqual(["Extrema shown", String(r.frame.display.numExtrema)]);
  });
});

describe("StatusPresenter", () => {
  function make() {
    const m = models();
    const status = new FakeTextView();
    const line = new FakeTextView();
    new StatusPresenter(status, line, m.frames, m.session, m.params);
    return { m, status, line };
  }

  it("says loading, then clears and describes the dataset", async () => {
    const { m, status, line } = make();
    void m.workspace.start("ring");
    await flush();
    expect(status.last).toBe("Loading ring…");
    m.source.resolve("ring", m.fixtures.ring);
    await flush();
    expect(status.last).toBe("");
    expect(line.last).toMatch(/^.+: .+ grid, maxima graph, 12 extrema before simplification$/);
  });

  it("explains an empty index and a failed load", async () => {
    const { m, status } = make();
    m.session.setIndex([]);
    await flush();
    expect(status.last).toBe(NO_DATASETS);
    m.session.setIndex([entry("ring")]);
    const id = m.session.beginLoad("ring");
    m.session.failLoad(id, "HTTP 404");
    await flush();
    expect(status.last).toBe("Could not load ring: HTTP 404");
  });
});

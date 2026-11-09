import { describe, expect, it } from "vitest";
import { PlotPresenter } from "../../src/presenters/PlotPresenter";
import { HINT_EMPTY, SelectionPresenter } from "../../src/presenters/SelectionPresenter";
import { SpinePresenter } from "../../src/presenters/SpinePresenter";
import { flush } from "../fakes";
import { A, B, C, S1 } from "../helpers";
import { FakePlotView, FakeSelectionView, FakeSpineView } from "./fakeViews";
import { models } from "./setup";

/** The worked example, opened at pLo = 0 so every extremum is drawn. */
async function lineAtZero() {
  const m = models();
  await m.open("line");
  m.params.setThresholds(0, Infinity);
  await flush();
  return m;
}

describe("SpinePresenter + selection", () => {
  it("view intents drive the selection model", async () => {
    const m = await lineAtZero();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    view.events.nodeHovered(C);
    view.events.nodeClicked(A, false);
    view.events.nodeClicked(B, true);
    expect(m.selection.state.hovered).toBe(C);
    expect([...m.selection.state.selected]).toEqual([A, B]);
    view.events.cleared();
    expect(m.selection.state.selected.size).toBe(0);
  });

  it("a selection change sends rings only, never the spine again", async () => {
    const m = await lineAtZero();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    await flush();
    const renders = view.renders.length;
    m.selection.selectOnly(A);
    await flush();
    m.selection.hover(C);
    await flush();
    expect(view.renders.length).toBe(renders);
    expect(view.highlights.at(-1)).toEqual([{ node: A, style: "selected" }, { node: C, style: "hovered" }]);
  });

  it("raising pLo turns a selected peak's ring into a stand-in on its representative", async () => {
    const m = await lineAtZero();
    const view = new FakeSpineView();
    new SpinePresenter(view, m.frames, m.session, m.params, m.selection);
    m.selection.selectOnly(B);
    m.params.setNoise(1.5);
    await flush();
    expect(view.highlights.at(-1)).toEqual([{ node: A, style: "standIn" }]);
    expect([...m.selection.state.selected]).toEqual([B]); // the pick itself is kept
  });
});

describe("PlotPresenter + selection", () => {
  it("ticks at the persistence of selected and hovered nodes", async () => {
    const m = await lineAtZero();
    const view = new FakePlotView();
    new PlotPresenter(view, m.session, m.params, m.selection);
    const d = m.fixtures.line;
    m.selection.selectOnly(B);
    m.selection.hover(C);
    await flush();
    expect(view.last!.marks).toEqual([
      { p: d.persistence[B], kind: "selected" },
      { p: d.persistence[C], kind: "hovered" },
    ]);
  });
});

describe("SelectionPresenter", () => {
  it("shows the hint until something is selected", async () => {
    const m = await lineAtZero();
    const view = new FakeSelectionView();
    new SelectionPresenter(view, m.frames, m.session, m.params, m.selection);
    await flush();
    expect(view.last).toEqual({ hovered: null, selected: [], hint: HINT_EMPTY });
  });

  it("describes picks, and says what a merged or hidden pick became", async () => {
    const m = await lineAtZero();
    const view = new FakeSelectionView();
    new SelectionPresenter(view, m.frames, m.session, m.params, m.selection);
    m.selection.selectOnly(B);
    m.selection.toggle(S1);
    m.selection.hover(A);
    m.params.setNoise(1.5);
    await flush();
    const vm = view.last!;
    expect(vm.hovered).toMatchObject({ title: "max #0", note: "" });
    expect(vm.hovered!.detail).toBe(`f 5.0 · P 3.0 · ${m.frames.selectionContext()!.regions.sizes[A]} samples`);
    expect(vm.selected.map((r) => [r.title, r.note])).toEqual([
      ["max #1", "merged into max #0 at this noise threshold"],
      ["saddle #4", "hidden at current thresholds"],
    ]);
    expect(vm.hint).toMatch(/^2 selected/);
  });
});

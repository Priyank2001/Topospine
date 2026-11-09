import { describe, expect, it } from "vitest";
import { suggestNoiseThreshold } from "../../src/core/thresholds";
import { SelectionModel } from "../../src/model/SelectionModel";
import { SessionModel } from "../../src/model/SessionModel";
import { SpineParamsModel } from "../../src/model/SpineParamsModel";
import { Workspace } from "../../src/model/Workspace";
import { ControlledSource, entry, flush } from "../fakes";
import { loadFixture } from "../helpers";

function setup(failIndex = false) {
  const source = new ControlledSource([entry("ring"), entry("line")], failIndex);
  const session = new SessionModel();
  const params = new SpineParamsModel();
  const selection = new SelectionModel();
  return { source, session, params, selection, ws: new Workspace(source, session, params, selection) };
}

describe("Workspace", () => {
  const ring = loadFixture("ring");
  const line = loadFixture("line");

  it("start() lists datasets and opens the requested one", async () => {
    const { source, session, ws } = setup();
    void ws.start("line");
    await flush();
    expect(session.entries.map((e) => e.name)).toEqual(["ring", "line"]);
    expect(session.state.load).toMatchObject({ status: "loading", name: "line" });
    source.resolve("line", line);
    await flush();
    expect(session.data).toBe(line);
  });

  it("reports an unreachable index as an error state", async () => {
    const { session, ws } = setup(true);
    await ws.start();
    expect(session.state.index).toEqual({ status: "error", message: "index unreachable" });
  });

  it("resets thresholds before the session publishes ready", async () => {
    const { source, session, params, ws } = setup();
    params.setThresholds(99, 99);
    let pLoWhenReady = NaN;
    session.subscribe((s) => {
      if (s.load.status === "ready") pLoWhenReady = params.state.pLo;
    });
    void ws.open("ring");
    source.resolve("ring", ring);
    await flush();
    expect(pLoWhenReady).toBe(suggestNoiseThreshold(ring));
  });

  it("clears the selection before the new dataset is published", async () => {
    const { source, session, selection, ws } = setup();
    selection.selectOnly(3);
    selection.hover(4);
    let selectedWhenReady = -1;
    session.subscribe((s) => {
      if (s.load.status === "ready") selectedWhenReady = selection.state.selected.size;
    });
    void ws.open("ring");
    source.resolve("ring", ring);
    await flush();
    expect(selectedWhenReady).toBe(0);
    expect(selection.state.hovered).toBeNull();
  });

  it("a slow first load never replaces a later choice or its thresholds", async () => {
    const { source, session, params, ws } = setup();
    void ws.open("ring");
    void ws.open("line");
    source.resolve("line", line);
    await flush();
    params.setThresholds(0.5, 0.7); // user adjusts the newer dataset
    source.resolve("ring", ring); // the old request finally arrives
    await flush();
    expect(session.state.load).toMatchObject({ status: "ready", name: "line" });
    expect(params.state).toMatchObject({ pLo: 0.5, pHi: 0.7 });
  });

  it("a failed load becomes an error state", async () => {
    const { source, session, ws } = setup();
    void ws.open("ring");
    source.reject("ring", "HTTP 500");
    await flush();
    expect(session.state.load).toEqual({ status: "error", name: "ring", message: "HTTP 500" });
  });
});

import { describe, expect, it } from "vitest";
import { SessionModel } from "../../src/model/SessionModel";
import { SpineFrames } from "../../src/model/SpineFrames";
import { SpineParamsModel } from "../../src/model/SpineParamsModel";
import { loadFixture } from "../helpers";

function ready() {
  const session = new SessionModel();
  const params = new SpineParamsModel();
  const ring = loadFixture("ring");
  params.resetForDataset(ring); // as Workspace does: keeps the layout small
  session.finishLoad(session.beginLoad("ring"), ring);
  return { session, params, frames: new SpineFrames(session, params) };
}

describe("SpineFrames", () => {
  it("is none until a dataset is ready", () => {
    expect(new SpineFrames(new SessionModel(), new SpineParamsModel()).current()).toEqual({ status: "none" });
  });

  it("returns the same frame object for the same state (shared by presenters)", () => {
    const { frames } = ready();
    const a = frames.current();
    expect(a.status).toBe("ok");
    expect(frames.current()).toBe(a);
  });

  it("recomputes when params change", () => {
    const { frames, params } = ready();
    const a = frames.current();
    params.setOptions({ glyphScale: 1.5 });
    expect(frames.current()).not.toBe(a);
  });
});

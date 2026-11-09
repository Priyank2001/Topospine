import { describe, expect, it } from "vitest";
import { SessionModel } from "../../src/model/SessionModel";
import { entry } from "../fakes";
import { loadFixture } from "../helpers";

describe("SessionModel", () => {
  const ring = loadFixture("ring");

  it("starts with the index loading and nothing open", () => {
    const s = new SessionModel();
    expect(s.state.index.status).toBe("loading");
    expect(s.state.load.status).toBe("idle");
    expect(s.data).toBeUndefined();
  });

  it("picks the requested dataset if listed, else the first", () => {
    const s = new SessionModel();
    s.setIndex([entry("a"), entry("b")]);
    expect(s.initialDataset("b")).toBe("b");
    expect(s.initialDataset("zzz")).toBe("a");
    expect(s.initialDataset(null)).toBe("a");
  });

  it("goes loading -> ready", () => {
    const s = new SessionModel();
    const id = s.beginLoad("ring");
    expect(s.state.load).toMatchObject({ status: "loading", name: "ring" });
    expect(s.finishLoad(id, ring)).toBe(true);
    expect(s.state.load).toMatchObject({ status: "ready", name: "ring" });
    expect(s.data).toBe(ring);
  });

  it("ignores a stale request finishing after a newer one started", () => {
    const s = new SessionModel();
    const first = s.beginLoad("a");
    const second = s.beginLoad("b");
    expect(s.finishLoad(first, ring)).toBe(false);
    expect(s.failLoad(first, "late")).toBe(false);
    expect(s.state.load).toMatchObject({ status: "loading", name: "b" });
    s.finishLoad(second, ring);
    expect(s.state.load).toMatchObject({ status: "ready", name: "b" });
  });

  it("records a failure with the dataset name", () => {
    const s = new SessionModel();
    const id = s.beginLoad("a");
    s.failLoad(id, "HTTP 404");
    expect(s.state.load).toEqual({ status: "error", name: "a", message: "HTTP 404" });
  });
});

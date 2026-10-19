import { describe, expect, it } from "vitest";
import { SpinePipeline, memo } from "../../src/core/derive";
import { DEFAULT_PARAMS } from "../../src/core/spineState";
import { Store } from "../../src/core/store";
import { loadFixture } from "../helpers";

describe("memo", () => {
  it("recomputes only when an argument changes identity", () => {
    const f = memo((a: number, b: object) => ({ a, b }));
    const o = {};
    const r1 = f(1, o);
    expect(f(1, o)).toBe(r1);
    f(1, {});
    expect(f.calls()).toBe(2);
  });
});

describe("Store", () => {
  it("notifies on change only", () => {
    const s = new Store({ x: 1, y: 2 });
    let n = 0;
    s.subscribe(() => n++);
    s.set({ x: 1 });
    s.set({ x: 3 });
    expect(n).toBe(1);
    expect(s.get().x).toBe(3);
  });
});

describe("SpinePipeline", () => {
  const ring = loadFixture("ring");

  it("moving pHi doesn't recompute representatives or merged regions", () => {
    const p = new SpinePipeline(ring);
    p.frame({ ...DEFAULT_PARAMS, pLo: 0.05 });
    p.frame({ ...DEFAULT_PARAMS, pLo: 0.05, pHi: 0.5 });
    expect(p.rep.calls()).toBe(1);
    expect(p.merged.calls()).toBe(1);
    expect(p.visibility.calls()).toBe(2);
  });

  it("changing glyph scale reuses the layout", () => {
    const p = new SpinePipeline(ring);
    const f1 = p.frame({ ...DEFAULT_PARAMS, pLo: 0.05, saturation: "cancel" });
    const f2 = p.frame({ ...DEFAULT_PARAMS, pLo: 0.05, saturation: "cancel", glyphScale: 1.2 });
    expect(f2.layout).toBe(f1.layout);
    expect(p.layout.calls()).toBe(1);
    expect(f2.geometry).not.toBe(f1.geometry);
  });

  it("warm start keeps surviving nodes close to where they were", () => {
    const p = new SpinePipeline(ring);
    const params = { ...DEFAULT_PARAMS, pLo: 0.05, saturation: "cancel" as const };
    const f1 = p.frame(params);
    const f2 = p.frame({ ...params, pLo: 0.06 });
    let drift = 0, span = 0;
    for (const [id, [x, y]] of f2.layout) {
      const old = f1.layout.get(id);
      if (old) drift = Math.max(drift, Math.hypot(x - old[0], y - old[1]));
      span = Math.max(span, Math.hypot(x, y));
    }
    expect(drift).toBeLessThan(0.1 * span);
  });

  it("produces one geometry array per level with finite numbers", () => {
    const f = new SpinePipeline(ring).frame({ ...DEFAULT_PARAMS, pLo: 0.05, saturation: "cancel" });
    expect(f.geometry.pieces.length).toBe(f.geometry.levels.length);
    expect(f.geometry.levels.length).toBeGreaterThan(1);
    for (const arr of f.geometry.pieces) expect(arr.every(Number.isFinite)).toBe(true);
    expect(f.display.numExtrema).toBe(6);
  });
});

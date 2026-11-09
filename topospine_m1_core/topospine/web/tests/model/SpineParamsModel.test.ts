import { describe, expect, it } from "vitest";
import { suggestNoiseThreshold } from "../../src/core/thresholds";
import { SpineParamsModel } from "../../src/model/SpineParamsModel";
import { loadFixture } from "../helpers";

describe("SpineParamsModel", () => {
  it("setThresholds raises pHi to pLo", () => {
    const m = new SpineParamsModel();
    m.setThresholds(5, 2);
    expect(m.state).toMatchObject({ pLo: 5, pHi: 5 });
  });

  it("setNoise cannot pass the variation threshold", () => {
    const m = new SpineParamsModel();
    m.setThresholds(1, 3);
    m.setNoise(10);
    expect(m.state).toMatchObject({ pLo: 3, pHi: 3 });
  });

  it("setVariation cannot drop below the noise threshold, and Infinity means unlimited", () => {
    const m = new SpineParamsModel();
    m.setThresholds(2, 4);
    m.setVariation(1);
    expect(m.state.pHi).toBe(2);
    m.setVariation(Infinity);
    expect(m.state.pHi).toBe(Infinity);
  });

  it("rejects negative and NaN thresholds", () => {
    const m = new SpineParamsModel();
    m.setThresholds(-1, NaN);
    expect(m.state).toMatchObject({ pLo: 0, pHi: 0 });
    m.setNoise(NaN);
    expect(m.state.pLo).toBe(0);
  });

  it("unlimitVariation keeps pLo", () => {
    const m = new SpineParamsModel();
    m.setThresholds(2, 4);
    m.unlimitVariation();
    expect(m.state).toMatchObject({ pLo: 2, pHi: Infinity });
  });

  it("resetForDataset starts at the suggested noise threshold with no variation limit", () => {
    const ring = loadFixture("ring");
    const m = new SpineParamsModel();
    m.setThresholds(9, 9);
    m.resetForDataset(ring);
    expect(m.state).toMatchObject({ pLo: suggestNoiseThreshold(ring), pHi: Infinity });
  });

  it("does not notify when nothing changes", () => {
    const m = new SpineParamsModel();
    let n = 0;
    m.subscribe(() => n++);
    m.setOptions({ glyphScale: 0.8 });
    m.setOptions({ glyphScale: 0.8 });
    expect(n).toBe(1);
  });
});

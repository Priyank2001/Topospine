import { describe, expect, it } from "vitest";
import { arcCurve, extremaCurve, filterGraph, maxFinitePersistence, representatives, suggestNoiseThreshold } from "../../src/core/thresholds";
import { A, B, C, D, S1, S2, S3, loadFixture } from "../helpers";

const d = loadFixture("line");
const kept = (m: Uint8Array) => new Set(Array.from(m).flatMap((v, i) => (v ? [i] : [])));
const keptArcs = (m: Uint8Array) =>
  new Set(Array.from(m).flatMap((v, a) => (v ? [`${d.arcSaddle[a]}-${d.arcExtremum[a]}`] : [])));

describe("Eqs. 1-3 (same table as the Python tests)", () => {
  it("full range keeps everything", () => {
    const v = filterGraph(d, 0, Infinity);
    expect(kept(v.node).size).toBe(7);
    expect(kept(v.arc).size).toBe(6);
  });

  it("R = [1.5, inf]: B and s1 go, s1's ridge arcs stay (P* = 3)", () => {
    const v = filterGraph(d, 1.5, Infinity);
    expect(kept(v.node)).toEqual(new Set([A, C, D, S2, S3]));
    expect(keptArcs(v.arc).has(`${S1}-${A}`)).toBe(true);
  });

  it("R = [2.5, inf]: s3's arcs go (P* = 2)", () => {
    const v = filterGraph(d, 2.5, Infinity);
    expect(kept(v.node)).toEqual(new Set([A, C, S2]));
    expect(keptArcs(v.arc)).toEqual(new Set([`${S1}-${A}`, `${S1}-${B}`, `${S2}-${B}`, `${S2}-${C}`]));
  });

  it("R = [0, 2.5]: the variation threshold splits the graph at s2", () => {
    const v = filterGraph(d, 0, 2.5);
    expect(kept(v.node)).toEqual(new Set([A, B, C, D, S1, S3]));
    expect(keptArcs(v.arc)).toEqual(new Set([`${S1}-${A}`, `${S1}-${B}`, `${S3}-${C}`, `${S3}-${D}`]));
  });

  it("rejects pLo > pHi", () => {
    expect(() => filterGraph(d, 2, 1)).toThrow(RangeError);
  });
});

describe("representatives", () => {
  it.each([
    [0, [A, A, A, B, C, C, C, D, D]],
    [1.5, [A, A, A, A, C, C, C, D, D]],
    [2.5, [A, A, A, A, C, C, C, C, C]],
    [3.5, [C, C, C, C, C, C, C, C, C]],
  ])("pLo = %s", (pLo, expected) => {
    const rep = representatives(d, pLo);
    expect(Array.from(d.labels, (l) => rep[l])).toEqual(expected);
  });
});

describe("curves", () => {
  it("match the Python values", () => {
    const t = [0, 1, 1.5, 2.5, 3, 3.5];
    expect(Array.from(extremaCurve(d, t))).toEqual([4, 4, 3, 2, 2, 1]);
    expect(Array.from(arcCurve(d, t))).toEqual([0, 2, 2, 4, 6, 6]);
    expect(maxFinitePersistence(d)).toBe(3);
  });
});

describe("suggestNoiseThreshold", () => {
  it("lands in the gap between noise and the six hills of the ring", () => {
    const ring = loadFixture("ring");
    const t = suggestNoiseThreshold(ring);
    const P = Array.from({ length: ring.numRegions }, (_, i) => ring.persistence[i]);
    expect(P.filter((p) => p >= t).length).toBe(6);            // exactly the hills survive
  });

  it("falls back to 1 % of the largest persistence without a clear gap", () => {
    expect(suggestNoiseThreshold(d)).toBeCloseTo(0.03);          // line: 1, 2, 3 -> no ratio >= 3
  });
});

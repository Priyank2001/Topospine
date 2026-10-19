import { describe, expect, it } from "vitest";
import { pca2 } from "../../src/core/layout/pca";
import { DEFAULT_STRESS, pairwiseDistances, stress, stressLayout, weights } from "../../src/core/layout/stress";

describe("pca2", () => {
  it("points on a 3-D line land on the first axis with distances kept", () => {
    const pos = Float64Array.from([0, 0, 0, 1, 2, 2, 2, 4, 4]); // spacing 3 along (1,2,2)/3
    const out = pca2(pos, 3, 3);
    expect(Math.abs(out[1]) + Math.abs(out[3]) + Math.abs(out[5])).toBeLessThan(1e-9); // no second axis
    expect(Math.abs(out[2] - out[0])).toBeCloseTo(3);                                  // distance preserved
  });

  it("keeps 2-D positions unrotated (only centred)", () => {
    expect(Array.from(pca2(Float64Array.from([0, 0, 4, 2]), 2, 2))).toEqual([-2, -1, 2, 1]);
  });

  it("is deterministic and sign-stable", () => {
    const pos = Float64Array.from([0, 0, 4, 1, 1, 3, 2, 2, 0]);
    expect(Array.from(pca2(pos, 3, 3))).toEqual(Array.from(pca2(pos, 3, 3)));
  });

  it("handles 1-D positions and empty input", () => {
    const out = Array.from(pca2(Float64Array.from([0, 2, 5]), 3, 1));
    [-7 / 3, 0, -1 / 3, 0, 8 / 3, 0].forEach((v, i) => expect(out[i]).toBeCloseTo(v));
    expect(pca2(new Float64Array(0), 0, 2).length).toBe(0);
  });
});

describe("stressLayout", () => {
  const triangle = () => {
    const target = Float64Array.from([0, 3, 4, 3, 0, 5, 4, 5, 0]); // 3-4-5 right triangle
    return { n: 3, target, edges: [[0, 1], [0, 2]] as [number, number][], init: Float64Array.from([0, 0, 1, 0.1, 0.2, 1]) };
  };

  it("recovers a triangle that has an exact 2-D embedding", () => {
    const res = stressLayout(triangle());
    const p = res.position;
    const dist = (i: number, j: number) => Math.hypot(p[2 * i] - p[2 * j], p[2 * i + 1] - p[2 * j + 1]);
    expect(dist(0, 1)).toBeCloseTo(3, 3);
    expect(dist(0, 2)).toBeCloseTo(4, 3);
    expect(dist(1, 2)).toBeCloseTo(5, 3);
  });

  it("never increases stress (majorization guarantee)", () => {
    const inp = triangle();
    const w = weights(inp, DEFAULT_STRESS.edgeWeight);
    let pos = inp.init;
    let prev = stress(pos, inp.target, w, 3);
    for (let k = 0; k < 10; k++) {
      pos = stressLayout({ ...inp, init: pos }, { ...DEFAULT_STRESS, maxIterations: 1 }).position;
      const cur = stress(pos, inp.target, w, 3);
      expect(cur).toBeLessThanOrEqual(prev + 1e-12);
      prev = cur;
    }
  });

  it("separates nodes that start on the same spot", () => {
    const inp = { ...triangle(), init: new Float64Array(6) };
    const p = stressLayout(inp).position;
    expect(Math.hypot(p[0] - p[2], p[1] - p[3])).toBeCloseTo(3, 2);
  });

  it("leaves very large graphs at their initial positions", () => {
    const inp = triangle();
    expect(Array.from(stressLayout(inp, { ...DEFAULT_STRESS, maxNodes: 2 }).position)).toEqual(Array.from(inp.init));
  });

  it("pairwise distances use the full dimension", () => {
    const pos = Float64Array.from([0, 0, 0, 0, 1, 1, 1, 1]); // two 4-D points
    expect(pairwiseDistances(pos, [0, 1], 4)[1]).toBeCloseTo(2);
  });
});

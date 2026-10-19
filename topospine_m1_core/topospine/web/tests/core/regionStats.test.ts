import { describe, expect, it } from "vitest";
import { MergedRegions } from "../../src/core/regionStats";
import { representatives } from "../../src/core/thresholds";
import { A, B, C, D, loadFixture } from "../helpers";

const d = loadFixture("line"); // unit bins over [0, 9]

describe("MergedRegions", () => {
  it("sizes per region without merging", () => {
    const r = MergedRegions.fromData(d, representatives(d, 0));
    expect(Array.from(r.sizes)).toEqual([3, 1, 3, 2]);
  });

  it("merges by representative and keeps the total", () => {
    const r = MergedRegions.fromData(d, representatives(d, 2.5));
    expect([A, B, C, D].map((i) => r.sizes[i])).toEqual([4, 0, 5, 0]);
  });

  it("counts are exact on bin edges and interpolate inside bins", () => {
    const r = MergedRegions.fromData(d, representatives(d, 0));
    // region A holds f = 1, 5, 3; between 3 and 6 -> {3, 5}
    expect(r.countBetween(A, 3, 6)).toBeCloseTo(2);
    expect(r.countBetween(A, 6, 3)).toBeCloseTo(2);
    expect(r.countAtOrAbove(B, 4.5)).toBeCloseTo(0.5);   // B holds f = 4, spread over [4, 5)
    expect(r.countAtOrAbove(C, -1)).toBe(3);
    expect(r.countAtOrAbove(C, 100)).toBe(0);
  });
});

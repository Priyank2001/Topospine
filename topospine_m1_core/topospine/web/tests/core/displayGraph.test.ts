import { describe, expect, it } from "vitest";
import { buildDisplayGraph } from "../../src/core/displayGraph";
import { filterGraph, representatives } from "../../src/core/thresholds";
import { A, B, C, D, S1, S2, S3, loadFixture } from "../helpers";

const d = loadFixture("line");

function links(pLo: number, pHi: number, dedupe = true) {
  const g = buildDisplayGraph(d, filterGraph(d, pLo, pHi), representatives(d, pLo), { dedupe });
  const ls = Array.from(g.linkSaddle, (s, i) => `${g.linkExtremum[i]}-${s}`).sort();
  return { g, ls };
}

describe("buildDisplayGraph", () => {
  it("full detail: every triplet", () => {
    const { g, ls } = links(0, Infinity);
    expect(ls).toEqual([`${A}-${S1}`, `${B}-${S1}`, `${B}-${S2}`, `${C}-${S2}`, `${C}-${S3}`, `${D}-${S3}`].sort());
    expect(g.numExtrema).toBe(4);
    expect(g.numSaddles).toBe(3);
  });

  it("R = [1.5, inf]: s1 collapses into A, s2 now joins A and C", () => {
    const { g, ls } = links(1.5, Infinity);
    expect(ls).toEqual([`${A}-${S2}`, `${C}-${S2}`, `${C}-${S3}`, `${D}-${S3}`].sort());
    expect(Array.from(g.nodes)).toEqual([A, C, D, S2, S3]);
  });

  it("R = [0, 2.5]: two separate features", () => {
    const { ls } = links(0, 2.5);
    expect(ls).toEqual([`${A}-${S1}`, `${B}-${S1}`, `${C}-${S3}`, `${D}-${S3}`].sort());
  });

  it("dedupe keeps only the highest saddle per pair of extrema", () => {
    const ring = loadFixture("ring");
    const pLo = 0.05;
    const vis = filterGraph(ring, pLo, Infinity, "cancel");
    const rep = representatives(ring, pLo);
    const all = buildDisplayGraph(ring, vis, rep, { dedupe: false });
    const one = buildDisplayGraph(ring, vis, rep, { dedupe: true });
    const pairs = new Set<string>();
    for (let i = 0; i < one.linkSaddle.length; i += 2) {
      const [a, b] = [one.linkExtremum[i], one.linkExtremum[i + 1]].sort((x, y) => x - y);
      const key = `${a}|${b}`;
      expect(pairs.has(key)).toBe(false);                    // each pair at most once
      pairs.add(key);
    }
    expect(one.numSaddles).toBeLessThanOrEqual(all.numSaddles);
    expect(one.numExtrema).toBe(6);                          // the six hills
  });
});

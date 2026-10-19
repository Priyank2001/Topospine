import { describe, expect, it } from "vitest";
import { MergedRegions } from "../../src/core/regionStats";
import { chooseLevels } from "../../src/core/spine/levels";
import { buildSpineGeometry, shapeRadius } from "../../src/core/spine/links";
import { sdTaperedCapsule } from "../../src/core/spine/sdf";
import { representatives } from "../../src/core/thresholds";
import { A, B, S1, loadFixture } from "../helpers";

describe("sdTaperedCapsule (CPU reference for the shader)", () => {
  it("equal radii = ordinary capsule", () => {
    expect(sdTaperedCapsule(0, 0, 0, 0, 1, 4, 0, 1)).toBeCloseTo(-1);   // on the axis, inside
    expect(sdTaperedCapsule(2, 3, 0, 0, 1, 4, 0, 1)).toBeCloseTo(2);    // 3 above the axis -> 2 outside
    expect(sdTaperedCapsule(6, 0, 0, 0, 1, 4, 0, 1)).toBeCloseTo(1);    // past the end cap
  });

  it("tapered side is tangent to both circles", () => {
    // circles r=2 at (0,0) and r=1 at (10,0): points on either circle are on the boundary
    expect(sdTaperedCapsule(-2, 0, 0, 0, 2, 10, 0, 1)).toBeCloseTo(0);
    expect(sdTaperedCapsule(11, 0, 0, 0, 2, 10, 0, 1)).toBeCloseTo(0);
    const mid = sdTaperedCapsule(5, 1.5, 0, 0, 2, 10, 0, 1);
    expect(mid).toBeLessThan(0.05);                                    // radius ~1.5 halfway
    expect(mid).toBeGreaterThan(-0.05);
  });

  it("one circle inside the other -> the bigger circle", () => {
    expect(sdTaperedCapsule(0, 5, 0, 0, 5, 1, 0, 1)).toBeCloseTo(0);
  });

  it("is rotation invariant", () => {
    const a = sdTaperedCapsule(1, 2, 0, 0, 1.5, 5, 0, 0.5);
    const b = sdTaperedCapsule(-2, 1, 0, 0, 1.5, 0, 5, 0.5); // rotated by 90 degrees
    expect(b).toBeCloseTo(a);
  });
});

describe("chooseLevels", () => {
  it("drops levels at/above the top, enforces the gap, caps the count", () => {
    expect(Array.from(chooseLevels([1, 1.01, 2, 3, 9, 10], 9, 10, { minGapFraction: 0.05, maxLevels: 10 }))).toEqual([1, 2, 3]);
    const many = Array.from({ length: 100 }, (_, i) => i);
    const out = chooseLevels(many, 1000, 100, { minGapFraction: 0, maxLevels: 5 });
    expect(Array.from(out)).toEqual([0, 25, 50, 74, 99]);
  });
});

describe("canonical links", () => {
  const d = loadFixture("line");
  const regions = MergedRegions.fromData(d, representatives(d, 0));
  const pos = (n: number): [number, number] => [d.position[n], 0];

  it("critical contour pinches at the saddle (figure eight)", () => {
    const geo = buildSpineGeometry(d, regions, { linkExtremum: [A], linkSaddle: [S1], pos }, Float64Array.from([3]),
      { knots: 4, mode: "linear", glyphScale: 1 });
    const p = geo.pieces[0];
    expect(p[p.length - 1]).toBe(0);                    // radius at the saddle end
    expect(p[2]).toBeGreaterThan(0);                    // radius at the extremum
  });

  it("contours above the saddle stop where g reaches c, with radius 0 there", () => {
    // On the 9-sample line the blob above a saddle holds no samples (the strict interval
    // excludes the peak itself), so use the ring: a real link with c between g(s) and g(u).
    const ring = loadFixture("ring");
    const rep = representatives(ring, 0.05);
    const r = MergedRegions.fromData(ring, rep);
    const s = Array.from({ length: ring.numNodes }, (_, i) => i).find(
      (i) => ring.kind[i] === 1 && rep[ring.arcExtremum[ring.saddleArcs[2 * i]]] !== rep[ring.arcExtremum[ring.saddleArcs[2 * i + 1]]],
    )!;
    const u = rep[ring.arcExtremum[ring.saddleArcs[2 * s]]];
    const gu = ring.value[u], gs = ring.value[s];
    const c = gs + 0.25 * (gu - gs);                    // reached at t = 0.75
    const pos2 = (n: number): [number, number] => (n === u ? [0, 0] : [10, 0]);
    const geo = buildSpineGeometry(ring, r, { linkExtremum: [u], linkSaddle: [s], pos: pos2 }, Float64Array.from([c]),
      { knots: 4, mode: "linear", glyphScale: 1 });
    const p = geo.pieces[0];
    expect(p.length).toBeGreaterThan(0);
    expect(p[p.length - 3]).toBeCloseTo(7.5);           // end x = 0.75 * 10
    expect(p[p.length - 1]).toBe(0);
    expect(p[2]).toBeGreaterThan(0);                    // blob around the extremum
  });

  it("no shape for levels at or above the extremum", () => {
    const geo = buildSpineGeometry(d, regions, { linkExtremum: [B], linkSaddle: [S1], pos }, Float64Array.from([4]),
      { knots: 4, mode: "linear", glyphScale: 1 });
    expect(geo.pieces[0].length).toBe(0);               // B has f = 4
  });

  it("nesting: lower isovalues never give smaller radii (paper Sec. 4.3)", () => {
    const ring = loadFixture("ring");
    const r = MergedRegions.fromData(ring, representatives(ring, 0.05));
    for (const u of [0, 1, 2, 3, 4, 5].map((k) => k * 20).filter((u) => u < ring.numRegions)) {
      for (let gp = 0.2; gp <= 1.2; gp += 0.1) {
        let prev = Infinity;
        for (let c = 0; c <= gp; c += 0.05) {             // c rising -> radius must not grow
          const rad = shapeRadius(ring, r, u, c, gp, "linear");
          expect(rad).toBeLessThanOrEqual(prev + 1e-9);
          prev = rad;
        }
      }
    }
  });

  it("minimum graphs use heights g = -f", () => {
    const ack = loadFixture("ackley");
    const r = MergedRegions.fromData(ack, representatives(ack, 0));
    const u = 0;
    const gu = -ack.value[u];
    expect(shapeRadius(ack, r, u, gu - 0.5, gu, "linear")).toBeGreaterThan(0);  // samples above the minimum
    expect(shapeRadius(ack, r, u, gu, gu, "linear")).toBe(0);
  });
});

describe("extra levels", () => {
  it("adds evenly spaced isovalues between the lowest candidate and the top", () => {
    const out = chooseLevels([0, 10], 10, 10, { minGapFraction: 0, maxLevels: 10, extraLevels: 4 });
    expect(Array.from(out)).toEqual([0, 2, 4, 6, 8]);
  });
});

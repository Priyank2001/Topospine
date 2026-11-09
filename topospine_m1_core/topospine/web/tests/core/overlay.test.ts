import { describe, expect, it } from "vitest";
import { buildDisplayGraph } from "../../src/core/displayGraph";
import { fmt, fmtThreshold } from "../../src/core/format";
import { levelFills } from "../../src/core/spine/levelColors";
import { buildOverlay } from "../../src/core/spine/overlay";
import { filterGraph, representatives } from "../../src/core/thresholds";
import { viridis } from "../../src/core/colormap";
import { A, C, D, S2, S3, loadFixture } from "../helpers";

describe("buildOverlay", () => {
  const line = loadFixture("line");
  const g = buildDisplayGraph(line, filterGraph(line, 1.5, Infinity), representatives(line, 1.5));
  const layout = new Map<number, [number, number]>(Array.from(g.nodes, (id) => [id, [id, -id]]));

  it("packs one segment per link and one centre + kind per node, in node order", () => {
    const o = buildOverlay(line, g, layout);
    expect(o.segments.length).toBe(4 * g.linkExtremum.length);
    expect(Array.from(o.segments.slice(0, 4))).toEqual([g.linkExtremum[0], -g.linkExtremum[0], g.linkSaddle[0], -g.linkSaddle[0]]);
    expect(Array.from(g.nodes).sort()).toEqual([A, C, D, S2, S3].sort());
    g.nodes.forEach((id, i) => {
      expect(o.centers[2 * i]).toBe(id);
      expect(o.kinds[i]).toBe(id === S2 || id === S3 ? 1 : 0);
    });
  });

  it("fails loudly if a drawn node has no position", () => {
    expect(() => buildOverlay(line, g, new Map())).toThrow(/no layout position/);
  });
});

describe("levelFills", () => {
  it("maps the bottom and top of the value range to the ends of viridis", () => {
    const line = loadFixture("line");
    const [lo, hi] = line.meta.valueRange;
    const fills = levelFills(line, [line.sign * lo, line.sign * hi]);
    expect(fills[0]).toEqual(viridis(0));
    expect(fills[1]).toEqual(viridis(1));
  });
});

describe("fmt", () => {
  it("keeps short numbers short and uses ∞ for no limit", () => {
    expect(fmt(0)).toBe("0");
    expect(fmt(0.123)).toBe("0.12");
    expect(fmt(1234)).toBe("1.2e+3");
    expect(fmtThreshold(Infinity)).toBe("∞");
  });
});

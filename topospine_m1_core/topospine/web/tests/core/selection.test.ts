import { describe, expect, it } from "vitest";
import { buildDisplayGraph } from "../../src/core/displayGraph";
import { MergedRegions } from "../../src/core/regionStats";
import { SelectionContext, describeNode, drawnNodes, highlightFor, nodeLabel } from "../../src/core/selection";
import { nearestNode } from "../../src/core/spine/pick";
import { filterGraph, representatives } from "../../src/core/thresholds";
import { A, B, C, S1, S2, loadFixture } from "../helpers";

/** The worked example f = 1 5 3 4 2 9 6 8 0 at noise threshold pLo: B (P = 1) merges into A above 1. */
function context(pLo: number): SelectionContext {
  const d = loadFixture("line");
  const rep = representatives(d, pLo);
  const g = buildDisplayGraph(d, filterGraph(d, pLo, Infinity), rep);
  return { data: d, rep, regions: MergedRegions.fromData(d, rep), drawn: drawnNodes(g) };
}

describe("describeNode", () => {
  it("a drawn extremum is visible, with its own region size", () => {
    const ctx = context(0);
    const info = describeNode(ctx, A);
    expect(info.status).toEqual({ kind: "visible" });
    expect(info.shownAs).toBe(A);
    expect(info.samples).toBe(ctx.regions.sizes[A]);
  });

  it("a merged extremum is shown as its representative, with the merged region's size", () => {
    const ctx = context(1.5);
    const info = describeNode(ctx, B);
    expect(info.status).toEqual({ kind: "merged", into: A });
    expect(info.shownAs).toBe(A);
    expect(info.samples).toBe(ctx.regions.sizes[A]);
  });

  it("a saddle that is not drawn is hidden and has no region size", () => {
    const ctx = context(1.5); // s1 joins A and B, which are one feature now: collapsed
    const info = describeNode(ctx, S1);
    expect(info.status).toEqual({ kind: "hidden" });
    expect(info.shownAs).toBeNull();
    expect(info.samples).toBeNull();
  });
});

describe("highlightFor", () => {
  it("rings selected nodes, stands in for merged ones once, and adds the hover", () => {
    const ctx = context(1.5);
    expect(highlightFor(ctx, C, [B, S1, S2])).toEqual([
      { node: S2, style: "selected" },
      { node: A, style: "standIn" },
      { node: C, style: "hovered" },
    ]);
  });

  it("no stand-in ring when the representative is itself selected", () => {
    const ctx = context(1.5);
    expect(highlightFor(ctx, null, [A, B])).toEqual([{ node: A, style: "selected" }]);
  });

  it("ignores a hovered node that is no longer drawn", () => {
    expect(highlightFor(context(1.5), S1, [])).toEqual([]);
  });
});

describe("nodeLabel", () => {
  it("names extrema by the graph's type and saddles as saddles", () => {
    const d = loadFixture("line");
    expect(nodeLabel(d, A)).toBe("max #0");
    expect(nodeLabel(d, S2)).toBe("saddle #5");
  });
});

describe("nearestNode", () => {
  const centers = [0, 0, 10, 0, 10, 10];
  it("finds the closest centre within range", () => {
    expect(nearestNode(centers, 9, 1, 3)).toBe(1);
  });
  it("returns -1 when nothing is within range", () => {
    expect(nearestNode(centers, 5, 5, 2)).toBe(-1);
  });
});

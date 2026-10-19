import { describe, expect, it } from "vitest";
import { ExportFormatError, decodeBin, parseExport } from "../../src/core/parse";
import { A, B, C, D, S1, S2, S3, loadFixture, readFixture } from "../helpers";

describe("parseExport", () => {
  it("reads the worked example exactly as Python wrote it", () => {
    const d = loadFixture("line");
    expect(d.numNodes).toBe(7);
    expect(Array.from(d.value)).toEqual([5, 4, 9, 8, 3, 2, 6]);
    expect(Array.from(d.persistence)).toEqual([3, 1, Infinity, 2, 1, 3, 2]); // null -> Infinity
    expect(Array.from(d.saturated.slice(S1))).toEqual([3, 3, 2]);
    expect(Number.isNaN(d.saturated[A])).toBe(true);                        // null -> NaN for extrema
    expect(Array.from(d.mergedInto)).toEqual([C, A, -1, C, -1, -1, -1]);
    expect(Array.from(d.labels)).toEqual([A, A, A, B, C, C, C, D, D]);
  });

  it("builds the saddle -> arc index", () => {
    const d = loadFixture("line");
    const ends = (s: number) => [d.saddleArcs[2 * s], d.saddleArcs[2 * s + 1]].map((a) => d.arcExtremum[a]).sort();
    expect(ends(S1)).toEqual([A, B]);
    expect(ends(S2)).toEqual([B, C]);
    expect(ends(S3)).toEqual([C, D]);
  });

  it("knows minima graphs and point data", () => {
    const d = loadFixture("ackley");
    expect(d.sign).toBe(-1);
    expect(d.points!.length).toBe(1500 * 2);
    expect(d.field).toBeUndefined();
  });

  it("rejects truncated binaries and unknown versions", () => {
    const { doc, buffers } = readFixture("line");
    expect(() => parseExport(doc, { ...buffers, labels: buffers.labels.slice(0, 4) })).toThrow(ExportFormatError);
    expect(() => parseExport({ ...doc, version: 2 }, buffers)).toThrow(/version/);
  });

  it("rejects arcs that don't go saddle -> extremum", () => {
    const { doc, buffers } = readFixture("line");
    const bad = structuredClone(doc);
    bad.arcs[0] = [bad.arcs[0][1], bad.arcs[0][0]];
    expect(() => parseExport(bad, buffers)).toThrow(/saddle -> extremum/);
  });

  it("decodes dtypes and checks counts", () => {
    const buf = new Uint16Array([1, 2, 3]).buffer;
    expect(Array.from(decodeBin({ path: "x", dtype: "uint16", shape: [3], bytes: 6 }, buf))).toEqual([1, 2, 3]);
    expect(() => decodeBin({ path: "x", dtype: "uint16", shape: [4], bytes: 6 }, buf)).toThrow(/needs 4/);
  });
});

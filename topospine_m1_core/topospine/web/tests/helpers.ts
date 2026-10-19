import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseExport, requiredFiles } from "../src/core/parse";
import { SpineData } from "../src/core/types";

const FIXTURES = join(__dirname, "fixtures");

export function readFixture(name: string): { doc: any; buffers: Record<string, ArrayBuffer> } {
  const dir = join(FIXTURES, name);
  const doc = JSON.parse(readFileSync(join(dir, "graph.json"), "utf8"));
  const buffers: Record<string, ArrayBuffer> = {};
  for (const [key, entry] of Object.entries(requiredFiles(doc))) {
    const b = readFileSync(join(dir, entry.path));
    buffers[key] = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
  }
  return { doc, buffers };
}

export function loadFixture(name: string): SpineData {
  const { doc, buffers } = readFixture(name);
  return parseExport(doc, buffers);
}

/** Node ids of the worked example: maxima A..D = 0..3 (samples 1,3,5,7), saddles s1..s3 = 4..6. */
export const A = 0, B = 1, C = 2, D = 3, S1 = 4, S2 = 5, S3 = 6;

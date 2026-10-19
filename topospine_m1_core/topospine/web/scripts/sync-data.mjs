// Copy pipeline exports (pipeline/out/<name>/) into public/data/<name>/ and write index.json.
// Usage: npm run sync-data [-- path/to/pipeline/out]
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(process.argv[2] ?? join(here, "..", "..", "pipeline", "out"));
const dst = join(here, "..", "public", "data");

if (!existsSync(src)) {
  console.error(`No exports at ${src}. Run e.g. \`python -m topospine.cli configs/gauss2d.yaml\` in pipeline/ first.`);
  process.exit(1);
}
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });

const index = [];
for (const name of readdirSync(src).sort()) {
  const dir = join(src, name);
  const graphPath = join(dir, "graph.json");
  if (!existsSync(graphPath)) continue;
  const doc = JSON.parse(readFileSync(graphPath, "utf8"));
  mkdirSync(join(dst, name));
  copyFileSync(graphPath, join(dst, name, "graph.json"));
  for (const entry of Object.values(doc.files)) copyFileSync(join(dir, entry.path), join(dst, name, entry.path));
  const kinds = doc.nodes.kind;
  index.push({
    name,
    kind: doc.dataset.kind,
    extremum: doc.dataset.extremum,
    numSamples: doc.dataset.numSamples,
    numExtrema: kinds.filter((k) => k === 0).length,
    numSaddles: kinds.filter((k) => k === 1).length,
  });
  console.log(`  ${name}`);
}
writeFileSync(join(dst, "index.json"), JSON.stringify(index, null, 2));
console.log(`${index.length} dataset(s) -> ${dst}`);

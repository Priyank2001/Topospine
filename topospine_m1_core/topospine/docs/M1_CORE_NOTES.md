# M1 core: file notes (files 1–6)

All six files are pure NumPy (+ SciPy's cKDTree for kNN). No TTK, VTK or file I/O, so
`pytest` runs anywhere in about half a second.

```
values + Neighborhood ─decompose()─► FlowDecomposition(graph, labels)
                      ─compute_persistence()─► Persistence(P, P*, merged_into)
                      ─filter_graph(p_lo, p_hi)─► ThresholdedGraph (Eqs. 1–3)
labels + values ─region_histograms()─► RegionHistograms (sizes, r_us lookups)
```

---

## File 1 · `core/graph.py` (+ package skeleton)

**Role.** The gradient flow graph G every source produces. Owns node kinds, values, sample
indices and saddle→maximum arcs, plus the invariants. Doesn't own coordinates, persistence or
labels. Layer: core.

**Design decisions**
- *One intermediate for every source* → Algorithm 1 is written once and our graph can be
  compared with TTK's/TACHYON's. Rejected: trusting each tool's own simplification.
- *Nodes reference samples by index, not coordinates* → the core is dimension-agnostic
  (3D grid and 8-D point cloud look identical here).
- *Immutable, validated arrays* (copied, read-only) → a malformed adapter output fails at
  construction with a clear message instead of corrupting Algorithm 1 later.
- *Saddles have exactly two arcs, possibly to the same maximum* → exact MS complexes contain
  such loops; our approximation never creates them.

**Tests (13).** Properties and `saddle_arcs`; copy/read-only; empty graph; 8 malformed graphs
rejected (each one names an adapter bug it would catch); loops allowed; tie-broken order.

## File 2 · `core/neighborhoods.py`

**Role.** The only grid-vs-points difference: a stream of undirected edges in blocks.

**Design decisions**
- *Edge blocks instead of CSR* → a 128³ grid with 26-connectivity has ~27 M edges (≈430 MB as
  int64 CSR); one block per stencil offset keeps peak memory ≈ 2 × 16 MB.
- *Connectivity by stencil size, implemented as "L1 radius ≤ r"* → 2/4/8/6/18/26 all come
  from one rule, valid in any dimension.
- *Half stencil* (first non-zero offset component positive) → every grid edge appears once.
- *kNN symmetrised by contract* (edges are undirected) → boundaries are seen from both sides.

**Tests (15).** Edge counts for six stencils; uniqueness and no self-loops; C order; length-1
axis; invalid connectivity; kNN symmetry on a hand-checkable 1-D cloud; self excluded;
input validation.

## File 3 · `core/gradient_flow.py`

**Role.** Steepest ascent → labels → boundary saddles → G. Paper Sec. 3.4.

**Design decisions**
- *Ranks instead of values* → `(f, index)` total order; plateaus resolve deterministically.
- *`np.maximum.at` on ranks* → highest neighbour for every sample in one vectorised pass per
  block, correct even when indices repeat (kNN reverse direction).
- *Pointer jumping for labels* → O(n log L) instead of following each path separately.
- *Region pair key `a·M + b`, reduced per block* → highest boundary edge per pair without a
  Python dict or holding all boundary edges at once.
- *Maxima are nodes 0..M−1* → labels are maximum node ids: they index persistence arrays
  directly and fit in uint16 for the browser.

**Tests (11).** Tie-broken ranks; NaN rejected; the worked example's "points to", labels,
saddle samples/values and arcs; plateau; single sample and monotone field; highest boundary
edge chosen; two Gaussians on 4- and 8-connected grids (saddle between peaks, persistence =
height difference); kNN recovers both peaks after p_lo = 0.1; larger k → fewer spurious maxima.

## File 4 · `core/persistence.py`

**Role.** Algorithm 1: P, P*, merged_into.

**Design decisions**
- *Direction flags on arcs + one outgoing arc per cancelled maximum* → PATH is a simple walk
  and REVERSE flips flags along it.
- *Union-find for terminals* → the lazy queue only needs û, v̂; full paths are walked once per
  saddle. Measured: 84 s → 7.8 s on a noisy 64³ grid (178 k saddles).
- *Python lists in the hot loop* → scalar list indexing is several times faster than ndarray.
- *Deterministic heap ties (by node id)* → identical output every run.

**Tests (26).** The worked example's P, P*, merged_into exactly; P* ≥ P; a ring (û = v̂) gets
P but cancels nothing and raises P* of the saddle on its path; empty graph; 20 random 1-D
signals match a brute-force elder-rule union-find (independent reference); the cancellation-only P* variant on the line and on a ring.

## File 5 · `core/extremum_graph.py`

**Role.** Eqs. 1–3 for any [p_lo, p_hi]; region representatives at p_lo; the two plot curves.
Python reference for the browser's TypeScript version.

**Design decisions**
- *Masks, not a new graph* → node/arc ids stay stable across thresholds, which the browser
  needs for a stable layout.
- *`representatives` by pointer jumping on merged_into* → region highlighting after
  simplification without touching per-sample data.

**Tests (10).** Every row of the walkthrough's threshold table; representatives at four
p_lo values (including the B → A → C chain); both curves; invalid ranges.

## File 6 · `core/region_stats.py`

**Role.** Per-region histograms of f: region sizes and r_us(c, p) lookups (Sec. 4.2).

**Design decisions**
- *Shared bin edges* → merging regions is a row sum (`merged`), so simplification never
  needs per-sample data.
- *Linear interpolation inside a bin* → smooth radii while dragging isovalues; exact at edges.

**Tests (7).** Sizes; bin placement; exact range counts; in-bin interpolation; merge preserves
totals; clipping; constant field and validation.

---

## Benchmark notes (container CPU, single thread)

| Field (128³ unless stated) | Stencil | Maxima | Saddles | decompose | persistence |
|---|---|---|---|---|---|
| smooth sin product | 6 | 4 | 6 | 0.6 s | 0.0 s |
| smooth sin product | 26 | 4 | 6 | 1.1 s | 0.0 s |
| + 1 % Gaussian noise | 6 | 107 415 | 672 538 | 2.2 s | 38 s |
| + 1 % Gaussian noise | 26 | 10 831 | 92 140 | 4.0 s | 2.2 s |
| 64³ + 5 % noise | 6 | 30 520 | 178 374 | 0.25 s | 7.8 s |

Observations worth keeping for the report:
- Cost is driven by the number of saddles, i.e. by noise, not by grid size.
- 26-connectivity produces ~10× fewer spurious maxima than 6-connectivity on noisy data
  (a coarse stencil creates fake local maxima), and is faster overall despite more edges.
- kNN shows the same effect with k (tests: k = 6 → 10 → 20 strictly fewer maxima).

## Check your understanding
1. Why can `steepest_ascent` use `np.maximum.at` on ranks rather than comparing values, and
   what would break with plain `best[src] = ...` assignment for kNN blocks?
2. In `_ReversibleFlow`, why is the union-find root of a path's first maximum always equal to
   the path's terminal? What would invalidate that?
3. Why does `filter_graph` return masks instead of a smaller graph, given what M2 does next?

---

# M1 files 7–12

`graph_from_regions` was split out of `decompose` (file 3) so the TTK adapter reuses the
saddle scan; `Persistence` gained `saturated_cancel` (file 4). Both changes are
backward-compatible and covered by the existing tests.

## File 7 · `core/datasets.py`, `io/readers.py`, `io/synthetic.py`

**Role.** Bring data in. `GridDataset`/`PointDataset` are pure containers (core); readers touch
disk (shell); synthetic generators give fields with known topology.

**Design decisions**
- *Two dataset kinds, one `kind` field* → consumers branch once (source choice, export).
- *Config axes in (x, y, z), arrays in (z, y, x)* → matches how data catalogues list dims and
  how VTK/WebGL order memory, so sample indices agree everywhere.
- *Normalisation lives in the reader* → kNN sees comparable units; `offset`/`scale` keep
  originals recoverable.
- *Registries (`READERS`, `GENERATORS`)* → a new format is one function + one dict entry.

**Tests (21).** Raw orientation and byte order, size mismatch, npy, CSV with feature subsets
and z-score, `.vti` round trip, xyz positions, normalisation round trips, bumps peak
positions, ring cycle, Ackley 2-D = 9 minima, generator errors.

## File 8 · `sources/base.py`, `sources/native_source.py`, `sources/__init__.py`

**Role.** `ExtremumGraphSource` protocol: `compute(dataset) -> FlowDecomposition` for maxima.
Native source = steepest ascent on a grid stencil (default: full stencil) or kNN.

**Design decisions**
- *Sources only compute maxima* → the pipeline negates for minima once; no backend duplicates it.
- *Full stencil by default* → the benchmark showed ~10× fewer spurious maxima on noisy grids.

## File 9 · `sources/ttk_source.py`

**Role.** TTK adapter: run `ttkMorseSmaleComplex`, take its maximum regions, build G with
`graph_from_regions`. **Not yet run against real TTK** (not installable in my sandbox); the
pure parts are tested with a fake backend, and `test_real_ttk_matches_native` (marked slow)
runs automatically once TTK is importable.

**Design decisions**
- *Regions only, auto-detected array* → robust to TTK version differences (DEVIATIONS #9).
- *Searches all output ports* → no hard-coded port numbers.

**Tests (10, in `tests/sources`).** Relabelled regions reproduce the native graph; maxima
regions beat minima regions in the picker; fake TTK backend end to end; points rejected;
VTK image axis order; real-TTK comparison (skipped without TTK).

## File 10 · `io/exporter.py`, `schema/spine.schema.json`

**Role.** The file contract for the browser, plus `read_export` to load it back into core objects.

**Design decisions**
- *Column arrays in JSON, bulk data in binaries* → typed arrays in the browser without parsing
  millions of numbers; `files` records dtype/shape/bytes so truncation is detected.
- *Histograms in `regions.bin`* → 100k noisy regions × 64 bins would be ~20 MB of JSON.
- *`null` for ±∞/NaN* → strict JSON (`allow_nan=False`); the schema documents the meaning.
- *Original f in the export, maxima-space graph on reload* → the browser shows real values;
  Python's invariants still hold after `read_export`.

**Tests (6).** Round trip (graph, labels, persistence with ∞, dequantised field), schema
validation, minima export, float32 field, truncated binary, uint32 labels above 65 535 regions.

## File 11 · `config.py`, `run.py`, `cli.py`, `configs/*.yaml`

**Role.** One command per dataset: `python -m topospine.cli configs/X.yaml [--preview]`.

**Design decisions**
- *Paths relative to the config file* → works from any working directory.
- *`run_pipeline` separate from argparse* → testable and notebook-friendly.
- *Timings in the summary* → numbers for the performance section come for free.

**Tests (9).** Path resolution, five invalid configs, every shipped config parses, end-to-end
run, CLI with preview.

## File 12 · `viz/preview2d.py`, `scripts/preview_2d.py`

**Role.** Matplotlib check of a 2-D export: regions at p_lo, G_R drawn saddle → extremum,
and the blue/red curves. Reads only the export, so it also validates the contract.

**Tests (4).** Renders for ring (both P* variants) and Ackley; 3-D export rejected.

---

## Milestone review (M1)

**Demo checklist**
1. `pytest -m "not slow"`: all pass in a few seconds.
2. `python -m topospine.cli configs/gauss2d.yaml --preview` → 2 maxima, 1 saddle.
3. `python -m topospine.cli configs/ring2d.yaml --preview --p-lo 0.05 --p-hi 0.9 --saturation cancel`
   → 8 maxima connected in a ring; rerun with `--saturation paper` to see DEVIATIONS #8.
4. `python -m topospine.cli configs/ackley2d.yaml --preview --p-lo 0.05` → 3 × 3 minima.
5. TTK spike: in the TTK conda env, `python -m topospine.cli configs/gauss3d_ttk.yaml` and
   `pytest -m slow -k ttk`.

**Architecture check.** No class has two responsibilities; the only `kind` branches are in
`NativeSource.neighborhood`, `write_export` and the preview, each choosing between two data
layouts. `run.py` imports the concrete source registry; acceptable as the composition root.

**Re-plan.** Two findings change M2's scope slightly: the P* toggle (small), and noisy data
producing very large graphs (672k saddles on noisy 128³). M2 should load only nodes/arcs that
can be visible for p_lo ≥ some export floor; an `export_min_persistence` option in the
exporter is the planned fix if real datasets need it.

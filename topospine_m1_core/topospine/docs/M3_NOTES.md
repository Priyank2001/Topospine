# M3 composable extraction: file notes and results

M3 split graph extraction into two swappable blocks, so native and TTK can be compared one
step at a time, and added TTK's own saddles as a second saddle method (DECISIONS.md D-004).

```
dataset ─► ExtractionContext (ranks + neighbourhood, built once)
             ├─► RegionMethod.labels(ctx)           ─► labels 0..M-1      ascent | ttk
             └─► SaddleMethod.saddles(ctx, labels)  ─► SaddleSet          boundary | ttk
                                  core.assemble_flow ─► FlowDecomposition ─► Algorithm 1 (unchanged)
```

| regions \ saddles | `boundary` | `ttk` |
|---|---|---|
| `ascent` | yes: preset `native` | rejected (D-007) |
| `ttk` | yes: preset `ttk` | yes: full TTK |

How to run a combination: `source: {regions: ttk, saddles: ttk}` in a config, or
`--regions` / `--saddles` on the command line (D-006, D-013). `graph.json` records what ran
under `dataset.source` and `dataset.extraction`.

---

## Files

All paths are under `pipeline/src/topospine/`.

| # | File | Role | Tests |
|---|---|---|---|
| 1 | `core/gradient_flow.py` | `SaddleSet`; `boundary_saddles` (our rule, moved out); `assemble_flow`, the only place a graph is built; ranks checked to be a permutation (D-008) | `tests/core/test_gradient_flow.py` |
| 2 | `sources/base.py`, `sources/composed_source.py` | the block interfaces (`RegionMethod`, `SaddleMethod`, `ExtractionContext`); `ComposedSource` joins two blocks, owns the neighbourhood, checks D-007 before data loads | `tests/sources/test_composed_source.py` |
| 3 | `sources/native_blocks.py` | `AscentRegions`, `BoundarySaddles`; `NativeSource` becomes the `ascent+boundary` preset | `tests/sources/test_native_blocks.py` |
| 4 | `sources/ttk_backend.py` | the only TTK/VTK code: run `ttkMorseSmaleComplex`, copy every port to read-only NumPy, cache the last dataset so `ttk+ttk` runs TTK once | `tests/sources/test_ttk_backend.py` |
| 5 | `sources/ttk_output.py`, `sources/ttk_blocks.py`, `core/reconnect.py` | TTK's output layout; `TtkRegions` (scored by TTK's maxima, D-012), `TtkSaddles` (D-009, D-010, D-011); joining pieces | `tests/sources/test_ttk_blocks.py`, `tests/core/test_reconnect.py` |
| 6 | `sources/__init__.py` | `REGION_METHODS`, `SADDLE_METHODS`, `PRESETS`, `compose_source`, `make_source` | `tests/sources/test_registry.py` |
| 7 | `config.py`, `cli.py`, `run.py` | the two config forms, the flags, the output suffix, what `graph.json` records | `tests/test_config_methods.py` |
| 8 | configs, docs | `gauss3d_ttk_ttk.yaml`; this file | (shipped configs parse) |

### Implementation details worth knowing

- **TTK 1.3.0 output layout.** Port 0 = critical points (`CellDimension`, `CellId`,
  `ttkVertexScalarField`); port 1 = separatrices (`SourceId`, `DestinationId`,
  `SeparatrixId`, `SeparatrixType`); the segmentation is the port whose point arrays have one
  value per sample. Ports are found by their arrays, never by number.
- **Uphill separatrix** = `SeparatrixType == d − 1` (1 in 2-D, 2 in 3-D), where d is TTK's
  dimension, read as the highest `CellDimension`.
- **Cell ids are per dimension.** A saddle and a maximum can both be `CellId` 0, so every
  lookup is by (dimension, id).
- **Group separatrices by saddle cell, not by sample.** `ttkVertexScalarField` is a cell's
  highest vertex, and two critical cells can share it (43 samples on noisy `bumps3d`).
  Grouping by sample produced false 3-way saddles. One sample can therefore carry two
  saddles; `assemble_flow` allows it.
- **Which segmentation array holds the maxima's regions.** In TTK 1.3.0 it is
  `AscendingManifold` (on noisy `bumps3d`: 136 regions for 135 TTK maxima; `Descending` had
  382 regions = the number of minima). We still score instead of trusting the name (D-012).
- **Reports.** Every block has `report()`; `TtkRegions` says which array won and its score,
  `TtkSaddles` says how many saddles were kept / dropped / added.

---

## Results: native vs TTK, one block at a time

Evidence script: `temp/evidence/m3_compare.py` (TTK env). "p ≥ 5 %" counts maxima whose
persistence is at least 5 % of the value range; "inf" counts maxima of infinite persistence
(must be 1 for a connected graph). Times include Rosetta overhead for TTK (D-003), so they
are not fair speed numbers.

| dataset | method | maxima | saddles | inf | p ≥ 5 % | top-3 finite p (% range) | TTK saddles kept/dropped/added |
|---|---|---|---|---|---|---|---|
| gauss3d | ascent+boundary | 4 | 6 | 1 | 4 | 57.6, 55.8, 32.7 | |
| gauss3d | ttk+boundary | 4 | 6 | 1 | 4 | 57.6, 55.8, 32.7 | |
| gauss3d | ttk+ttk | 4 | 9 | 1 | 4 | 57.6, 55.8, 32.9 | 9/9/0 |
| bonsai (2-D slice) | ascent+boundary | 1006 | 3097 | 1 | 281 | 54.9, 49.8, 49.4 | |
| bonsai | ttk+boundary | 1219 | 3700 | 1 | 279 | 54.9, 49.8, 49.4 | |
| bonsai | ttk+ttk | 1219 | 1686 | 1 | 298 | 54.9, 49.8, 49.4 | 1637/135/49 |
| foot (2-D slice) | ascent+boundary | 1737 | 5352 | 1 | 494 | 83.5, 40.8, 37.6 | |
| foot | ttk+boundary | 2093 | 6599 | 1 | 481 | 83.5, 40.8, 37.6 | |
| foot | ttk+ttk | 2093 | 4025 | 1 | 587 | 84.3, 42.7, 40.8 | 4009/103/16 |
| engine (2-D slice) | ascent+boundary | 3022 | 9328 | 1 | 11 | 97.3, 19.2, 10.2 | |
| engine | ttk+boundary | 3686 | 11502 | 1 | 11 | 97.3, 19.2, 10.2 | |
| engine | ttk+ttk | 3686 | 6953 | 1 | 11 | 97.3, 19.2, 10.2 | 6942/132/11 |
| aneurism (2-D slice) | ascent+boundary | 206 | 621 | 1 | 112 | 100, 100, 100 | |
| aneurism | ttk+boundary | 218 | 535 | 1 | 112 | 100, 100, 100 | |
| aneurism | ttk+ttk | 218 | 220 | 1 | 117 | 100, 100, 100 | 159/72/61 |

What the table says:

1. **Regions step (ascent → ttk, saddles fixed to boundary).** TTK finds 6–22 % more maxima
   on the real slices (its triangulation and our 8-neighbour stencil disagree on tiny
   bumps), but the important ones agree: the number with p ≥ 5 % differs by at most 13 of
   ~500, and the top-3 persistences are identical. On clean `gauss3d` the two are identical.
2. **Saddles step (boundary → ttk, regions fixed to ttk).**
   - TTK keeps **fewer** saddles: one per real pass rather than one per pair of touching
     regions, plus repeated passes between the same pair (`gauss3d`: 9 vs 6; pairs (0,2)×2,
     (2,3)×3).
   - TTK's exact saddle can sit **lower** than our "highest border edge", so persistence
     rises slightly (foot: 84.3 vs 83.5; `gauss3d` 3rd peak 32.9 vs 32.7).
   - **More maxima pass the 5 % cut** (foot 587 vs 481, bonsai 298 vs 279). Cause: passes
     TTK doesn't give us, either dropped as one-sided (D-009) or lower than our border edge.
     D-011 only adds passes where pieces are disconnected, not where a higher pass is
     missing, so such peaks merge later and look more important. Check: TTK's saddles **plus
     all** our boundary saddles give exactly the `ttk+boundary` counts (foot 481, bonsai 279).
   - Every run has exactly **one** infinite-persistence maximum: D-011 keeps the graph whole.
     Without it, foot falls into 17 pieces and bonsai into 50.
3. **Open concern (review item).** On `aneurism`, D-011 added 61 of our saddles against 159
   kept from TTK: the "revisit if" condition of D-011 is met. Together with point 2, this
   says `ttk+ttk` is a fair *structural* comparison (which saddles TTK finds) but its
   persistence values on noisy real data are biased upward. For persistence comparisons,
   `ttk+boundary` vs `native` is the cleaner one.

---

## Not done in M3

- Degenerate saddles (3+ peaks) stop the run (D-010); never seen so far.
- Block parameters on the command line (`--regions-param`); see D-013 "Revisit if".
- Tachyon as a third region method (D-002, deferred).
- The web viewer does not show `dataset.extraction` yet (it is in `graph.json`).

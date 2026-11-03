# High-dimensional visualization features: how they plug in

Read this for any feature that shows data with more than 3 dimensions (point datasets
such as `ackley4d`, or any `meta.kind === "points"` export).

## Contents
1. What data we have
2. The three extension points
3. Linked views and selection
4. Feature catalogue (candidates, in suggested order)
5. Performance budgets
6. Visual consistency rules

---

## 1. What data we have

From the file contract (see `docs/ARCHITECTURE.md`, "The file contract"):

| Data | Shape | Meaning |
|---|---|---|
| `points` | n × d float32 | every sample, in the normalised space the kNN graph used |
| `meta.points.featureNames`, `offset`, `scale` | d | names; `x_original = x * scale + offset` |
| `labels` | n | region (extremum node id) of each sample |
| `position` | numNodes × posDim | coordinates of every critical point (extrema + saddles) |
| `value`, `persistence`, arcs | per node / arc | the extremum graph |
| `regionCounts` | numRegions × bins | value histogram per region |

So we can show: the samples themselves, the critical points, which region each sample
belongs to at the current noise threshold (via `representatives(pLo)`), and how features vary
per region. New per-sample or per-region statistics that are expensive belong in the
pipeline + file contract, not in the browser.

## 2. The three extension points

### a. `ProjectionStrategy` (core, pure): d-D → 2-D
```ts
/** Maps rows of an n × d matrix to 2-D. Pure; no DOM. */
export interface ProjectionStrategy {
  readonly id: string;                 // "pca", "axes", "mds", …
  readonly label: string;              // shown in the UI
  project(data: Float32Array | Float64Array, n: number, d: number, opts: ProjectionOptions): Float64Array;
}
```
Today `core/layout/pca.ts` and `stress.ts` are hard-wired into `SpinePipeline`. Wrap them as
strategies and register them in `core/projection/registry.ts`. Adding UMAP/t-SNE later = one new file + one registry entry.
Which projection is active is **app state** (`ProjectionModel` or a field in a view-settings model), not a view field.

### b. Linked view (view interface + presenter)
Every new view of the data is a pair:
- `views/<name>/contract.ts` (interface, view model, events) + concrete view: draws a view model, emits intents (`hovered(ids)`, `brushed(ids)`, `cleared()`).
- `presenters/<Name>Presenter.ts` (extends `Presenter`): subscribes to `SessionModel`, `SpineParamsModel`, `SelectionModel` (and whatever settings model it needs), maps to the view model, forwards intents to `SelectionModel`.

### c. Selector (core, pure, memoised)
Anything computed from data + state (projected coordinates, region colours, per-region feature
means, brushed sets) is a memoised selector like the stages in `core/derive.ts`. Presenters call
selectors; they never store results.

## 3. Linked views and selection

`SelectionModel` (`web/src/model/SelectionModel.ts`, built in F1) is the single owner of "what the user is pointing at":

```ts
interface SelectionState {
  hovered: number | null;              // transient, from pointer moves
  selected: ReadonlySet<number>;       // sticky, click order; the ids the user actually picked
}
// methods: hover(id | null), selectOnly(id), toggle(id), clear(), reset()
```

Not built yet, add when the first non-spine view can pick: `selectedRegions` (sample brushes
resolve to regions) and `source` (which view made the selection, to avoid feedback loops).
What a pick means at the current thresholds (visible / merged into its representative /
hidden) is derived in `core/selection.ts` from `SpineFrames.selectionContext()`.

Rules:
- Views never highlight on their own; they highlight what the view model says is selected. Then all views agree.
- A brush in view A → `selection.select(ids, "A")` → all presenters re-present → view A doesn't redraw its brush rectangle from state (ephemeral), but does redraw highlights.
- Picks keep their original ids. When pLo changes, presenters map them to their current representatives through `core/selection.ts`; the model is never mutated behind the user's back.
- `Esc` / click on empty space → `selection.clear()`.

## 4. Feature catalogue (candidates, in suggested order)

| # | Feature | What the user learns | New pieces |
|---|---|---|---|
| F1 ✅ | **Linked selection spine ↔ plot ↔ details** (done) | Which extremum is which; its persistence and size | `SelectionModel`, picking in `SpineView`, `HighlightLayer`, selection details panel |
| F2 | **Sample projection view** (2-D scatter of all samples, coloured by region at pLo) | How regions sit in the high-D domain; overlaps hidden by projection | `ProjectionStrategy` (PCA, pick-two-axes), `ProjectionView` (WebGL points), `ProjectionPresenter` |
| F3 | **Parallel coordinates of critical points** (one polyline per extremum/saddle across d features + value) | Which features separate the peaks; saddle positions between peaks | `ParallelCoordsView` (canvas 2-D), axis brushing → selection |
| F4 | **Region feature profiles** (per selected region: mean ± spread of each feature, or small histograms) | How a region differs from the rest | selector over `points` + `labels` + `rep`; small-multiples view |
| F5 | **Scatterplot matrix (SPLOM)** of samples or critical points, subsampled | Pairwise structure; projection check | reuses F2's point renderer per cell; dimension picker |
| F6 | **Spine layout choice** (PCA / stress / MDS) and layout quality readout (stress value) | How faithful the 2-D spine is to the d-D distances | strategies from 2a for `SpinePipeline`, stress metric selector |

Build F1 first: it creates `SelectionModel` and picking, which F2–F5 all reuse.

## 5. Performance budgets

- Target 60 fps for hover/brush, < 100 ms for threshold changes on 100k samples × 4-10 dims.
- Per-sample work on threshold change must be O(n) typed-array passes (e.g. relabel through `rep`), never per-sample objects.
- Projections of all samples are computed once per (dataset, strategy, dims) and memoised; only colours change with pLo.
- Draw ≥ 10k points with WebGL (instanced points / `THREE.Points`), not Canvas 2-D.
- Deterministic subsampling (seeded, stratified by region) for SPLOM cells and parallel coordinates when n is large; show "showing k of n".
- Measure before optimising; log numbers in `docs/RESULTS_LOG.md`.

## 6. Visual consistency rules

- One region → one colour in every view. A single mapper (`core/regionColors.ts`) assigns categorical colours to representatives; every presenter uses it.
- Value (f) → viridis everywhere it means "height"; categorical colours never encode value.
- Selected = full opacity + ink outline; non-selected fade to ~25% when a selection exists.
- Axis labels use `featureNames` and original units (`offset`/`scale`).
- Every view states what is projected / subsampled in a caption line.

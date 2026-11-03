# Topospine architecture, in plain words

This document explains every part of the project: what it is for, what it holds, and who
talks to whom. Read it before changing code. When you add a part, add it here too.

Status tag: **[planned]** marks parts designed for the high-dimensional features but not
built yet. Everything without a tag exists in the code.

---

## 1. The big picture

Topospine shows the *shape* of a function: where its peaks are, how important each peak is,
and how peaks connect. It does this in two separate programs:

```
   data file / synthetic data
            │
            ▼
 ┌──────────────────────┐   writes files    ┌──────────────────────────┐
 │  PIPELINE (Python)   │ ────────────────▶ │  WEB APP (TypeScript)    │
 │  heavy maths, once   │  graph.json +     │  interactive, in browser │
 │  per dataset         │  *.bin files      │  sliders, views, picking │
 └──────────────────────┘                   └──────────────────────────┘
```

- The **pipeline** does the slow work once: it finds peaks and saddles, measures how important
  they are, and saves everything to a folder.
- The **web app** reads that folder and lets you explore it: move thresholds, see the spine
  update, compare views.
- The **file contract** (section 4) is the only thing they share. Either side can change
  internally as long as the files stay the same.

### Words you will meet

| Word | Plain meaning |
|---|---|
| Scalar field / f | A number at every point of space (temperature, density, a test function). |
| Extremum | A peak (maximum) or a pit (minimum) of f. We work with maxima; minima = maxima of −f. |
| Saddle | A mountain pass: the highest point on the lowest path between two peaks. |
| Region (of an extremum) | All points that "flow uphill" to that peak. |
| Extremum graph | Peaks and saddles as nodes, with an edge from each saddle to the two peaks it joins. |
| Persistence P | How important a peak is: how far you must go down before it merges with a higher peak. Small P = noise. |
| Saturated persistence P* | For a saddle: the persistence level at which its connection stops mattering (paper's Algorithm 1). |
| Noise threshold pLo | Hide peaks with P below this. |
| Variation threshold pHi | Hide connections through saddles that are themselves important. |
| Representative | After hiding a small peak, the bigger peak it merged into. |
| Topological spine | The 2-D picture: blobs for peaks, tubes for connections, sized by region volume, with contour levels. |
| High-dimensional data | Point samples with d > 3 coordinates (e.g. Ackley in 4-D). You can't draw them directly, so we project. |

---

## 2. The pipeline (Python, `pipeline/`)

Think of it as a factory line: **config → dataset → graph → importance → statistics → files.**

```
 config.yaml ─▶ readers / synthetic ─▶ Dataset ─▶ Source (native | TTK) ─▶ FlowDecomposition
                                                                            │
     files ◀── exporter ◀── region histograms ◀── persistence (Algorithm 1) ◀┘
```

### Entry points
| Component | Role in one sentence |
|---|---|
| `cli.py` | The command you type: reads arguments, calls `run_pipeline`. Nothing else. |
| `config.py` | Reads one YAML file into a typed `RunConfig`; resolves paths relative to the YAML. |
| `run.py` | The conductor: runs each step of the line in order and times it. Tests call it directly. |

### Core (`core/`, pure NumPy: no files, no TTK, no VTK)
| Component | Role |
|---|---|
| `datasets.py` | Two containers: `GridDataset` (values on a regular grid) and `PointDataset` (scattered points in d dimensions). Everything downstream accepts either. |
| `neighborhoods.py` | Answers one question, "who are each sample's neighbours?": a grid stencil for grids, a k-nearest-neighbour graph for points. Streams edges in blocks to save memory. |
| `gradient_flow.py` | Walks every sample uphill to its peak (giving regions) and finds the saddle between each pair of touching regions (`boundary_saddles`). Whatever method found the regions and saddles, `assemble_flow` turns them into the graph; a saddle method hands it a `SaddleSet` (each saddle's sample and the two regions it joins). |
| `graph.py` | The extremum graph data structure that every source produces, so the next step is written once. |
| `persistence.py` | The paper's Algorithm 1: computes P and P* by cancelling the least important peak first. |
| `extremum_graph.py` | Eqs. 1–3: given [pLo, pHi], which peaks, saddles and arcs stay. Reference for the web version. |
| `region_stats.py` | A value histogram per region, so the browser can size spine tubes without per-sample data. |

### Shell (talks to the outside world)
| Component | Role |
|---|---|
| `io/readers.py` | Turns files (raw, npy, vti, csv) into a `Dataset`. New format = one function + one entry in `READERS`. |
| `io/synthetic.py` | Generates test data with known answers (bumps, ring, Ackley, Schwefel, Gaussian mixtures). |
| `io/exporter.py` | Writes (and reads back) the file contract. |
| `sources/base.py` | The interfaces of graph extraction: the whole job (`ExtremumGraphSource`: `compute(dataset) → FlowDecomposition`) and its two blocks, `RegionMethod` (which peak each sample flows up to) and `SaddleMethod` (the saddles between those regions). `ExtractionContext` is what both blocks of one run share: the dataset, its ranks, the neighbourhood. |
| `sources/composed_source.py` | `ComposedSource` joins one region method and one saddle method into a backend. It builds the shared context once, refuses incompatible pairs before any data is loaded (DECISIONS.md D-007), and owns the neighbourhood settings (grid stencil, k). |
| `sources/native_source.py` | Our own backend (steepest ascent). Works for grids and points. |
| `sources/ttk_source.py` | TTK backend: uses TTK's regions, our saddle rule. New backend = one file + one entry in `SOURCES`. |
| `viz/preview2d.py`, `scripts/preview_2d.py` | A static PNG check of a 2-D result, made only from the exported files. |
| `scripts/make_web_fixtures.py` | Writes the tiny datasets the web tests use. |
| `configs/*.yaml` | One file per dataset run, so every result is one command away. |
| `schema/spine.schema.json` | The written-down file contract (shared with the web app). |

**Design idea:** maths in `core/` never touches disk or libraries, so it is easy to test with
tiny worked examples. Swappable parts (readers, backends) sit behind one interface and a
registry dictionary, so adding one never edits existing code.

---

## 3. The web app (TypeScript, `web/`)

### 3.1 The pattern: Model–View–Presenter (MVP)

Picture a restaurant:
- **Model** = the kitchen's order book. It holds the truth (what was ordered) and the rules
  ("no dessert before mains"). It doesn't know who is eating.
- **View** = the dining table. It shows what it is given and passes on what the guest asks
  for. It decides nothing.
- **Presenter** = the waiter. Takes the request from the table to the order book, and brings
  back exactly what the table should show.

```
  you drag a slider
        │
        ▼
     VIEW ── "thresholdsDragged(3, 7)" ──▶ PRESENTER ── params.setThresholds(3, 7) ──▶ MODEL
       ▲                                     │                                         │
       └──── render(viewModel) ◀──── builds view model ◀──── "I changed" ◀────────────┘
```

Why: each piece has one job, so it is small, easy to test (a presenter can be tested with a
fake view, no browser), and easy to extend (a new view = a new view + presenter pair; nothing
else changes). Data always flows in one direction, so you can always answer "why does the
screen show this?".

### 3.2 Layers and who may use whom

```
                main.ts  (builds and connects everything)
                   │
    ┌──────────────┼───────────────────┐
    ▼              ▼                   ▼
  views/ ──▶ render/          presenters/ ──▶ model/ ──▶ services/
    │                              │            │
    └──── core/ types ◀────────────┴────────────┘      core/ = pure maths, used by all
```

| Layer | Folder | One-line job | Never does |
|---|---|---|---|
| Core | `core/` | Pure algorithms on typed arrays. | DOM, GPU, state |
| Model | `model/` | Holds app state, enforces rules, announces changes; runs the use cases. | DOM, GPU, views |
| Service | `services/` | Fetches files. | State, UI |
| Presenter | `presenters/` | Turns state into view models; turns user intents into model calls. | DOM, GPU |
| View | `views/` | Draws view models; reports user actions. | Rules, state changes |
| Render | `render/` | GPU objects and shaders behind a view. | Anything outside its canvas |
| Composition root | `main.ts` | Creates all objects and wires them. | Logic |

### 3.3 Where state lives (the state table)

Every piece of state has exactly one owner. Anything that can be computed from other state
is **not** stored; it is recomputed (and cached) by selectors.

| State | Kind | Owner | Changed by |
|---|---|---|---|
| List of datasets (loading / ready / error) | app | `SessionModel.index` | `setIndex`, `failIndex` |
| Open dataset (idle / loading / ready / error) + its `SpineData` | app | `SessionModel.load` | `beginLoad`, `finishLoad`, `failLoad` |
| pLo, pHi | app | `SpineParamsModel` | `setThresholds`, `setNoise`, `setVariation`, `unlimitVariation`, `resetForDataset` |
| Saturation, spine style (radius mode, glyph scale, levels, show links/nodes, dedupe) | app | `SpineParamsModel` | `setOptions` |
| Hovered node, selected nodes (ids the user picked, in click order) | app | `SelectionModel` | `hover`, `selectOnly`, `toggle`, `clear`, `reset` |
| Active projection + chosen dimensions | app | `ProjectionModel` [planned] | `setStrategy`, `setAxes` |
| Spine frame: visible graph, representatives, layout, geometry, merged regions | derived | `SpineFrames` (cached `SpinePipeline` per dataset) | recomputed when dataset or params change |
| What a pick means now (visible / merged into #k / hidden) and which rings to draw | derived | `core/selection.ts` over `SpineFrames.selectionContext()` | recomputed per frame and selection |
| Persistence curves, overlay arrays, level colours, spine content view model | derived | cached inside the presenter that shows them | recomputed per dataset / frame |
| Camera pan/zoom (`Viewport`), drag in progress (`PointerGestures`), focused plot line | ephemeral | the view itself | user input |
| Which dataset the camera was last fitted to | presenter | `SpinePresenter` | a new dataset becomes ready |

Rules in short: change state only through named model methods; never edit a returned
object; slow requests that come back after a newer one are ignored.

### 3.4 Components

#### Core (`core/`): the maths, no screen
| Component | Role |
|---|---|
| `types.ts` | The in-memory shape of one dataset (`SpineData`): typed arrays indexed by node, arc or sample. |
| `parse.ts` | Checks the downloaded files against the contract and turns them into `SpineData`. |
| `thresholds.ts` | Eqs. 1–3 in TypeScript: what is visible for [pLo, pHi]; representatives; the two persistence curves; a suggested starting pLo. |
| `regionStats.ts` | Adds up region histograms when peaks merge; answers "how many samples between two values?". |
| `displayGraph.ts` | From the visible graph to what is drawn: redirects hidden peaks to their representatives and drops collapsed saddles. |
| `layout/pca.ts` | A first 2-D placement of all critical points (principal components). |
| `layout/stress.ts` | Moves nodes so 2-D distances match the real (possibly high-D) distances. |
| `spine/levels.ts` | Picks which contour levels to draw. |
| `spine/links.ts` | Builds the tube pieces (circles joined by tapered capsules) for each level. |
| `spine/sdf.ts` | The shape's distance function, in TypeScript, to test what the shader does. |
| `spine/overlay.ts` | Packs the drawn graph into flat arrays (link segments, node centres and kinds) for the overlay. |
| `spine/levelColors.ts` | Fill colour of each contour level (viridis over the value range). |
| `colormap.ts` | Viridis colours for values. |
| `format.ts` | Short number formatting for labels (`0.12`, `1.2e+3`, `∞`). |
| `spineState.ts` | The `SpineParams` type and its defaults: plain data, so the core pipeline can take it. |
| `selection.ts` | What a picked node means under the current thresholds: visible, merged into its representative, or hidden; its f, P and region size; and which rings to draw (selected, hovered, dashed stand-in for a merged pick). |
| `spine/pick.ts` | Nearest drawn node to a point, within a radius. |
| `derive.ts` | `SpinePipeline`: chains the steps above and caches each step, so moving one slider only redoes what depends on it. Also `memo`, the one-entry cache used everywhere. |

#### Models (`model/`): the truth and the rules
| Component | Role |
|---|---|
| `Store.ts` | The observable box each model keeps privately. Skips notifying when nothing changed. |
| `SessionModel.ts` | Two small state machines: the dataset list, and the open dataset (loading, ready or failed). Every load has a request id; a stale one can't finish. Synchronous: it never fetches. |
| `SpineParamsModel.ts` | Thresholds and spine options. Owns rules like "pLo ≤ pHi", "no negative thresholds", and "a new dataset starts at the suggested pLo". |
| `SelectionModel.ts` | What the user is pointing at: the hovered node and the selected nodes, shared by all views so they highlight the same things. Stores the ids actually picked; what stands in for them at the current thresholds is derived. |
| `Workspace.ts` | The use cases that touch more than one model: `start` (list, then open the first dataset) and `open` (fetch, reset thresholds and selection, then publish ready). Models never listen to each other; this class coordinates them. |
| `SpineFrames.ts` | Derived state: the current `SpineFrame`, cached per dataset and per params snapshot, so every presenter gets the same frame object; plus the `SelectionContext` (representatives, region sizes, drawn nodes) built once per frame. |
| `ProjectionModel.ts` [planned] | Which high-D → 2-D projection is active and on which dimensions. |

#### Services (`services/`)
| Component | Role |
|---|---|
| `DatasetSource.ts` | The interface `index()` / `load(name)`, and the `DatasetEntry` type. Tests pass a fake. |
| `HttpDatasetSource.ts` | Downloads `index.json`, `graph.json` and the binaries from `public/data/`. Parsing is left to `core/parse.ts`. |

#### Presenters (`presenters/`): the waiters
`Presenter.ts` is their shared base: it keeps subscriptions, turns many model changes in one
tick into **one** `present()` (on the microtask queue, before the browser paints), and disposes
the view it owns.

| Component | Listens to | Shows in | Sends to |
|---|---|---|---|
| `SpinePresenter` | Session, Params (via SpineFrames), Selection | spine view: content only when it changed, rings on every selection change; fits when a new dataset appears | `selection.hover`, `selectOnly`, `toggle`, `clear` (offers a `fitView` command) |
| `PlotPresenter` | Session, Params, Selection | persistence plot, with ticks at P of selected/hovered nodes | `params.setNoise`, `params.setVariation` |
| `SelectionPresenter` | Session, Params (via SpineFrames), Selection | selection details | — |
| `PanelPresenter` | Session, Params | parameter panel | params methods, `workspace.open`, the injected `fitView` command |
| `StatsPresenter` | Session, Params (via SpineFrames) | stats list | — |
| `StatusPresenter` | Session, Params (via SpineFrames) | status overlay, dataset line | — |

#### Views (`views/`): the tables
Each folder holds a `contract.ts` (the view interface, its view model and its events; no DOM)
and the concrete class. Presenters import only the contract.

| Component | Draws | Reports |
|---|---|---|
| `spine/SpineView` | The spine on a WebGL canvas and highlight rings; resize, theme, redraw-on-demand; finds the node under the pointer. Mixes outline colours from the theme. | `nodeHovered`, `nodeClicked(id, additive)`, `cleared` (double-click fits) |
| `spine/Viewport` | Pan/zoom maths (centre + scale), no DOM, unit-tested. | — |
| `spine/PointerGestures` | Raw pointer/wheel/key events → pan, zoom, hover, click (moved < 4 px), leave, Esc. | gestures to `SpineView` |
| `spine/theme` | Reads canvas colours from the page's CSS tokens (light/dark). | — |
| `plot/PersistencePlotView` | The two-curve plot with draggable threshold lines and selection ticks; keyboard support. | `noiseDragged`, `variationDragged` |
| `selection/SelectionListView` | "Selection" heading, a hint line, the pointer row, one row per selected node. | — |
| `panel/LilGuiPanelView` | lil-gui sliders and toggles. | `datasetChosen`, `noiseChanged`, `variationChanged`, `variationLimitToggled`, `optionsChanged`, `fitRequested` |
| `stats/StatsListView` | Label/value rows in a `<dl>`. | — |
| `text/TextView` | One line of text (used for the status overlay and the dataset line). | — |
| `ProjectionView`, `ParallelCoordsView`, … [planned] | High-D views (see section 6). | hover, brush, clear |

#### Render (`render/`): the GPU work behind `SpineView`
| Component | Role |
|---|---|
| `SpineSdfRenderer.ts` | Per contour level: draws capsule distances into a texture, then fills and outlines the union in one full-screen pass. Clean edges, no overlap seams. |
| `Overlay.ts` | Draws the links (lines) and critical-point markers on top. |
| `HighlightLayer.ts` | Rings around hovered/selected nodes, on top of the markers. Separate so a hover rebuilds a handful of quads, never the spine. |
| `shaders/*.glsl` | The GPU programs used by the three renderers. |

#### Glue
| Component | Role |
|---|---|
| `main.ts` | The composition root: builds models, services, views and presenters, wires them, starts the workspace, disposes everything on hot reload, and shows startup errors. |
| `scripts/sync-data.mjs` | Copies pipeline output into `public/data/` and writes `index.json`. |
| `tests/core`, `tests/model`, `tests/presenters`, `tests/views` | Vitest. Presenter tests use the fake views in `tests/presenters/fakeViews.ts` and real models, so they run without a browser. `tests/fakes.ts` has a dataset source whose loads finish when the test says so. |

---

## 4. The file contract (pipeline → web)

One folder per dataset, described exactly in `pipeline/schema/spine.schema.json`:

| File | Contents |
|---|---|
| `graph.json` | Metadata, nodes (kind, value, sample, position, P, P*), arcs, histogram bin edges, and a list of the binaries with type and size. |
| `labels.bin` | For every sample: the peak whose region it belongs to. |
| `regions.bin` | For every peak: a histogram of values in its region. |
| `field.bin` | Grids only: the field values (for drawing the field). |
| `points.bin` | Point data only: every sample's d coordinates. This is the input to high-D views. |

Changing the contract means changing the schema, the exporter, `core/parse.ts`, and their
tests together.

---

## 5. Life of one interaction (dragging the noise threshold)

1. You drag the blue line in the plot. `PersistencePlotView` emits `noiseDragged(3.1)`.
2. `PlotPresenter` calls `params.setNoise(3.1)`.
3. `SpineParamsModel` applies its rule (pLo may not pass pHi) and updates its store, which
   notifies listeners. Each presenter just marks itself "needs present".
4. In the same tick, before the browser paints, each presenter presents once:
   - `SpinePresenter` asks `SpineFrames.current()` for the frame. Only the cached pipeline steps
     that depend on pLo re-run. It hands a `SpineViewModel` to `SpineView`, which schedules one
     GPU redraw.
   - `PlotPresenter`, `PanelPresenter`, `StatsPresenter` and `StatusPresenter` do the same for
     their views. They get the very same frame object, so the layout ran once.

Nobody except the model decided anything about thresholds, and nobody except the views
touched the screen.

**Opening a dataset** works the same way: `PanelPresenter` calls `workspace.open(name)` →
`SessionModel` goes to "loading" → the fetch finishes → `SpineParamsModel.resetForDataset` →
`SessionModel` goes to "ready". Both changes land in one tick, so every view shows the new
dataset with its own thresholds in a single render. If you picked another dataset meanwhile,
the older request is ignored. The selection is cleared in the same step, because node ids
mean something else in another dataset.

**Clicking a node**:
1. `PointerGestures` sees a press and release that moved less than 4 px: a click, not a pan.
2. `SpineView` finds the nearest drawn node within 10 px and emits `nodeClicked(id, shift)`.
3. `SpinePresenter` calls `selection.selectOnly(id)` (or `toggle(id)` with shift).
4. In the next tick: `SpinePresenter` sends only new **rings** (the spine content is unchanged,
   so it is not re-sent); `PlotPresenter` adds a tick at the node's persistence;
   `SelectionPresenter` lists the node with f, P and region size.
5. If you later raise pLo so the peak merges, nothing in the selection changes; the derived
   view shows a dashed ring on the peak it merged into and says "merged into max #k".

---

## 6. How to add things

| You want to add… | Create | Register / wire | Don't touch |
|---|---|---|---|
| A file format (pipeline) | a reader function in `io/readers.py` | `READERS` entry | other readers |
| A graph backend (pipeline) | `sources/<name>_source.py` implementing `ExtremumGraphSource` | `SOURCES` entry | `run.py`, core |
| A colour map | function in `core/` | mapper that picks colour maps | views |
| A projection (high-D → 2-D) [planned] | `core/projection/<name>.ts` implementing `ProjectionStrategy` + test | projection registry | views, presenters |
| A new view of the data | `views/<name>/contract.ts`, the view, `presenters/<Name>Presenter.ts` (extends `Presenter`), tests with a fake view | `main.ts` | other views/presenters |
| A new piece of app state | a field + named methods on its one owning model, + test | the state table above | views |
| A use case touching two models | a method on `Workspace` (or a sibling use-case class), + test | the presenter that triggers it | the models' subscriptions |

### Worked example: a "sample projection" view for high-D data [planned]

Goal: scatter all samples of a 4-D dataset in 2-D, coloured by their region at the current pLo.

1. `core/projection/pca.ts`: `PcaProjection implements ProjectionStrategy` (pure, tested on a
   flat 3-D cloud whose answer is known).
2. `model/ProjectionModel.ts`: `{ strategyId, axes }` with `setStrategy`, `setAxes`.
3. Cached selectors `projectedSamples(data, strategy, axes)` and `sampleColors(labels, rep)`
   (like `SpineFrames`), so only colours change when pLo moves.
4. `views/projection/contract.ts` + `ProjectionView.ts` (WebGL points; reports
   `hovered` / `brushed`).
5. `presenters/ProjectionPresenter.ts` (extends `Presenter`): listens to Session, Params,
   Projection, Selection; builds the view model; sends brushes to `SelectionModel`. Tested
   with a fake view.
6. One line in `main.ts`. Rows added to the tables in this document.

No existing view, presenter or model needs to change, because new features plug in through
the same contracts.

---

## 7. History

**Linked selection (F1, November 2026).** Hover, click and shift-click nodes on the spine;
rings, plot ticks and a details list stay in sync through `SelectionModel`. `SpineView` was
split along the way: camera maths into `Viewport`, input into `PointerGestures`.

**The move to MVP.**

Until November 2026 one class, `app/App.ts`, built everything, ran the pipeline, formatted the
stats and status text, and kept the loaded data in loose fields; `Panel` wrote to the store
directly and clamped thresholds itself. It was split into the models, presenters and views
above. Behaviour is unchanged, with three fixes that came out of the split:
- choosing a second dataset before the first finished loading could show the first one;
- the double-click listener on the spine canvas was never removed on dispose;
- a startup error such as "WebGL2 is required" was thrown before the status line existed and
  never shown.

---
name: topospine-dev
description: Project rules for all code in the Topospine repo (topological spines, extremum graphs, the TypeScript/Three.js web viewer and the Python pipeline). Enforces OOP + SOLID, Model-View-Presenter (MVP) in the web app, explicit state management, the docs/ARCHITECTURE.md contract, and the docs/DECISIONS.md decision log (every choice between options is recorded there). Use this skill for ANY change in this repo: new features (especially high-dimensional data visualization: linked views, projections, brushing, parallel coordinates, scatterplot matrices), refactors, bug fixes, tests, or questions about where code belongs. Use it together with graphics-project, which supplies the milestone/file-by-file workflow; where the two disagree on architecture, this skill wins.
---

# Topospine development rules

Topospine = `topospine_m1_core/topospine/`:
- `pipeline/`: offline Python that computes extremum graphs and writes the file contract.
- `web/`: the browser viewer (TypeScript, Three.js, Vite, Vitest).
- `docs/ARCHITECTURE.md`: the plain-language map of every component. **Read it before touching code.**

Workflow (phases, trackers, one file per turn, stop for approval) comes from the `graphics-project` skill. This skill adds the architecture and code rules every file must follow.

## Before writing any code

0. Skim the Index of `docs/DECISIONS.md` for settled choices that touch the change.
1. Read `docs/ARCHITECTURE.md`. Find the layer (Model / Presenter / View / Core / Render / Service) the change belongs to. If it fits none, stop and propose an architecture change first.
2. For a feature, fill in the **feature card** below and get approval before file 1.
3. Read `references/mvp-and-state.md` whenever you add or change a model, presenter or view.
4. Read `references/highdim-features.md` for any high-dimensional visualization feature.

### Feature card (present it, then stop)

```
Feature: <name>
User story: As a <user> I want to <action> so that <insight>.
State:      new fields + which model owns each (one owner per field)
Derived:    new pure selectors in core/ (inputs → output, memoised on?)
Views:      new/changed view interfaces (view model in, events out)
Presenters: who listens to what, who calls which model method
Files:      path | responsibility | layer | test file
Docs:       sections of ARCHITECTURE.md to add/update
```

## The architecture in one picture (web app)

```
             user input                                 pixels
                 │                                         ▲
                 ▼                                         │
   ┌──────────────────────────┐  view model (plain data)   │
   │ VIEW  (passive, DOM/GPU) │◀───────────────────────────┤
   └────────────┬─────────────┘                            │
                │ intent events ("thresholdDragged")       │
                ▼                                          │
   ┌──────────────────────────┐   reads + selectors   ┌────┴──────┐
   │ PRESENTER (no DOM)       │──────────────────────▶│  maps     │
   │ intent → model method    │                       │  state →  │
   │ model change → view model│◀──── change event ────│  VM       │
   └────────────┬─────────────┘                       └───────────┘
                │ calls named methods (setThresholds, openDataset)
                ▼
   ┌──────────────────────────┐   uses   ┌─────────────────────────┐
   │ MODEL (state + rules)    │─────────▶│ CORE (pure algorithms)  │
   │ Store-backed, observable │          │ SERVICES (fetch, I/O)   │
   └──────────────────────────┘          └─────────────────────────┘
```

Data flows one way: **View → Presenter → Model → Presenter → View.** Nothing else.

## Hard rules (a review fails if any is broken)

### Layer dependencies (enforce with imports)
| Layer | May import | Must never import |
|---|---|---|
| `core/` | `core/` only | DOM, `three`, models, presenters, views |
| `model/` | `core/`, `services/` interfaces | DOM, `three`, presenters, views |
| `services/` | `core/` types | models, presenters, views |
| `presenters/` | `model/`, `core/`, view **interfaces** | DOM APIs, `three`, concrete views |
| `views/` | `render/`, `core/` types, own view-model types | models, `Store`, presenters, algorithms |
| `render/` | `three`, `core/` types | DOM outside its canvas, models |
| `main.ts` | everything | (it is the only place that does) |

### MVP
- **Views are passive.** They draw a view model and emit intent events. No `store.set`, no business rules (clamping, validation), no formatting decisions beyond layout. The `pHi ≥ pLo` rule belongs in the model, not in a slider callback.
- **Every view has an interface** (`ISpineView`, `IPlotView`, …) in the same file or in `views/<name>/contract.ts`. Presenters depend only on the interface (Dependency Inversion), so presenter tests use a fake view.
- **View models are plain, immutable, ready-to-draw data**: strings already formatted, colours already resolved, typed arrays already packed. A view does not compute what to show, only how to draw it.
- **One presenter per view** (or per tightly coupled view group). A presenter does three things only: subscribe to models, map state to a view model, translate intents into model method calls.
- **`main.ts` is the composition root.** It constructs models, services, views, presenters and wires them. No logic there.

### State management
- **One owner per piece of state.** Every field appears in exactly one model. The state table in `ARCHITECTURE.md` lists them; update it when you add a field.
- **Three kinds of state, three homes:**
  1. *App state* (shared, user-meaningful, could go in the URL): in a model, e.g. thresholds, selected dataset, selected nodes, active projection.
  2. *Derived state*: never stored. Computed by memoised pure selectors (`core/derive.ts` pattern), keyed on input identity.
  3. *Ephemeral view state* (drag in progress, hover pixel, camera pan/zoom): private to the view. Promote it to a model the moment a second component needs it.
- **Mutation only through named model methods** (`params.setThresholds(lo, hi)`, `selection.toggle(id)`). Methods enforce invariants. `Store.set` is private to the model that owns the store.
- **Immutable snapshots.** `get()` returns `Readonly<S>`; never mutate a returned object or a typed array inside state. Replace, don't edit.
- **Async is a state machine.** Loading uses a discriminated union `{ status: "idle" } | { status: "loading", name, requestId } | { status: "ready", data } | { status: "error", message }`. Late responses whose `requestId` is stale are dropped.
- **Every subscription returns an unsubscribe**; every class that subscribes, listens or allocates GPU memory has `dispose()`, and its owner calls it. `main.ts` disposes everything on hot reload.

### OOP and SOLID (see graphics-project `references/oop-solid.md`)
- **S**: one reason to change per class. If you need "and" to describe it, split it.
- **O**: new technique / layout / projection / colour map / reader = new file implementing an existing interface + one registry entry. No `if (kind === …)` chains outside a registry or the one place that picks a strategy.
- **L**: every implementation of an interface is usable wherever the interface is; no `instanceof` checks on it.
- **I**: small interfaces. A view that only draws doesn't implement event binding it never uses.
- **D**: depend on interfaces; inject concretes from `main.ts` (web) or the registries (`SOURCES`, `READERS` in the pipeline).
- **Abstractions must pay rent**: add an interface only for 2+ implementations, a likely-to-change boundary, or a test seam (all views qualify via presenter tests).

### Code style (match the existing files)
- Each file starts with a doc comment: its role, what it deliberately does *not* do, and the data flow if non-trivial. Comments explain *why*, not *what*.
- One exported class per file; file name = class name. Pure-function modules in `core/` are named for the concept (`thresholds.ts`).
- Aim for files under ~200 lines and functions under ~40. Past that, split by responsibility.
- TypeScript: `strict`, no `any`, no non-null `!` on values that can really be missing; `readonly` by default; typed arrays for per-node data.
- Python: type hints everywhere, `@dataclass(frozen=True)` for value objects, `Protocol` for interfaces, NumPy-only `core/`.
- No magic numbers: tunables go in a defaults object (`DEFAULT_PARAMS`, `DEFAULT_STRESS`) or the YAML config.

### Tests (written in the same turn as the code)
- `core/`: unit tests with small worked examples (as today).
- `model/`: invariants, no-op updates don't notify, stale async results are dropped.
- `presenters/`: fake view + real models. Assert the view model produced and the model calls caused by each intent. No DOM.
- `views/`: only what can't be tested elsewhere (screenshot/golden image via the existing headless setup).
- Pipeline: pytest, same structure as `pipeline/tests/`.

### Documentation (part of done)
Any new component, state field or extension point updates `docs/ARCHITECTURE.md` in the same change: its row in the component tables, the state table, and (for a new extension point) the "How to add…" section. Use plain words; define any topology term on first use.

### Decision log (`docs/DECISIONS.md`)
Every choice between real options is logged in `docs/DECISIONS.md`, in the same turn it is made.
- **What counts**: the user picks between options you offered; the user approves your proposal; you pick a method, tool, default, scope cut or install route that someone could later ask "why?" about; something is deliberately deferred or rejected. Also log a decision you discover was made earlier but never written down ("recorded after the fact").
- **What doesn't**: per-file implementation detail (goes in the file notes, e.g. `M1_CORE_NOTES.md`) and deviations from the paper (go in `DEVIATIONS.md`; link both ways when one causes the other).
- **How**: add a row to the Index table and a card with the next ID `D-xxx`, using the same headings as the existing cards: Date · Status · Decided by, The question, What we chose, Why, Options we didn't take, What it means later, Revisit if (plus "Where in the code" once code exists). Plain words, short bullets, a small table or example when it helps a newcomer.
- **Who decided**: be accurate. "Priyank (approved Claude's proposal)" is not the same as "Claude chose". Never log a decision as approved before the user approved it; a proposal still waiting for approval is not logged yet.
- **Never rewrite history**: when a decision changes, add a new entry and change only the old one's status line ("Changed by D-xxx" / "Replaced by D-xxx").
- Before proposing a design, read the Index so you don't re-open a settled question without saying so.

## Pipeline (Python) note

MVP is for interactive UI and does not apply to the batch pipeline. There the rules are: pure NumPy `core/`, I/O in `io/`, backends behind the `ExtremumGraphSource` Protocol, formats/backends added via the `READERS` / `SOURCES` registries, one YAML config per run. Any change to the file contract (`graph.json`, `*.bin`) updates `pipeline/schema/spine.schema.json`, `web/src/core/parse.ts`, and their tests together.

## Review checklist (run before saying a file or milestone is done)

- [ ] Imports respect the layer table.
- [ ] No view touches a model; no presenter touches the DOM.
- [ ] Every new state field has one owner and a row in the state table.
- [ ] Nothing derived is stored.
- [ ] Invariants live in model methods.
- [ ] Async paths handle stale responses and errors as states.
- [ ] `dispose()` cascades; no leaked listeners/subscriptions/GPU objects.
- [ ] Tests for model + presenter (+ core) pass: `cd web && npm test`, `cd pipeline && pytest -m "not slow"`.
- [ ] `docs/ARCHITECTURE.md` updated.
- [ ] Every decision made this turn has an entry in `docs/DECISIONS.md` (index row + card).

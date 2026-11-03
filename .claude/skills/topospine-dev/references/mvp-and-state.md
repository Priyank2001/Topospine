# MVP and state management: patterns for the Topospine web app

Read this when you add or change a model, presenter or view. Every pattern below exists in
`web/src/`; copy the real file next to the one you are writing.

## Contents
1. Folder layout
2. Model pattern
3. Async: synchronous state machines + a use case
4. Derived state
5. View contract pattern
6. Presenter pattern
7. Composition root
8. Testing each piece
9. Anti-patterns (from the pre-MVP code)

---

## 1. Folder layout

```
web/src/
├── main.ts                     composition root: build + wire + dispose; shows startup errors
├── model/
│   ├── Store.ts                generic observable snapshot (private to each model)
│   ├── SessionModel.ts         index + load state machines (sync, request ids)
│   ├── SpineParamsModel.ts     thresholds + options with invariants
│   ├── Workspace.ts            use cases spanning models: start(), open()
│   └── SpineFrames.ts          derived: cached SpineFrame for (dataset, params)
├── services/
│   ├── DatasetSource.ts        interface + DatasetEntry
│   └── HttpDatasetSource.ts    fetch from public/data
├── core/                       pure algorithms, mappers (spine/overlay.ts, spine/levelColors.ts), format.ts
├── presenters/
│   ├── Presenter.ts            base: subscriptions, per-tick coalescing, owns + disposes its view
│   ├── SpinePresenter.ts  PlotPresenter.ts  PanelPresenter.ts  StatsPresenter.ts  StatusPresenter.ts
├── views/<name>/
│   ├── contract.ts             I<Name>View, <Name>ViewModel, <Name>ViewEvents (no DOM imports)
│   └── <Concrete>View.ts       implements the contract
└── render/                     GPU resources and shaders (owned by views)
```

`core/spineState.ts` (the `SpineParams` type + defaults) stays in core because the pure
`SpinePipeline` takes it; `SpineParamsModel` owns the live instance.

## 2. Model pattern

A model = private `Store` + `state` getter + `subscribe` + named methods that enforce rules.

```ts
export class SpineParamsModel {
  private readonly store: Store<SpineParams>;
  get state(): Readonly<SpineParams> { return this.store.get(); }
  subscribe(fn: Listener<SpineParams>): () => void { return this.store.subscribe(fn); }

  setNoise(pLo: number): void { this.store.set({ pLo: Math.min(clampNonNegative(pLo), this.state.pHi) }); }
  setVariation(pHi: number): void { this.setThresholds(this.state.pLo, pHi); }
  resetForDataset(data: SpineData): void { this.setThresholds(suggestNoiseThreshold(data), Infinity); }
}
```

Rules:
- Methods are named for user meaning (`setNoise`), not for fields (`setPLo`).
- Models are **synchronous** and never subscribe to each other.
- Never return a mutable reference into state.

## 3. Async: synchronous state machines + a use case

The model holds the states; a use case class (`Workspace`) does the awaiting and reports
back through transitions.

```ts
// SessionModel: sync transitions, request ids
beginLoad(name): number           // -> { status: "loading", name, requestId }
isCurrent(requestId): boolean
finishLoad(requestId, data): boolean   // ignored (false) if stale
failLoad(requestId, message): boolean

// Workspace.open: order matters
const id = session.beginLoad(name);
const data = await source.load(name);
if (!session.isCurrent(id)) return;     // superseded
params.resetForDataset(data);           // first: thresholds for the new data
session.finishLoad(id, data);           // then: publish ready (same tick -> one render)
```

New cross-model behaviour = a new `Workspace` method (or a sibling use-case class), with a
test using `ControlledSource` from `tests/fakes.ts`.

## 4. Derived state

Never stored; cached on input identity with `memo` from `core/derive.ts`.
- Shared by several presenters → a class in `model/` like `SpineFrames` (`current()` returns a
  discriminated union `none | ok | error`).
- Used by one presenter only → a `memo` field on that presenter (`PlotPresenter.curves`,
  `SpinePresenter.overlay`).

## 5. View contract pattern

```ts
// views/plot/contract.ts — no DOM, no three
export interface PlotViewModel { readonly t: Float64Array; /* … */ readonly loLabel: string; }
export interface PlotViewEvents { noiseDragged(pLo: number): void; variationDragged(pHi: number): void; }
export interface IPlotView { bind(events: PlotViewEvents): void; render(vm: PlotViewModel): void; dispose(): void; }
```

- View models are ready to draw: labels formatted, fills resolved, arrays packed.
- Theme-dependent colours are the view's job (SpineView mixes outlines with its theme ink).
- Views keep only interaction state (drag, focus, camera). They emit raw values; models clamp.
- A view with no user events has no `bind` (Interface Segregation): `IStatsView`, `ITextView`.

## 6. Presenter pattern

```ts
export class PlotPresenter extends Presenter {
  private readonly curves = memo(plotCurves);
  constructor(private readonly view: IPlotView, private readonly session: SessionModel, private readonly params: SpineParamsModel) {
    super(view);                                            // takes ownership of the view
    view.bind({ noiseDragged: (p) => params.setNoise(p), variationDragged: (p) => params.setVariation(p) });
    this.listen(session.subscribe(() => this.invalidate()), params.subscribe(() => this.invalidate()));
    this.invalidate();                                      // present the current state
  }
  protected present(): void {
    const d = this.session.data;
    if (!d) return;
    const { pLo, pHi } = this.params.state;
    this.view.render({ ...this.curves(d), pLo, pHi, loLabel: `noise ${fmt(pLo)}`, hiLabel: `variation ${fmtThreshold(pHi)}` });
  }
}
```

- Subscriptions only call `invalidate()`; all work happens in `present()`, once per tick.
- A presenter needing an action owned elsewhere gets it as an injected command interface
  (`PanelCommands.fitView`), never a reference to another view.
- Pure mapping helpers are exported (`plotCurves`, `statsRows`, `statusMessage`) or live in
  `core/` so they can be tested directly.

## 7. Composition root

`main.ts` constructs `SessionModel`, `SpineParamsModel`, `Workspace(HttpDatasetSource, …)`,
`SpineFrames`, then each `new XPresenter(new XView(el), …models)`, calls `workspace.start`,
and disposes all presenters on HMR. A new feature adds one line here.

## 8. Testing each piece

| Piece | How | Example |
|---|---|---|
| Model | plain Vitest | `setThresholds(5, 2)` → `pHi === 5`; same value twice notifies once |
| Use case | `ControlledSource` (resolve/reject per name) + `flush()` | open a, open b, resolve b, resolve a → ready with b, thresholds untouched |
| Derived | real models | same state → same frame object; params change → new frame |
| Presenter | fake view from `tests/presenters/fakeViews.ts` + `models()` from `tests/presenters/setup.ts` | one dataset open → exactly one render; intent → model state |
| Mapper | pure input/output | `buildOverlay` packs 2 floats per node in node order |
| View | headless Chromium screenshot (Playwright, `--use-gl=swiftshader`) | page loads, drag changes stats, no console errors |

Add a `Fake<Name>View extends Recorder<VM>` to `fakeViews.ts` for every new view contract.

## 9. Anti-patterns (from the pre-MVP code; don't reintroduce)

- One class that composes, presents and formats DOM (the old `app/App.ts`).
- Views calling `store.set` or clamping values (the old `ui/Panel.ts`).
- Async without request ids (a slow first dataset replaced a later choice).
- Loose flags as state (`needsFit`); derive from a change instead (fit when the data identity changes).
- Anonymous event listeners that can't be removed in `dispose()`.
- `as any` to reach a library method.

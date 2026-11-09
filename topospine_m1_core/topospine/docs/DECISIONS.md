# Decision log

Every choice we made between real options, in the order we made it, with the reason.
If you ever wonder "why is it like this?", look here first.

**What goes where**

| File | Answers |
|---|---|
| `DECISIONS.md` (this file) | *Why did we pick this option over the others?* Project-level choices: methods, tools, scope, defaults. |
| `DEVIATIONS.md` | *Where do we differ from the paper (Correa et al. 2011), and how?* |
| `M1_CORE_NOTES.md`, `M2_NOTES.md` | *Why is this one file written this way?* Small per-file design notes. |
| `ARCHITECTURE.md` | *What exists now, and who talks to whom?* |

**How to read a status**

- **Active**: this is how things are now.
- **Deferred**: we chose *not now*; the "Revisit if" line says what would change that.
- **Changed by D-xxx**: a later decision changed part of this one. Read both.
- **Replaced by D-xxx**: no longer true; kept so the history makes sense.

Old entries are never rewritten. When we change our mind, we add a new entry and update
the old one's status line only.

---

## Index

| ID | Date | Decision | Status |
|---|---|---|---|
| [D-001](#d-001) | M1 | The TTK adapter takes only TTK's regions; saddles come from our own rule | Changed by D-004, D-007 |
| [D-002](#d-002) | 2026-11-04 | No Tachyon backend for now | Deferred |
| [D-003](#d-003) | 2026-11-04 | TTK installed in its own Intel (x86-64) conda env, run under Rosetta | Active |
| [D-004](#d-004) | 2026-11-04 | Split graph extraction into two swappable blocks: *regions* and *saddles* | Active |
| [D-005](#d-005) | 2026-11-04 | Old configs (`source: {type: native}` / `{type: ttk}`) keep working as presets | Active |
| [D-006](#d-006) | 2026-11-04 | `--regions` / `--saddles` command-line flags can override the YAML | Active |
| [D-007](#d-007) | 2026-11-04 | TTK saddles are only allowed together with TTK regions | Active |
| [D-008](#d-008) | 2026-11-04 | Caller-supplied `ranks` are checked to be a permutation, not trusted | Active |
| [D-009](#d-009) | 2026-11-04 | TTK saddles with fewer than two uphill separatrices are dropped | Changed by D-011 |
| [D-010](#d-010) | 2026-11-04 | A TTK saddle with more than two uphill separatrices is an error, not split | Active |
| [D-011](#d-011) | 2026-11-04 | When TTK's saddles leave the peaks in pieces, join the pieces with our highest boundary saddles | Active; revisit condition met (M3_NOTES.md) |
| [D-012](#d-012) | 2026-11-04 | TTK's segmentation arrays are scored by TTK's own maxima, not our stencil's | Active |
| [D-013](#d-013) | 2026-11-04 | How `--regions` / `--saddles` treat parameters, presets and `--out` | Active (awaiting Priyank's review) |
| [D-014](#d-014) | 2026-11-04 | Remove noise by simplifying the field with TTK before extraction | Active, scheduled after D-016 (premise corrected, see card) |
| [D-015](#d-015) | 2026-11-04 | Simplification: every method sees the simplified field, it is what gets exported, threshold is a fraction of the range | Active, scheduled after D-016 |
| [D-016](#d-016) | 2026-11-04 | Add a stencil matching TTK's triangulation first, then simplification | Active |
| [D-017](#d-017) | 2026-11-04 | The TTK-mesh stencil is selected with `connectivity: ttk` | Active |
| [D-018](#d-018) | 2026-11-04 | The three `gauss3d*` cross-check configs use `connectivity: ttk` | Active |
| [D-019](#d-019) | 2026-11-05 | `simplify` on a non-`ttk` stencil warns, but still runs | Active |

---

<a id="d-001"></a>
### D-001 · The TTK adapter takes only TTK's regions

**Date** M1 (recorded here on 2026-11-04) · **Status** Changed by D-004, D-007 · **Decided by** M1 design

**The question.** TTK's Morse-Smale complex gives both regions (which peak each sample
flows up to) and saddles with their connections. Which parts do we use?

**What we chose.** Only the regions. Saddles are found with the same rule as our native
method (the highest point on the border between two regions).

**Why.**
- TTK's saddle output (port numbers, array names, type codes) has changed between TTK
  releases. The per-sample region ids have not.
- With one saddle rule for both backends, any difference between TTK and native is a
  difference in regions only, which is easy to explain.

**Options we didn't take.** Reading TTK's saddles directly: fragile across versions, and we
had no TTK install to test against.

**What changed later.** D-004 made the saddle rule a swappable block, and TTK's own saddles
became an option. The `ttk` preset still behaves exactly as described here (D-005). Details
in `DEVIATIONS.md` #9.

---

<a id="d-002"></a>
### D-002 · No Tachyon backend for now

**Date** 2026-11-04 (recorded after the fact) · **Status** Deferred · **Decided by** never
explicitly decided; recorded when Priyank asked why it was missing

**The question.** Tachyon (Ande, Subhash & Natarajan, a fast parallel method for extremum
graphs) comes from our own lab. Why don't we use its code?

**What we chose.** Nothing yet. The code is ready for it (a new backend is one new file plus
one registry entry), but no adapter was written.

**Why (best reconstruction).**
- We would use only part of it. The persistence values the app needs come from the spines
  paper's Algorithm 1, not from Tachyon's own simplification, so Tachyon would only replace
  the fast first step.
- As far as we know it handles 3-D grids only. Our point-cloud (high-dimensional) data would
  still need the native method.
- Building a research C++ code is costly, and speed was not our bottleneck. Graph *size* on
  noisy data was, and a faster solver doesn't fix that.

**Revisit if.** The lab shares the code with a usable licence, or large volumes (e.g. the
klacansky datasets) become too slow with the native method. With D-004 in place it would
plug in as a region block and/or a saddle block.

---

<a id="d-003"></a>
### D-003 · TTK installed in its own Intel conda env, run under Rosetta

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank asked for TTK; Claude chose
the install method

**The question.** How do we get TTK on this Apple Silicon Mac to compare against?

**What we chose.** `micromamba` (from Homebrew) with a separate env `topospine-ttk` at
`~/mamba/envs/topospine-ttk`. It has TTK 1.3.0, VTK 9.4.1, Python 3.11, and the pipeline
installed in editable mode. It is an **Intel (osx-64) env running under Rosetta**.

```
export MAMBA_ROOT_PREFIX=~/mamba
micromamba run -n topospine-ttk pytest -m slow
micromamba run -n topospine-ttk python -m topospine.cli configs/gauss3d_ttk.yaml
```

**Why.**
- conda-forge has no Apple Silicon (osx-arm64) build of TTK. The Intel build exists and runs
  under Rosetta.
- A separate env leaves the everyday `pipeline/.venv` untouched and fast.

**Options we didn't take.**
- Building TTK from source for arm64: hours of work, and a fragile build.
- Putting TTK in `.venv`: impossible, because TTK is not on PyPI.

**What it means later.**
- TTK timings on this machine include Rosetta overhead. Don't report them as a fair speed
  comparison. Time TTK on Linux for the report.
- The first import after an update is slow (minutes) while Rosetta translates the libraries.

**Revisit if.** conda-forge publishes an osx-arm64 TTK build.

**First result.** The real-TTK test passed for the first time. On `gauss3d`, native and TTK
give the identical graph: 4 peaks, 6 saddles, 12 arcs, same persistence values.

---

<a id="d-004"></a>
### D-004 · Two swappable blocks: regions and saddles

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (approved Claude's proposal)

**The question.** Before, each backend did the whole job in one piece, so we couldn't mix
methods or compare one step at a time. How should extraction be organised?

**What we chose.** Two blocks, each chosen in the config:

| Block | Job | Methods |
|---|---|---|
| Regions | For every sample, which peak it flows up to | `ascent` (ours, grids and point clouds), `ttk` (grids) |
| Saddles | The passes between regions, each with its two connections | `boundary` (ours), `ttk` (TTK's own saddles) |

```yaml
source:
  regions: {type: ttk}
  saddles: {type: ttk}
  connectivity: 26
```

**Why.**
- Changing one block at a time tells us *which step* causes a difference (an ablation for
  the report).
- A new method (e.g. Tachyon, D-002) is one new file plus one registry entry.
- Everything after this step (Algorithm 1, histograms, export, the web app) is unchanged.

**Options we didn't take.**
- One backend per combination (`ttk_full`, `ttk_regions`, …): the number of backends grows
  with every new method.
- An `if method == …` chain inside one backend: it breaks the project's open/closed rule.

**What it means later.** Comparing combinations shows exactly which step is responsible for
a difference. D-007 limits which combinations are allowed.

**Where in the code.** `core/gradient_flow.py` (shared graph assembly), `sources/` (blocks
and registries).

---

<a id="d-005"></a>
### D-005 · Old configs keep working as presets

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (approved Claude's proposal)

**What we chose.** `source: {type: native}` means `ascent` + `boundary`, and
`source: {type: ttk}` means `ttk` regions + `boundary` saddles: exactly what they did before.

**Why.** All 20+ existing configs, and their outputs, stay valid and reproducible.

**Option we didn't take.** Rewriting every config to the new keys: churn, and old output
folders would no longer match their configs.

---

<a id="d-006"></a>
### D-006 · Command-line flags can override the YAML

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (approved Claude's proposal)

**The question.** To compare methods, do we write one YAML per combination, or override the
methods from the command line?

**What we chose.** Both work. `--regions` and `--saddles` override the YAML:

```
topospine configs/klacansky_bonsai.yaml --regions ttk --saddles ttk
```

Two safeguards:
1. When a flag changes a method, the output folder gets a suffix (`out/bonsai` becomes
   `out/bonsai_ttk-ttk`), so combinations never overwrite each other. In the web viewer
   each combination shows up as its own dataset.
2. `meta.json` records the methods that actually ran, so a result can always be traced
   even though the YAML alone no longer says how it was made.

**Why.** 17 klacansky configs × 3 combinations would be ~50 near-identical YAML files.

**Option we didn't take.** YAML only: the most reproducible, but heavy duplication for
comparison sweeps.

**What it means later.** To reproduce a result, read `meta.json` in its output folder, not
just the YAML.

---

<a id="d-007"></a>
### D-007 · TTK saddles only together with TTK regions

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (approved Claude's proposal)

**The question.** Should `regions: ascent` + `saddles: ttk` be allowed?

**What we chose.** No, for now. It is rejected with a clear message. Allowed combinations:

| Regions \ Saddles | `boundary` | `ttk` |
|---|---|---|
| `ascent` | yes (native) | **no** |
| `ttk` | yes (old `ttk` preset) | yes (full TTK) |

**Why.** Our ascent and TTK don't find exactly the same peaks, mostly on noisy data. With
mixed blocks:
- A peak we find but TTK doesn't gets no saddles. Algorithm 1 then gives it infinite
  persistence, so **the noise slider can never hide it**: a fake "important" peak.
- A peak TTK finds but we don't sits on the slope of one of our regions. Its saddles attach
  to that region's peak, which creates fake loops.
- Comparisons stop being clean: you couldn't tell a saddle-rule difference from a
  peak-mismatch difference.

With this rule, each comparison changes exactly one thing:
`ascent+boundary` vs `ttk+boundary` = regions only; `ttk+boundary` vs `ttk+ttk` = saddles only.

**How it is enforced.** Each saddle method declares which region method it needs, and the
composed source checks that in one place (no `if` chains).

**Revisit if.** We want the mixed combination as an explicit ablation. Then we write down a
rule for matching TTK peaks to our regions (a new entry here), and lift the restriction in
one line.

---

<a id="d-008"></a>
### D-008 · Caller-supplied ranks are checked, not trusted

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (picked option (a) of two
Claude offered)

**The question.** After the D-004 split, `assemble_flow` and `boundary_saddles` accept a
`ranks` array from the caller (so the O(n log n) sort runs once, not twice). Turning ranks
into "which sample has rank r" uses the O(n) trick `out[ranks] = arange(n)`, which is right
**only** if `ranks` is a permutation of 0..n-1. Do we trust callers?

**What we chose.** (a) Check it: every rank in 0..n-1, each exactly once
(`np.bincount(...).max() == 1`). A bad array raises `ValueError` instead of silently
placing a peak at the wrong sample. The length is checked too.

**Why.**
- The failure is silent. A repeated rank overwrites a sample; a missing rank leaves a slot
  of uninitialised memory, which usually *looks* valid (often `0`, a real sample index). We
  showed a peak moving from f = 3.0 to f = 2.0 with no error.
- The check is O(n): small next to the sort that made the ranks.

**Options we didn't take.** (b) Don't accept `ranks` from callers at all: always safe, but
every run pays a second O(n log n) sort (noticeable on 256³ volumes).

**What it means later.** The check catches *malformed* ranks, not ranks computed from the
wrong values (e.g. from f when the values are −f): those are still a valid permutation.
Callers should get ranks from `sample_ranks(values)` of the same values.

**Where in the code.** `core/gradient_flow.py` · `_sample_at_rank`, `assemble_flow`; tests
`test_*_rejects_ranks_that_are_not_a_permutation`. Full explanation with evidence:
`temp/explanation.md` (working notes, not part of the docs).

---

<a id="d-009"></a>
### D-009 · TTK saddles with fewer than two uphill separatrices are dropped

**Date** 2026-11-04 · **Status** Changed by D-011 · **Decided by** Priyank
(approved Claude's recommendation, one of three options offered)

**The question.** An uphill separatrix is the path from a saddle up to a peak. In our graph
every saddle has exactly two arcs, one to each peak it joins. Many of TTK's saddles have
fewer than two uphill separatrices, because a path runs into the domain border instead of
reaching a peak. What should the `ttk` saddle method do with them?

| Dataset | saddles | 2 uphill | 1 uphill (border / interior) | 0 uphill |
|---|---|---|---|---|
| clean `bumps3d` | 9 | 1 | 8 (8 / 0) | 0 |
| noisy `bumps3d` (σ = 0.02) | 883 | 392 | 449 (235 / 214) | 42 |

**What we chose.** Drop them. Each run reports how many were dropped (`SaddleReport`).

**Why.**
- A pass between peaks needs two peaks. A one-sided saddle has no second peak to join.
- On clean `bumps3d` this leaves exactly the one real saddle, so `ttk+ttk` matches native.

**Options we didn't take.**
- Make them a loop back to the one peak they reach: keeps every TTK saddle, but adds an arc
  TTK never produced and hundreds of loop nodes on noisy data.
- A config switch `drop | loop`: more code and settings for a comparison nobody asked for yet.

**What it means later (found right after the decision, same day).** On noisy `bumps3d`,
`ttk+ttk` has 5 maxima with infinite persistence instead of 1: some peaks were linked to
the rest only through dropped saddles, so the graph falls apart into pieces. A loop would
not fix this either. See "Revisit if".

**Revisit if** a `ttk+ttk` graph has more than one maximum of infinite persistence, which
already happens on noisy 3-D data. Needs a follow-up decision.

**Where in the code.** `sources/ttk_blocks.py` · `ttk_saddles`, `SaddleReport`; tests
`test_reads_passes_loops_and_drops_one_sided`, `test_real_ttk_plus_ttk_on_clean_bumps3d`.
Evidence: `temp/evidence/ttk_saddle_survey.py`, `temp/evidence/ttk_one_sided_saddles.py`.
Deviation: `DEVIATIONS.md` #17.

---

<a id="d-010"></a>
### D-010 · A TTK saddle with more than two uphill separatrices is an error

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (approved Claude's
recommendation over the original plan to split them)

**The question.** A degenerate saddle joins three or more peaks at once. What should the
`ttk` saddle method do if TTK reports one?

**What we chose.** Stop with a `ValueError` that names the saddle's cell and sample.

**Why.**
- None appeared on any test dataset, including noisy 3-D (883 saddles), once separatrices
  were grouped per saddle *cell*. (Grouping per *sample* had produced false 3-way saddles:
  two TTK cells can share their highest vertex.)
- Splitting rules for a case we have never seen would be untested guesswork.

**Options we didn't take.** Split a k-way saddle into k − 1 saddles at the same sample,
chained over its peaks (the original plan). Easy to add later if real data needs it.

**Revisit if** the error ever fires on a real dataset.

**Where in the code.** `sources/ttk_blocks.py` · `ttk_saddles`; test
`test_degenerate_saddle_is_an_error`.

---

<a id="d-011"></a>
### D-011 · Join the pieces TTK's saddles leave with our highest boundary saddles

**Date** 2026-11-04 · **Status** Active; its "revisit if" condition was met on
`klacansky_aneurism` (61 added vs 159 kept), see M3_NOTES.md · **Decided by** Priyank
(picked option (b) of three Claude offered)

**The question.** After D-009, `ttk+ttk` on noisy `bumps3d` split into pieces: groups of
peaks with no saddle between them. Each piece's top got infinite persistence, so the run
showed 5 "global maxima" instead of 1. How do we fix that?

**What we chose.** (b) Keep every TTK saddle. If the peaks are still in more than one piece,
run our boundary rule on TTK's regions and add its saddles **highest first**, each only if
it joins two different pieces. This is Kruskal's algorithm for a maximum spanning forest:
every piece is joined to the rest at its highest pass, as a merge tree would do.

| noisy `bumps3d` (σ = 0.02) | maxima | saddles | maxima with infinite persistence |
|---|---|---|---|
| native | 159 | 685 | 1 |
| `ttk+boundary` | 136 | 705 | 1 |
| `ttk+ttk` before (D-009 only) | 136 | 392 | 5 |
| `ttk+ttk` now | 136 | 395 (392 TTK + 3 ours) | 1 |

**Why.**
- Persistence needs one connected graph. Infinite persistence on a small noise peak is
  plainly wrong, and the spine would draw it as a top-level feature.
- Few of our saddles are added (3 here), and none when TTK's saddles already connect
  everything (clean `bumps3d`: 0), so `ttk+ttk` stays as close to TTK as possible.
- The boundary rule already works on TTK's regions (it is the `ttk` preset's saddle rule).

**Options we didn't take.**
- (a) Leave the pieces and document `ttk+ttk` as useful only on clean data.
- Loops for one-sided saddles (the rejected D-009 option): a loop joins a peak to itself,
  so it can't connect pieces.

**What it means later.** `ttk+ttk` is no longer pure TTK: the run summary must show how
many saddles were added (`SaddleReport.added`). The added saddles are ours, placed on the
highest border edge between pieces (DEVIATIONS.md #2), not TTK's exact saddle.

**Revisit if** `added` is large compared with `kept` on real data: then most of the graph
would come from our rule, and `ttk+boundary` is the more honest comparison.

**Where in the code.** `core/reconnect.py` · `count_pieces`, `connect_pieces`;
`sources/ttk_blocks.py` · `TtkSaddles.saddles`; tests `tests/core/test_reconnect.py`,
`test_lost_separatrices_are_bridged_by_the_highest_boundary_saddle`.

---

<a id="d-012"></a>
### D-012 · TTK's segmentation arrays are scored by TTK's own maxima

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (approved Claude's
recommendation)

**The question.** TTK gives two segmentation arrays (`AscendingManifold`,
`DescendingManifold`); which one holds the maxima's regions depends on TTK's naming
convention, so the M1 code scores each one: the fraction of its regions holding exactly
one maximum. Since M1 the maxima were found with **our** stencil. On noisy `bumps3d` no
array reached the 0.5 cut-off (Ascending 0.49, Descending 0.30), so the `ttk` preset failed.

**What we chose.** Count **TTK's own maxima** (its top-dimension critical cells) per region.

**Why.**
- Exact: each of TTK's maxima regions holds exactly one of TTK's maxima. Our stencil and
  TTK's mesh disagree on what a local maximum is (159 vs 135 here), which is what dragged
  the right array below the cut-off.
- Result on noisy `bumps3d`: Ascending 0.99, Descending 0.24. The right array wins clearly.

**Options we didn't take.** Lowering `min_score`: hides the mismatch rather than removing it,
and a lower cut-off would also let a wrong array through.

**What it means later.** Region picking now needs TTK's critical-points output (it already
runs; no extra cost). The 0.5 cut-off stays as a guard.

**Where in the code.** `sources/ttk_blocks.py` · `maximum_score`, `pick_maximum_regions`,
`TtkRegions`; `sources/ttk_output.py` · `ttk_maxima`; test
`test_regions_are_scored_by_ttk_maxima_not_our_stencil`.

---

<a id="d-013"></a>
### D-013 · How the method flags treat parameters, presets and `--out`

**Date** 2026-11-04 · **Status** Active (awaiting Priyank's review) · **Decided by** Claude
chose, while implementing D-006; not yet reviewed by Priyank

**The question.** D-006 says `--regions` / `--saddles` override the config. It doesn't say
what happens to the YAML parameters of a block, to a preset config, or to `--out`.

**What we chose.**

| Case | Behaviour |
|---|---|
| A flag names the method the config already uses | nothing changes: same config, no suffix |
| A flag changes a block's method | that block's YAML parameters are dropped (they belonged to the old method); the other block keeps its own |
| The config is a preset (`type: native` / `ttk`) | it becomes two blocks; only the shared keys (`connectivity`, `k`) carry over |
| A preset config has its own keys (e.g. `min_score`) | error: rewrite the config as `regions:` + `saddles:` |
| `--out DIR` is given | used exactly as given, no suffix |

`graph.json` records the result under `dataset.source` (e.g. `ttk+ttk`) and
`dataset.extraction` (each block's method and report, plus `connectivity` and `k`). The
source is built before the data loads, so a bad pair (D-007) fails at once.

**Why.**
- Parameters of one method mean nothing to another (`min_score` is a TTK regions setting).
  Silently passing them on would either crash or, worse, be ignored.
- Preset parameters don't say which block they belong to; guessing would hide mistakes.
- `--out` is the user saying exactly where to write.

**Options we didn't take.** Mapping preset parameters to blocks automatically (needs every
preset to describe its parameters; not worth it while no config uses them). Adding the suffix
to `--out` too (surprising when the user named the folder).

**Revisit if** a sweep needs block parameters on the command line (e.g. `--regions-param`).

**Where in the code.** `config.py` · `parse_source`, `with_methods`; `run.py` ·
`build_source`; `sources/composed_source.py` · `report`; tests `tests/test_config_methods.py`.

---

<a id="d-014"></a>
### D-014 · Remove noise by simplifying the field with TTK before extraction

**Date** 2026-11-04 · **Status** Active, scheduled after D-016. Its premise ("`ttk+ttk` overstates
persistence") turned out wrong: the boundary rule understates it (M3_NOTES.md §3); kept as a
noise cut ·
**Decided by** Priyank (picked one of four options Claude offered)

**The question.** On noisy data `ttk+ttk` overstates persistence (foot slice: 587 maxima
above 5 % of the range vs 481 native) because TTK lacks some passes (M3_NOTES.md). The
viewer's noise slider cuts by persistence, so it can't separate inflated noise peaks from
real ones. What should the user get to "cut the noisy part"?

**What we chose.** An optional simplification step: TTK's
`ttkTopologicalSimplificationByPersistence` removes every feature below a persistence
threshold from the field *before* extraction, so noise peaks and their saddles never appear.

**Why.**
- It removes the cause (noise features) instead of correcting numbers afterwards.
- It is standard TTK practice, and the filter exists in our TTK 1.3.0 install
  (`SetPersistenceThreshold`, `SetThresholdIsAbsolute`, `SetPairType`).

**Options we didn't take.**
- Restore lost passes (`fill: all`): removes the bias exactly, but makes `ttk+ttk`
  persistence equal to `ttk+boundary`, so the saddle comparison loses its meaning.
- Flag suspect peaks in `graph.json` and the viewer: transparent, but needs a file-contract
  change and web work.
- Viewer threshold only: no code, but the bias stays.

**Revisit if** simplification on real data removes features users consider real at
thresholds that are needed to remove the bias.

---

<a id="d-015"></a>
### D-015 · How simplification fits the pipeline

**Date** 2026-11-04 · **Status** Active, scheduled after D-016 · **Decided by** Priyank (picked Claude's
recommended option on all three points)

**The question.** Three design points of D-014: which methods see the simplified field, which
field is exported, and in what unit the threshold is given.

**What we chose.**

| Point | Choice | Rejected |
|---|---|---|
| 1. Who sees the simplified field | **every** method (native, `ttk+boundary`, `ttk+ttk`) | only the TTK methods: they would be compared on different fields |
| 2. What is exported and shown | **the simplified field**, so spine heights, regions and field agree | the original field for display: removed bumps would sit at heights no spine node has |
| 3. Threshold unit | **fraction of the value range** by default (`simplify: 0.02`); `absolute: true` for raw values | absolute only: the same number would mean different things per dataset |

**What it means later.**
- Any run with `simplify` needs the TTK env, even a native one.
- `graph.json` records `dataset.simplify` so a result can be traced to its threshold.
- A simplified output is not the raw data: DEVIATIONS.md gets an entry.

**Evidence after building it (2026-11-05, `temp/evidence/simplify_foot.py`, klacansky_foot).**
TTK cut 2117 -> 1679 maxima at 1 % and -> 594 at 5 %; the top five persistences stay the same
in every method, so real features survive. The guarantee "nothing left with 0 < p < t" holds
only on TTK's mesh: with `connectivity: ttk`, ascent+boundary leaves 0, and the TTK region
method leaves 1-2 maxima on the domain border (the D-009 border behaviour). With the shipped
`connectivity: 8`, the boundary saddles leave 65-89, because TTK removed noise on a different
mesh than the one we extract on. So `simplify` should be used with `connectivity: ttk`.

---

<a id="d-016"></a>
### D-016 · A stencil matching TTK's triangulation first, then simplification

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (picked Claude's
recommendation, one of four options offered)

**The question.** Checking against TTK's persistence diagram showed that the native-vs-TTK
persistence gap comes mainly from our stencil, not from noise: our 8/26-neighbour stencil
links both diagonals of every grid cell, TTK's triangulation only one. What do we build next?

| foot slice, ascent+boundary | maxima with p ≥ 5 % | values shared with TTK's diagram |
|---|---|---|
| full stencil (8), today's default | 493 | 1703 / 1736 |
| one-diagonal stencil (Freudenthal, orientation B) | 593 | 2080 / 2116 |
| TTK persistence diagram | 579 | |

**What we chose.** First add a stencil option that matches TTK's triangulation exactly (the
diagonal convention pinned down until our local-maxima counts equal TTK's). Then build the
simplification of D-014/D-015 on top as a noise cut. Today's defaults (8 / 26) stay, so every
existing output reproduces (D-005).

**Why.** It removes the root cause of the gap and makes native a fair reference for TTK;
simplification alone left the gap unchanged (foot at 5 %: 500 / 488 / 583).

**Options we didn't take.** Mesh stencil only (simplification shelved); simplification only
(gap stays); document and stop.

**Revisit if** no stencil orientation reproduces TTK's local maxima exactly; then the option is
"close to TTK" rather than "same mesh as TTK", and the notes must say so.

**Evidence.** `temp/evidence/persistence_vs_ttk_diagram.py`,
`temp/evidence/freudenthal_stencil.py`, `temp/evidence/simplify_precheck.py` (working notes).

---

<a id="d-017"></a>
### D-017 · The TTK-mesh stencil is selected with `connectivity: ttk`

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (picked Claude's proposed
name over the alternative)

**The question.** How does a config ask for the stencil of D-016 (the edges of TTK's
triangulated grid: one diagonal per square, 6 neighbours in 2-D, 14 in 3-D)?

**What we chose.** `connectivity: ttk`. In code the class is `FreudenthalNeighborhood`, the
textbook name of this subdivision.

**Why.** The config name says what it matches, so a user comparing with TTK finds it.

**Options we didn't take.**
- `connectivity: freudenthal`: precise, but only meaningful to someone who knows the term.
- A number (`6` / `14`): `6` already means "faces only" in 3-D.

**What we found while building it.** TTK's diagonal runs along the *negated* last array
axis (x): offsets {0,1}^d with x flipped. With it, our local maxima equal TTK's
piecewise-linear maxima vertex for vertex (2-D and 3-D, random and real data); every other
orientation differs. Test: `test_freudenthal_maxima_equal_ttk_pl_maxima` (slow).

---

<a id="d-018"></a>
### D-018 · The `gauss3d*` cross-check configs use `connectivity: ttk`

**Date** 2026-11-04 · **Status** Active · **Decided by** Priyank (picked Claude's
recommended option (b) of three)

**The question.** `gauss3d.yaml` (native), `gauss3d_ttk.yaml` (`ttk` preset) and
`gauss3d_ttk_ttk.yaml` (`ttk+ttk`) exist to compare methods on one volume. They all used the
26-neighbour stencil, which differs from TTK's mesh (D-016), so the comparison mixed method
and mesh. Switching changes their outputs, which D-005 promised to keep stable.

**What we chose.** (b) Switch **all three** to `connectivity: ttk` together. Switching only the
TTK configs would compare native on 26 with TTK on its mesh: the same mismatch again.

**What changes** (measured; maxima and saddle counts unchanged):

| config | persistence of the 3 finite maxima, % of range |
|---|---|
| `gauss3d`, `gauss3d_ttk` | 57.56 / 55.75 / 32.75 → 57.65 / 55.75 / 32.90 |
| `gauss3d_ttk_ttk` | 57.65 / 55.75 / 32.90 (unchanged) |

**Why.** These configs exist only as a cross-check, and the shipped example should show the
right setting for comparisons with TTK. The change is about 0.1 % of the range.

**Options we didn't take.** (a) Leave all three on 26: reproducible, but a silent
mesh mismatch. (c) Keep them and add three `connectivity: ttk` copies: six configs for one
volume.

**What it means later.** Outputs of these three configs made before this change used
`connectivity: 26`; `graph.json` records which one (`dataset.extraction.connectivity`).
After the switch all three methods give the same top persistence on `gauss3d`
(0.5748 / 0.5559 / 0.3281 of the range, as fractions).
This is a scoped exception to D-005: all other configs keep their stencils.

---

<a id="d-019"></a>
### D-019 · `simplify` on a non-`ttk` stencil warns, but still runs

**The question.** TTK simplifies on its own mesh. On another stencil (8, 26, ...) some
features below the threshold survive (klacansky_foot, 5 %: 87 left with ascent+boundary,
0 with `connectivity: ttk`; see D-015 evidence). What should a run do then?

**What we chose.** Run, and print a warning that names `connectivity: ttk` (`run.py`,
`SIMPLIFY_STENCIL_WARNING`).

**Options we didn't take.**
- Refuse to run: blocks comparisons on purpose ("how much does the stencil matter after
  simplifying?") and breaks configs that only add `--simplify`.
- Switch to the `ttk` stencil silently: the run would no longer match its config, the
  folder name would not show it, and stencil-only differences would look like effects of
  simplification.

**Revisit if** users routinely ignore the warning, or a second simplifier with another mesh
is added (then the check belongs on the simplifier, not in `run.py`).


### D-020 · Sixteen circles per canonical link

**The question.** A canonical link approximates the paper's Minkowski sum of circles along the
extremum-saddle arc (Sec. 4.1) with K sampled circles joined by tapered capsules. The code
used K = 8 (`DEFAULT_LINKS.knots`, and a hard-coded `knots: 8` in `core/derive.ts`). Is 8 too
coarse for the bulged lobes of the critical contour?

**What we chose.** K = 16 in both places. The default lives in `DEFAULT_LINKS`, and
`derive.ts` passes it explicitly, so the two must change together.

**Options we didn't take.**
- Keep 8: the outline of each link is visibly faceted on large radii.
- Make K adaptive to the radius: more code and a second parameter, with no evidence yet that a
  fixed count is the bottleneck.

**Revisit if** the cost of drawing 16 circles per link per level becomes visible on the largest
datasets, or if the faceting still shows at high zoom.

### D-021 · Radius proportional to volume by default

**The question.** Paper Sec. 4.2 makes a link's radius proportional to the enclosed volume.
The code defaulted to `"sqrt"` (area proportional to volume), which keeps small regions
visible next to large ones (DEVIATIONS #11). Which should be the default?

**What we chose.** `"linear"` (radius ∝ volume) in both `DEFAULT_LINKS` and the
`spineState` default. The panel option "Radius ∝ volume (paper)" remains, and "Area ∝
volume" is still selectable.

**Options we didn't take.**
- Keep `"sqrt"`: a visible deviation from the paper, which is the reference for this viewer.
- Remove the `"sqrt"` option: it is a useful view of small regions, and the choice is cheap to keep.

**Revisit if** small regions become unreadable at the default and users switch to area
encoding most of the time.

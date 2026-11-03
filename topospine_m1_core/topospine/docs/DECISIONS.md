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

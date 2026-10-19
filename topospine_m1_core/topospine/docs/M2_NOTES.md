# M2: the topological spine in the browser

Screenshots (headless Chromium, software WebGL): `figures/m2_*.png`.

## Algorithms, with the worked example

**1. From G_R to what is drawn** (`core/displayGraph.ts`). Take f = 1 5 3 4 2 9 6 8 0 at
R = [1.5, ∞]. Eqs. 1–3 keep A, C, D, s2, s3 and arcs s1–A, s1–B, s2–B, s2–C, s3–C, s3–D.
Redirect every arc endpoint to its representative at p_lo (B → A):

| saddle | ends after redirect | result |
|---|---|---|
| s1 | A, A | collapsed: dropped |
| s2 | A, C | connector A – s2 – C |
| s3 | C, D | connector C – s3 – D |

So the spine draws A – s2 – C – s3 – D: the ridge from A now meets C at s2, exactly as the
walkthrough's "A ⋯ s2" row said. With "One saddle per pair", if two saddles join the same
two extrema only the higher one stays (it is where the features actually meet).

**2. Layout** (`core/layout/pca.ts`, `stress.ts`). Start from PCA of all critical points
(computed once, so every threshold shares a frame; 2-D data is only centred). Then stress
majorization: each sweep moves node i to
x_i ← Σ_j w_ij (x_j + d_ij (x_i − x_j)/‖x_i − x_j‖) / Σ_j w_ij,
with d_ij the Euclidean distance between the critical points in the domain. For a 3-4-5
triangle this converges to exactly that triangle (tested), and stress never increases
(tested sweep by sweep). Warm start: nodes that stay visible start where they were.

**3. Link geometry** (`core/spine/links.ts`). For link A → s1 on the line (g(A) = 5,
g(s1) = 3, positions x = 1 and x = 2) and isovalue c:
- c = 3 = g(s1): radius at A counts A's samples with 3 < f < 5; at s1 the interval is empty,
  radius 0: the figure-eight pinch.
- c = 4: the shape stops where g(p) = 4, halfway (x = 1.5), radius 0 there: a closed blob.
- c ≥ 5: no shape.
Each covered part is cut into 8 pieces; consecutive circles are joined by tapered capsules.

**4. Rendering** (`render/SpineSdfRenderer.ts`). Per level, lowest first:
(a) draw every capsule piece as an instanced quad that writes `0.5 + d / (2·band)` with MIN
blending into an 8-bit target → each pixel holds the distance to the union of the level's
shapes; (b) a full-screen triangle fills d < 0 and strokes |d| < w/2, anti-aliased, over the
screen. Outlines therefore follow the union only, never the overlaps between pieces.
`core/spine/sdf.ts` is the same distance function in TypeScript, unit-tested; the shader
mirrors it line by line.

## Files

| File | Responsibility | Layer |
|---|---|---|
| `core/types.ts` | SpineData typed arrays; height g = sign·f | core |
| `core/parse.ts` | graph.json + buffers → SpineData, all checks | core |
| `core/thresholds.ts` | Eqs. 1–3, representatives, curves, starting threshold | core |
| `core/regionStats.ts` | merged histograms, r_us lookups | core |
| `core/displayGraph.ts` | G_R → drawn connectors | core |
| `core/layout/pca.ts`, `stress.ts` | initial frame, distance-preserving layout | core |
| `core/spine/levels.ts`, `links.ts`, `sdf.ts` | isovalues, capsule pieces, SDF reference | core |
| `core/colormap.ts` | viridis | core |
| `core/store.ts`, `spineState.ts`, `derive.ts` | state, defaults, memoised pipeline | core |
| `data/DatasetLoader.ts` | fetch index + files | platform |
| `render/SpineSdfRenderer.ts`, `Overlay.ts`, `shaders/*` | GPU passes, markers, lines | render |
| `view/SpineView.ts` | renderer, camera, pan/zoom, resize, theme, render on demand | view |
| `ui/PersistencePlot.ts`, `Panel.ts` | the two-curve plot, lil-gui | ui |
| `app/App.ts`, `main.ts` | wiring, HMR cleanup | app |
| `scripts/sync-data.mjs` | pipeline/out → public/data + index.json | tooling |

Tests: 7 files, 51 tests (`npm test`), all on pure core modules, using fixtures exported by
`pipeline/scripts/make_web_fixtures.py`, so the TypeScript is checked against real Python
output (the worked example, a noisy ring, Ackley minima from points).

## Milestone review (M2)

**Demo checklist**
1. `npm test` passes; `npm run build` succeeds.
2. gauss2d: two blobs joined at one saddle, nested contours (Fig. 7 look).
3. ring2d: opens at noise ≈ 0.14 with exactly the 8 hills in a ring (Fig. 5b's cycle);
   five extra connections cross the middle. Drag the red line left of the jump near 1.1:
   they disappear. That is the variation threshold doing what Sec. 3.4 describes.
4. ackley2d: 3 × 3 minima, the global minimum linked to all 8 neighbours (Fig. 13a, 2D).
5. gauss3d: 4 maxima, all pairwise adjacent (6 saddles): links cross in 2-D. This is the
   crossing problem the proposal's feature 5 (M4) addresses.

**Performance.** All four datasets lay out in < 10 ms. The full noisy ring at p_lo ≈ 0.01
(1282 drawn nodes) took ~9 s in the O(n²) layout, which is why the app now starts at the
suggested threshold and falls back to PCA above 600 nodes.

**Not yet verified on real hardware.** Screenshots come from headless Chromium with
SwiftShader. Please run `npm run dev` on your machine and check the frame rate while
dragging the sliders and zooming, especially on the integrated GPU.

**Re-plan.** M3 (data view + linking) is next and needs: picking on the spine (CPU
point-in-capsule using `sdf.ts`), the label lookup texture, the volume and scatter views.
M4 gains two concrete targets from this milestone: crossing reduction (gauss3d) and moving
the layout to a Web Worker for graphs above a few hundred nodes.

# Paper → code map

Paper: C. Correa, P. Lindstrom, P.-T. Bremer, *Topological Spines: A Structure-Preserving
Visual Representation of Scalar Fields*, IEEE TVCG 17(12), 2011.

| Paper concept | Where | Code | Test |
|---|---|---|---|
| Directed gradient flow graph G = (N, E), arcs saddle → extremum | Sec. 3.4 | `core/graph.py` · `GradientFlowGraph` | `test_graph.py` |
| Descending manifolds D(u) by steepest ascent (approx. MS complex) | Sec. 3.4 | `core/gradient_flow.py` · `steepest_ascent`, `decompose` (labels) | `test_line_example_ascent_and_labels`, `test_two_gaussians_on_grid` |
| (n−1)-saddle = highest shared point of two neighbouring manifolds | Sec. 3.4 | `core/gradient_flow.py` · `decompose` (boundary scan) | `test_saddle_takes_highest_boundary_edge` |
| Neighbourhoods in arbitrary dimension (grid / kNN) | Sec. 3.4 | `core/neighborhoods.py` | `test_neighborhoods.py` |
| Algorithm 1: persistence P, lazy priority queue | Alg. 1 | `core/persistence.py` · `compute_persistence` | `test_line_example_matches_hand_computation`, `test_matches_elder_rule_on_random_1d_signals` |
| PATH(G, s, u), REVERSE(G, P) | Alg. 1 | `_ReversibleFlow.path`, `_ReversibleFlow.cancel` | (via Algorithm 1 tests) |
| Saturated persistence P* | Sec. 3.4, Alg. 1 | `compute_persistence` (P* update) | `test_saturated_never_below_persistence`, cycle test |
| Cycles (û = v̂: saddle removed, nothing cancelled) | Sec. 3.3, Fig. 5b | `compute_persistence` | `test_cycle_saddle_gets_persistence_but_cancels_nothing` |
| G_R for R = [p_lo, p_hi] | Eqs. 1–3 | `core/extremum_graph.py` · `filter_graph` | `test_extremum_graph.py` |
| Persistence plot (blue) / variation plot (red) | Sec. 4.5, Fig. 8b | `extrema_curve`, `arc_curve` | `test_curves` |
| Link radius r_us(c, p) = volume between isovalues in D(u) | Sec. 4.2 | `core/region_stats.py` · `count_between` | `test_count_between_exact_on_bin_edges` |
| Volume preservation under simplification (merged regions) | Sec. 4.3 | `RegionHistograms.merged` + `representatives` | `test_merge_follows_representatives` |
| Minimum graph | Sec. 3.3 | pipeline negates f (`run.py`), export keeps original values | `test_minima_export_keeps_original_values` |
| Cycle of hills (Fig. 5) | Fig. 5b | `configs/ring2d.yaml`, `io/synthetic.ring_grid` | `test_ring_has_a_cycle` |
| Ackley's function, 3^d minima | Fig. 13a | `configs/ackley2d.yaml`, `ackley4d.yaml` | `test_ackley_minima_count_2d` |
| Persistence/variation plots | Fig. 8b | `viz/preview2d.py` (right panel) | `test_preview_renders` |
| Eqs. 1–3 in the browser | Eqs. 1–3 | `web/src/core/thresholds.ts` · `filterGraph` | `thresholds.test.ts` (same table as Python) |
| Link radius r_us(c, p) on merged regions | Sec. 4.2 | `web/src/core/regionStats.ts`, `spine/links.ts` · `shapeRadius` | `spine.test.ts` |
| Canonical topological link (Minkowski sum of circles) | Sec. 4.1, Fig. 7 | `spine/links.ts` · `buildSpineGeometry`; GPU: `render/shaders/capsule.frag.glsl` | figure-eight and truncation tests |
| Contour nesting guarantee | Sec. 4.3 | `shapeRadius` (interval grows as c falls) | nesting property test |
| Isovalue selection with minimum gap | Sec. 4.4 | `spine/levels.ts` | `chooseLevels` tests |
| Force-directed layout, rest length = Euclidean distance | Sec. 4.4 | `layout/stress.ts` (stress majorization), `layout/pca.ts` | `layout.test.ts` |
| Colour by scalar value | Sec. 4.4 | `colormap.ts`, `App.levelStyles` | — |
| Interactive persistence/variation plot | Sec. 4.5, Fig. 8b | `ui/PersistencePlot.ts` | — (manual) |

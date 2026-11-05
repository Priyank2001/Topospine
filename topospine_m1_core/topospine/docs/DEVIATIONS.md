# Deviations and unspecified details

Each entry: what the paper says (or doesn't), what we do, and why.

1. **Eqs. 1–3 reconstructed.** The inequality/interval symbols were lost in the PDF text
   we work from. We use: maximum kept iff `p_lo <= P(u)`; saddle kept iff
   `p_lo <= P(s) <= p_hi`; arc kept iff `P(s) <= p_hi and P*(s) >= p_lo`. This reproduces
   the volcano behaviour of Fig. 5 and the two-curve plots of Fig. 8b. Thresholds are
   inclusive. *To verify against the typeset paper before M2.*
2. **Saddle placement.** Sec. 3.4 says the saddle is the highest shared point of two
   neighbouring manifolds. On discrete samples we take the highest boundary edge
   (by `min(f(i), f(j))`) and place the saddle at its lower endpoint, so
   `f(saddle) = min(f(i), f(j))`. One sample can be the saddle of several region pairs
   (a degenerate multi-saddle); each pair gets its own saddle node.
   The result depends on which edges exist. With the default full stencil (8 / 26) both
   diagonals of a grid cell are edges, so two regions can touch across a diagonal *above*
   the true saddle: saddles come out too high and persistence too low (foot slice: 481
   maxima above 5 % of the range vs 579 in TTK's persistence diagram). On TTK's mesh
   (`connectivity: ttk`, D-016) the rule matches TTK closely (581 vs 579). The default stays
   the full stencil so earlier outputs reproduce (D-005).
3. **Ties.** The paper assumes a Morse function (distinct values). We order samples by
   `(f, index)` ("simulation of simplicity") everywhere, including which maximum Algorithm 1
   cancels. For maxima, "cancel û iff |f(û)−f(s)| < |f(v̂)−f(s)|" is the same as "cancel the
   lower one", so this only changes behaviour on exact ties.
4. **Algorithm 1 implementation details (equivalent results).**
   - The queue is seeded with each saddle's initial persistence instead of 0 (both are valid
     lower bounds; this skips one full round of re-insertions).
   - The lazy re-insert check uses a union-find over maxima to find path terminals; the full
     PATH traversal runs only when a saddle is finalised (an assertion checks they agree).
   - P* uses a running maximum. Finalised persistences are non-decreasing, so this equals
     the paper's plain assignment.
5. **Link radius from histograms.** r_us(c, p) is computed from per-region histograms
   (default 64 shared bins), exact at bin edges and linearly interpolated inside a bin.
   Counts are sample counts; physical volume = count × voxel volume.
6. **kNN neighbourhoods** are symmetrised and Euclidean. Features with different units must
   be normalised before building the graph (reader/source responsibility, M1 file 7–8).
7. **Maxima only in the core.** The minimum graph is computed by running the pipeline on −f.
8. **Saturated persistence on noisy data (`saturatedCancel`).** Algorithm 1 raises P* of every
   saddle on the paths of every finalised saddle, including cycle saddles (û = v̂). On noisy
   2-D data the background is full of such loops (each encloses a noise minimum); they have
   high persistence (~ peak height), so they raise P* of thousands of low-persistence noise
   saddles. Eq. 3 then keeps those saddles' arcs for any p_hi, because P(s) is small. Measured
   on `configs/ring2d.yaml` at R = [0.05, 0.9]: 2778 arcs with the paper's P*, 36 with the
   variant. We therefore export both: `saturated` (paper, default) and `saturatedCancel`
   (raised only by saddles that cancel a maximum, plus each saddle itself). The ring's cycle
   is still recovered with the variant. The browser gets a toggle; comparing the two is an
   ablation for the report. Note the variant can hide loop-supporting arcs once p_lo exceeds
   the persistence of every maximum on the loop.
9. **TTK adapter uses TTK's regions, not its separatrices.** TTK's separatrix arrays and port
   layout differ between releases; the per-vertex manifold ids are stable. We take TTK's
   maximum regions and derive saddles with our own boundary rule (#2). The array holding the
   maximum regions is detected automatically (regions with exactly one of TTK's own maxima,
   DECISIONS.md D-012), so a naming-convention mix-up can't silently produce a minimum graph.
   This is the `ttk` preset. Since M3, TTK's own saddles are available too (`ttk+ttk`, #17).
10. **Axis conventions.** Grid arrays are (z, y, x) with x fastest (VTK and WebGL 3D-texture
    order); configs and exported metadata use (x, y, z). Point positions are exported in the
    normalised space the kNN graph was built in, with `offset`/`scale` to undo it.

## M2 (spine in the browser)

11. **Size encoding.** The paper sets the link radius proportional to the enclosed volume.
    Default here: radius ∝ √volume, so a circle's *area* is proportional to volume and a
    region 100× smaller is still visible. The paper's version is one click away
    ("Radius ∝ volume (paper)").
12. **Which connections are drawn ("collapsed" mode).** Visible arcs are redirected to the
    surviving extremum their endpoint merged into; a saddle whose two arcs then reach the same
    extremum is dropped; by default only the highest saddle per pair of extrema is kept
    ("One saddle per pair"). The paper instead keeps simplified saddles' arcs to trace ridges
    through cancelled extrema (volcano, Fig. 5). That "ridge" mode needs cancelled extrema as
    pass-through nodes and is deferred (M4).
13. **Layout.** Stress majorization instead of a mass-spring simulation: same energy
    (springs with rest length = Euclidean distance between critical points), but monotone,
    deterministic and step-size free. All pairs weighted d⁻², links ×8. 2-D data is only
    centred (no PCA rotation). Above 600 drawn nodes the PCA layout is kept (O(n²) cost).
14. **Isovalues.** All critical values below the highest drawn extremum, plus 6 evenly
    spaced extra levels (the paper's optional pseudo-contours, Sec. 4.1), min. gap 3 % of the
    height range, at most 24 levels.
15. **Contour shape.** The Minkowski sum of circles along a link is approximated by 8 tapered
    capsules. Where the region holds much volume just above the saddle, circles near the saddle
    already cover it, so the critical contour shows a notch rather than a sharp figure-eight
    pinch; a smaller glyph size or the linear encoding makes the pinch visible.
16. **Starting noise threshold.** Not in the paper (which reads plateaus off the plot by eye):
    the app opens at the geometric middle of the widest ratio gap between consecutive extremum
    persistences, or 1 % of the maximum if no gap ≥ 3× exists.

## M3 (composable extraction)

17. **TTK saddles (M3, `ttk` saddle method).** Only saddles with exactly two uphill
    separatrices become graph saddles; saddles where a path runs into the domain border are
    dropped (DECISIONS.md D-009). If that leaves the peaks in separate pieces, our boundary
    saddles (#2) are added, highest first, only where they join two pieces (D-011), so the
    graph has one global maximum. Saddles joining 3+ peaks stop the run (D-010).
18. **Simplified field (optional, `simplify:` / `--simplify`).** Not in the paper, which reads
    noise off the persistence plot instead. Before extraction, TTK's persistence simplification
    flattens every maximum below the threshold (fraction of the value range) into its saddle;
    all methods then see, and the export contains, this simplified field, not the raw data
    (DECISIONS.md D-014, D-015). `graph.json` records it under `dataset.simplify`. The cut is
    exact only with `connectivity: ttk`; on another stencil some features below the threshold
    remain, and maxima on the domain border can remain with the TTK region method.

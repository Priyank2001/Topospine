import numpy as np
import pytest

from topospine.core import compute_persistence
from topospine.io.synthetic import bumps_grid
from topospine.sources.base import ExtractionContext
from topospine.sources.composed_source import ComposedSource
from topospine.sources.native_blocks import AscentRegions
from topospine.sources.native_source import NativeSource
from topospine.sources.ttk_backend import MorseSmaleOutput, PortArrays, TtkBackend, run_morse_smale
from topospine.sources.ttk_blocks import SaddleReport, TtkRegions, TtkSaddles
from topospine.sources.ttk_output import TtkArrayNames, ttk_maxima, ttk_saddles

# 12 samples in 3 regions; peaks at samples 1, 5, 10.
LABELS = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2])
PEAKS = {0: 1, 1: 5, 2: 10}                       # max CellId -> sample


def fake_msc(d, saddles, seps, segmentation=None):
    """saddles: {CellId: sample}. seps: [(SeparatrixType, saddle CellId, dest CellId, polyline cells)].

    Saddle and maximum CellIds deliberately overlap (0, 1, 2 ...), as in TTK, where ids
    are numbered per dimension.
    """
    rows = [(0, 0, 0)] + [(d - 1, c, v) for c, v in saddles.items()] + [(d, c, v) for c, v in PEAKS.items()]
    dim, cid, vert = (np.array(col, dtype=np.int64) for col in zip(*rows))
    src, dst, sid, typ = [], [], [], []
    for i, (t, s, m, cells) in enumerate(seps):
        src += [s] * cells; dst += [m] * cells; sid += [i] * cells; typ += [t] * cells
    cp = PortArrays({"CellDimension": dim, "CellId": cid, "ttkVertexScalarField": vert}, {})
    sep = PortArrays({}, {"SourceId": np.array(src), "DestinationId": np.array(dst),
                          "SeparatrixId": np.array(sid), "SeparatrixType": np.array(typ)})
    seg = PortArrays(segmentation or {}, {})
    return MorseSmaleOutput((cp, sep, PortArrays({}, {}), seg))


def mixed_case(d):
    up, down = d - 1, 0
    saddles = {0: 3, 1: 7, 2: 6, 3: 11, 4: 4}
    seps = [(up, 0, 0, 3), (up, 0, 1, 1),        # normal pass between peaks 0 and 1 (3 polyline cells)
            (up, 1, 1, 1), (up, 1, 2, 2),        # pass 1-2
            (up, 2, 1, 1), (up, 2, 1, 1),        # both paths reach peak 1: a loop
            (up, 3, 2, 1),                       # one-sided: other path ran off the border
            (down, 0, 0, 2)]                     # saddle -> minimum: ignored
    return saddles, seps                         # saddle 4 has no uphill separatrix at all


@pytest.mark.parametrize("d", [2, 3])
def test_reads_passes_loops_and_drops_one_sided(d):
    s, dropped = ttk_saddles(fake_msc(d, *mixed_case(d)), LABELS)
    assert s.samples.tolist() == [3, 6, 7]
    assert s.pairs.tolist() == [[0, 1], [1, 1], [1, 2]]
    assert dropped == 2


def test_degenerate_saddle_is_an_error():
    saddles, seps = mixed_case(2)
    with pytest.raises(ValueError, match=r"degenerate saddle \(cell 0, sample 3\) has 3"):
        ttk_saddles(fake_msc(2, saddles, seps + [(1, 0, 2, 1)]), LABELS)


def test_two_saddle_cells_at_one_sample_stay_two_saddles():
    # Real TTK: ttkVertexScalarField is a cell's highest vertex, which cells can share.
    saddles, seps = mixed_case(2)
    out = fake_msc(2, {**saddles, 5: 3}, seps + [(1, 5, 1, 1), (1, 5, 2, 1)])
    s, dropped = ttk_saddles(out, LABELS)
    assert s.samples.tolist() == [3, 3, 6, 7]
    assert sorted(map(tuple, s.pairs[:2].tolist())) == [(0, 1), (1, 2)]
    assert dropped == 2


def test_unknown_cell_id_is_an_error():
    with pytest.raises(RuntimeError, match="maximum cell 9"):
        ttk_saddles(fake_msc(2, {0: 3}, [(1, 0, 0, 1), (1, 0, 9, 1)]), LABELS)


def test_missing_arrays_name_what_to_override():
    with pytest.raises(RuntimeError, match="SeparatrixType"):
        ttk_saddles(MorseSmaleOutput(fake_msc(2, *mixed_case(2)).ports[:1]), LABELS)


def test_array_names_can_be_overridden():
    out = fake_msc(2, *mixed_case(2))
    sep = out.ports[1].cell
    renamed = dict(sep, Kind=sep["SeparatrixType"])
    del renamed["SeparatrixType"]
    out = MorseSmaleOutput((out.ports[0], PortArrays({}, renamed)))
    s, _ = ttk_saddles(out, LABELS, TtkArrayNames(separatrix_type="Kind"))
    assert s.samples.tolist() == [3, 6, 7]


def test_ttk_saddles_need_ttk_regions():
    with pytest.raises(ValueError, match="D-007"):
        ComposedSource(AscentRegions(), TtkSaddles())


def _msc_from(dec, drop_saddles=()):
    """A fake TTK output that encodes a known decomposition exactly.

    drop_saddles: graph saddle nodes whose separatrices TTK "lost" (as when a path runs
    off the border), leaving the regions in pieces.
    """
    g = dec.graph
    max_cell = {int(node): i for i, node in enumerate(g.maxima)}
    cp_rows = [(1, i, int(g.samples[s])) for i, s in enumerate(g.saddles)] + \
              [(2, max_cell[int(m)], int(g.samples[m])) for m in g.maxima]
    dim, cid, vert = (np.array(c) for c in zip(*cp_rows))
    saddle_cell = {int(s): i for i, s in enumerate(g.saddles)}
    arcs = [(int(s), int(m)) for s, m in g.arcs if int(s) not in drop_saddles]
    src = np.array([saddle_cell[s] for s, _ in arcs])
    dst = np.array([max_cell[m] for _, m in arcs])
    return MorseSmaleOutput((
        PortArrays({"CellDimension": dim, "CellId": cid, "ttkVertexScalarField": vert}, {}),
        PortArrays({}, {"SourceId": src, "DestinationId": dst, "SeparatrixId": np.arange(src.size),
                        "SeparatrixType": np.ones(src.size, dtype=np.int64)}),
        PortArrays({"DescendingManifold": dec.labels * 4 + 9}, {}),
    ))


def test_ttk_plus_ttk_reproduces_a_known_graph_with_one_ttk_run():
    g = bumps_grid((40, 30), **THREE_BUMPS)
    native = NativeSource().compute(g)
    calls = []
    backend = TtkBackend(lambda ds: calls.append(ds) or _msc_from(native))
    regions, saddles = TtkRegions(backend), TtkSaddles(backend)
    dec = ComposedSource(regions, saddles).compute(g)
    assert len(calls) == 1                                          # both blocks share one TTK run
    assert dec.labels.tolist() == native.labels.tolist()
    for field in ("kinds", "samples", "values"):
        assert getattr(dec.graph, field).tolist() == getattr(native.graph, field).tolist(), field
    assert sorted(map(tuple, dec.graph.arcs.tolist())) == sorted(map(tuple, native.graph.arcs.tolist()))
    assert saddles.last_report == SaddleReport(kept=native.graph.saddles.size, dropped=0, added=0)
    assert regions.last_choice[0] == "DescendingManifold"


THREE_BUMPS = dict(centers=[[0.2, 0.3], [0.7, 0.7], [0.5, 0.2]], heights=[1.0, 0.9, 0.7], width=0.1)


def test_lost_separatrices_are_bridged_by_the_highest_boundary_saddle():
    g = bumps_grid((40, 30), **THREE_BUMPS)
    native = NativeSource().compute(g)
    gr = native.graph
    low_peak = int(gr.maxima[np.argmin(gr.values[gr.maxima])])
    lost = {int(s) for s, m in gr.arcs if m == low_peak}            # every pass of the lowest peak
    backend = TtkBackend(lambda ds: _msc_from(native, drop_saddles=lost))
    saddles = TtkSaddles(backend)
    dec = ComposedSource(TtkRegions(backend), saddles).compute(g)
    p = compute_persistence(dec.graph).persistence[dec.graph.maxima]
    assert np.isinf(p).sum() == 1                                  # one piece again: one global maximum
    assert saddles.last_report == SaddleReport(kept=gr.saddles.size - len(lost), dropped=len(lost), added=1)
    highest_lost = max(lost, key=lambda s: gr.values[s])
    assert gr.samples[highest_lost] in dec.graph.samples           # bridged at its highest pass


def test_connected_ttk_saddles_get_no_boundary_saddles():
    native = NativeSource().compute(bumps_grid((40, 30), **THREE_BUMPS))
    s = TtkSaddles(TtkBackend(lambda ds: _msc_from(native)))
    ComposedSource(TtkRegions(s.backend), s).compute(bumps_grid((40, 30), **THREE_BUMPS))
    assert s.last_report.added == 0


def test_reports_say_what_ttk_did():
    g = bumps_grid((40, 30), **THREE_BUMPS)
    native = NativeSource().compute(g)
    backend = TtkBackend(lambda ds: _msc_from(native))
    src = ComposedSource(TtkRegions(backend), TtkSaddles(backend), connectivity=8)
    assert src.report()["regions"] == {"method": "ttk"}              # nothing to say before a run
    src.compute(g)
    assert src.report() == {
        "regions": {"method": "ttk", "array": "DescendingManifold", "score": 1.0},
        "saddles": {"method": "ttk", "kept": native.graph.saddles.size, "dropped": 0, "added": 0},
        "connectivity": 8, "k": 15}


def test_ttk_maxima_are_the_top_dimension_cells():
    for d in (2, 3):
        assert sorted(ttk_maxima(fake_msc(d, *mixed_case(d))).tolist()) == sorted(PEAKS.values())


def test_regions_are_scored_by_ttk_maxima_not_our_stencil():
    # TTK says the peaks are samples 1, 5, 10. "Wrong" puts two of them in one region.
    wrong = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
    out = fake_msc(2, *mixed_case(2), segmentation={"AscendingManifold": LABELS * 7, "DescendingManifold": wrong})
    regions = TtkRegions(TtkBackend(lambda ds: out))
    labels = regions.labels(ExtractionContext(bumps_grid((3, 4)), None, None))
    assert labels.tolist() == LABELS.tolist()
    assert regions.last_choice == ("AscendingManifold", {"DescendingManifold": 0.5, "AscendingManifold": 1.0})


@pytest.mark.slow
def test_real_ttk_plus_ttk_on_clean_bumps3d():
    pytest.importorskip("topologytoolkit")
    g = bumps_grid((24, 20, 16), centers=[[0.3, 0.3, 0.5], [0.7, 0.6, 0.5]], heights=[1.0, 0.8], width=0.15)
    calls = []
    backend = TtkBackend(lambda ds: calls.append(ds) or run_morse_smale(ds))
    saddles = TtkSaddles(backend)
    dec = ComposedSource(TtkRegions(backend), saddles).compute(g)
    nat = NativeSource().compute(g)
    assert len(calls) == 1
    assert saddles.last_report == SaddleReport(kept=1, dropped=8, added=0)    # 8 border saddles (D-009)
    p_ttk = np.sort(compute_persistence(dec.graph).persistence[dec.graph.maxima])
    p_nat = np.sort(compute_persistence(nat.graph).persistence[nat.graph.maxima])
    assert p_ttk.size == p_nat.size and np.allclose(p_ttk, p_nat, rtol=0.05)

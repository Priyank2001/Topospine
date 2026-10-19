import numpy as np
import pytest

from tests.conftest import A, B, C, D, LINE_VALUES, S1, S2, S3
from topospine.core import (
    GridNeighborhood,
    KnnNeighborhood,
    NodeKind,
    compute_persistence,
    decompose,
    sample_ranks,
    steepest_ascent,
)


def test_ranks_break_ties_by_index():
    assert sample_ranks(np.array([2.0, 1.0, 2.0, 0.0])).tolist() == [2, 1, 3, 0]


def test_ranks_reject_nan():
    with pytest.raises(ValueError):
        sample_ranks(np.array([1.0, np.nan]))


def test_line_example_ascent_and_labels(line_example):
    dec, _ = line_example
    ascent = steepest_ascent(sample_ranks(LINE_VALUES), GridNeighborhood((9,), 2))
    assert ascent.tolist() == [1, 1, 1, 3, 5, 5, 5, 7, 7]           # table row "points to"
    assert dec.labels.tolist() == [A, A, A, B, C, C, C, D, D]        # table row "label"


def test_line_example_graph(line_example):
    g = line_example[0].graph
    assert g.kinds.tolist() == [NodeKind.MAXIMUM] * 4 + [NodeKind.SADDLE] * 3
    assert g.samples.tolist() == [1, 3, 5, 7, 2, 4, 6]               # saddle = lower endpoint of top boundary edge
    assert g.values.tolist() == [5, 4, 9, 8, 3, 2, 6]
    arcs = {(int(s), int(m)) for s, m in g.arcs}
    assert arcs == {(S1, A), (S1, B), (S2, B), (S2, C), (S3, C), (S3, D)}


def test_plateau_resolved_by_index():
    dec = decompose(np.array([0.0, 1.0, 1.0, 0.0]), GridNeighborhood((4,), 2))
    assert dec.graph.samples[dec.graph.maxima].tolist() == [2]       # one max, not two (tie-break works)
    assert dec.graph.saddles.size == 0


def test_single_sample_and_monotone_field():
    assert decompose(np.array([3.0]), GridNeighborhood((1,), 2)).graph.num_nodes == 1
    dec = decompose(np.arange(10.0), GridNeighborhood((10,), 2))
    assert dec.graph.maxima.size == 1 and (dec.labels == 0).all()


def test_saddle_takes_highest_boundary_edge():
    # Two regions touch along two edges in 2-D; the saddle must be on the higher one.
    f = np.array([[9.0, 1.0, 8.0],
                  [0.0, 0.0, 0.0],
                  [7.0, 5.0, 6.0]])
    dec = decompose(f, GridNeighborhood(f.shape, 4))
    g = dec.graph
    assert g.saddles.size >= 1
    assert g.values[g.saddles].max() == 5.0                          # catches keeping the first/lowest edge


def gaussians_2d(shape=(41, 61)):
    y, x = np.mgrid[0:shape[0], 0:shape[1]].astype(float)
    big = np.exp(-((x - 20) ** 2 + (y - 20) ** 2) / 60.0)
    small = 0.6 * np.exp(-((x - 42) ** 2 + (y - 20) ** 2) / 60.0)
    return big + small


@pytest.mark.parametrize("conn", [4, 8])
def test_two_gaussians_on_grid(conn):
    f = gaussians_2d()
    dec = decompose(f, GridNeighborhood(f.shape, conn))
    g = dec.graph
    assert g.maxima.size == 2 and g.saddles.size == 1
    peak_cols = sorted(int(s) % f.shape[1] for s in g.samples[g.maxima])
    assert peak_cols == [20, 42]
    saddle_col = int(g.samples[g.saddles[0]]) % f.shape[1]
    assert 20 < saddle_col < 42                                      # saddle lies between the peaks
    pers = compute_persistence(g)
    small = g.maxima[np.argmin(g.values[g.maxima])]
    assert pers.persistence[small] == pytest.approx(g.values[small] - g.values[g.saddles[0]])


def scattered_gaussians(seed=7, n=3000):
    rng = np.random.default_rng(seed)
    pts = rng.uniform([0, 0], [40, 60], size=(n, 2))
    f = np.exp(-((pts[:, 1] - 20) ** 2 + (pts[:, 0] - 20) ** 2) / 60.0) + 0.6 * np.exp(
        -((pts[:, 1] - 42) ** 2 + (pts[:, 0] - 20) ** 2) / 60.0
    )
    return pts, f


def test_two_gaussians_from_scattered_points():
    pts, f = scattered_gaussians()
    dec = decompose(f, KnnNeighborhood(pts, k=10))
    pers = compute_persistence(dec.graph)
    P = pers.persistence[dec.graph.maxima]
    assert dec.graph.maxima.size > 2                                 # random sampling creates spurious slope maxima...
    assert (P >= 0.1).sum() == 2                                     # ...which p_lo removes: both real peaks survive
    assert sorted(P[P >= 0.1])[0] > 0.3                              # the small peak is far above the noise


def test_larger_k_gives_fewer_spurious_maxima():
    pts, f = scattered_gaussians()
    counts = [decompose(f, KnnNeighborhood(pts, k=k)).graph.maxima.size for k in (6, 10, 20)]
    assert counts[0] > counts[1] > counts[2] >= 2                    # k trades noise for smoothing

import numpy as np
import pytest

from tests.conftest import A, B, C, D, S1, S2, S3
from topospine.core import arc_curve, extrema_curve, filter_graph, representatives

INF = np.inf


def kept(mask):
    return {int(i) for i in np.flatnonzero(mask)}


def kept_arcs(graph, tg):
    return {(int(s), int(m)) for (s, m), k in zip(graph.arcs, tg.arc_mask) if k}


def test_full_range_keeps_everything(line_example):
    dec, pers = line_example
    tg = filter_graph(dec.graph, pers, 0.0, INF)
    assert tg.node_mask.all() and tg.arc_mask.all()


def test_noise_threshold_keeps_ridge_arcs_of_simplified_saddle(line_example):
    dec, pers = line_example
    tg = filter_graph(dec.graph, pers, 1.5, INF)
    assert kept(tg.node_mask) == {A, C, D, S2, S3}                    # B and s1 gone
    assert (S1, A) in kept_arcs(dec.graph, tg)                         # P*(s1)=3 keeps the ridge drawn
    assert (S1, B) in kept_arcs(dec.graph, tg)


def test_higher_noise_threshold(line_example):
    dec, pers = line_example
    tg = filter_graph(dec.graph, pers, 2.5, INF)
    assert kept(tg.node_mask) == {A, C, S2}
    assert kept_arcs(dec.graph, tg) == {(S1, A), (S1, B), (S2, B), (S2, C)}   # s3's arcs gone (P*=2)


def test_variation_threshold_splits_features(line_example):
    dec, pers = line_example
    tg = filter_graph(dec.graph, pers, 0.0, 2.5)
    assert kept(tg.node_mask) == {A, B, C, D, S1, S3}                  # s2 (P=3) exceeds p_hi
    assert kept_arcs(dec.graph, tg) == {(S1, A), (S1, B), (S3, C), (S3, D)}


@pytest.mark.parametrize(
    "p_lo,expected_regions",
    [
        (0.0, [A, A, A, B, C, C, C, D, D]),
        (1.5, [A, A, A, A, C, C, C, D, D]),     # B merged into A
        (2.5, [A, A, A, A, C, C, C, C, C]),     # D merged into C
        (3.5, [C] * 9),                         # chain B -> A -> C followed to the end
    ],
)
def test_representatives(line_example, p_lo, expected_regions):
    dec, pers = line_example
    assert representatives(pers, p_lo)[dec.labels].tolist() == expected_regions


def test_curves(line_example):
    dec, pers = line_example
    t = np.array([0.0, 1.0, 1.5, 2.5, 3.0, 3.5])
    assert extrema_curve(dec.graph, pers, t).tolist() == [4, 4, 3, 2, 2, 1]   # P >= t, boundary inclusive
    assert arc_curve(dec.graph, pers, t).tolist() == [0, 2, 2, 4, 6, 6]       # P(s) <= t


def test_invalid_range(line_example):
    dec, pers = line_example
    with pytest.raises(ValueError):
        filter_graph(dec.graph, pers, 2.0, 1.0)
    with pytest.raises(ValueError):
        filter_graph(dec.graph, pers, -1.0)

import numpy as np
import pytest

from tests.conftest import A, B, C, D, S1, S2, S3
from topospine.core import GradientFlowGraph, GridNeighborhood, NodeKind, compute_persistence, decompose

INF = np.inf


def test_line_example_matches_hand_computation(line_example):
    _, pers = line_example
    assert pers.persistence.tolist() == [3, 1, INF, 2, 1, 3, 2]       # P row of the walkthrough
    assert pers.saturated[[S1, S2, S3]].tolist() == [3, 3, 2]         # P*(s1)=3 is the key case
    assert np.isnan(pers.saturated[[A, B, C, D]]).all()
    assert pers.merged_into.tolist() == [C, A, -1, C, -1, -1, -1]


def test_saturated_never_below_persistence(line_example):
    _, pers = line_example
    s = [S1, S2, S3]
    assert (pers.saturated[s] >= pers.persistence[s]).all()


def test_cycle_saddle_gets_persistence_but_cancels_nothing():
    # Maxima a(10), b(9); saddles s1(5), s2(3) both join a and b: a ring.
    M, S = NodeKind.MAXIMUM, NodeKind.SADDLE
    g = GradientFlowGraph(
        kinds=np.array([M, M, S, S]),
        values=np.array([10.0, 9.0, 5.0, 3.0]),
        samples=np.arange(4),
        arcs=np.array([[2, 0], [2, 1], [3, 0], [3, 1]]),
    )
    pers = compute_persistence(g)
    assert pers.persistence.tolist() == [INF, 4, 4, 7]   # s2 reaches a both ways: p = 10 - 3
    assert pers.merged_into.tolist() == [-1, 0, -1, -1]  # only b was cancelled
    assert pers.saturated[[2, 3]].tolist() == [7, 7]     # s1 lies on s2's path through b


def test_no_saddles():
    g = GradientFlowGraph(kinds=np.array([0]), values=np.array([1.0]), samples=np.array([0]), arcs=np.empty((0, 2)))
    assert compute_persistence(g).persistence.tolist() == [INF]


def elder_rule_1d(f):
    """Brute-force 0-dim superlevel persistence on a line (union-find sweep)."""
    order = sorted(range(len(f)), key=lambda i: (f[i], i), reverse=True)
    parent, top, seen, died = {}, {}, set(), {}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in order:
        parent[i], top[i] = i, i
        for j in (i - 1, i + 1):
            if j in seen:
                ri, rj = find(i), find(j)
                if ri == rj:
                    continue
                lo, hi = sorted((ri, rj), key=lambda r: (f[top[r]], top[r]))
                if top[lo] != i:                      # a real max dies, not the new sample
                    died[top[lo]] = f[top[lo]] - f[i]
                parent[lo] = hi
        seen.add(i)
    return died


@pytest.mark.parametrize("seed", range(20))
def test_matches_elder_rule_on_random_1d_signals(seed):
    f = np.cumsum(np.random.default_rng(seed).normal(size=200))
    dec = decompose(f, GridNeighborhood((f.size,), 2))
    pers = compute_persistence(dec.graph)
    g = dec.graph
    ours = {int(g.samples[m]): pers.persistence[m] for m in g.maxima if np.isfinite(pers.persistence[m])}
    ref = elder_rule_1d(f.tolist())
    assert ours.keys() == ref.keys()
    for k in ref:
        assert ours[k] == pytest.approx(ref[k])       # Algorithm 1 == standard persistence in 1-D


def test_cancellation_only_saturation(line_example):
    _, pers = line_example
    # No cycles on a line, so both variants agree.
    assert pers.saturated_cancel[[S1, S2, S3]].tolist() == [3, 3, 2]


def test_cycle_does_not_raise_cancellation_only_saturation():
    M, S = NodeKind.MAXIMUM, NodeKind.SADDLE
    g = GradientFlowGraph(
        kinds=np.array([M, M, S, S]),
        values=np.array([10.0, 9.0, 5.0, 3.0]),
        samples=np.arange(4),
        arcs=np.array([[2, 0], [2, 1], [3, 0], [3, 1]]),
    )
    pers = compute_persistence(g)
    assert pers.saturated[[2, 3]].tolist() == [7, 7]          # paper: the cycle saddle s2 saturates s1
    assert pers.saturated_cancel[[2, 3]].tolist() == [4, 7]   # variant: only b's cancellation counts for s1

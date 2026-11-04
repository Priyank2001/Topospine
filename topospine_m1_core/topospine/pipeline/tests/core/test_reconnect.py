import numpy as np

from topospine.core import SaddleSet, connect_pieces, count_pieces, sample_ranks

#           sample: 0    1    2    3    4    5    6    7
VALUES = np.array([9.0, 1.0, 5.0, 2.0, 7.0, 3.0, 6.0, 4.0])
RANKS = sample_ranks(VALUES)


def _set(samples, pairs):
    return SaddleSet(np.array(samples, dtype=np.int64), np.array(pairs, dtype=np.int64).reshape(-1, 2))


def test_count_pieces():
    assert count_pieces(np.empty((0, 2), dtype=np.int64), 3) == 3
    assert count_pieces(np.array([[0, 1], [1, 1]]), 3) == 2          # a loop joins nothing
    assert count_pieces(np.array([[0, 1], [2, 1]]), 3) == 1


def test_adds_the_highest_candidate_between_pieces():
    kept = _set([1], [[0, 1]])                                        # pieces {0,1} and {2}
    candidates = _set([3, 6, 5, 2], [[1, 2], [0, 2], [0, 1], [0, 1]])
    out, added = connect_pieces(kept, candidates, RANKS, 3)
    assert added == 1
    assert out.samples.tolist() == [1, 6]                             # f=6 beats f=2; {0,1} pairs skipped
    assert out.pairs.tolist() == [[0, 1], [0, 2]]


def test_only_as_many_as_needed_highest_first():
    kept = _set([], [])                                               # 4 regions, all apart
    candidates = _set([2, 4, 6, 7], [[0, 1], [1, 2], [0, 2], [2, 3]])
    out, added = connect_pieces(kept, candidates, RANKS, 4)
    assert added == 3                                                 # a tree: 4 pieces need 3 joins
    assert out.samples.tolist() == [4, 6, 7]                          # f=5 (0-1) closes a cycle: skipped
    assert count_pieces(out.pairs, 4) == 1


def test_already_connected_is_left_alone():
    kept = _set([1, 3], [[0, 1], [1, 2]])
    out, added = connect_pieces(kept, _set([6], [[0, 2]]), RANKS, 3)
    assert out is kept and added == 0


def test_region_without_candidates_stays_apart():
    out, added = connect_pieces(_set([1], [[0, 1]]), _set([], []), RANKS, 3)
    assert added == 0 and count_pieces(out.pairs, 3) == 2

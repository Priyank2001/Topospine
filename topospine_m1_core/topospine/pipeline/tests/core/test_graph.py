import numpy as np
import pytest

from topospine.core.graph import GradientFlowGraph, NodeKind

M, S = NodeKind.MAXIMUM, NodeKind.SADDLE


def make(kinds=(M, M, S), values=(5.0, 4.0, 3.0), samples=(1, 3, 2), arcs=((2, 0), (2, 1))):
    return GradientFlowGraph(kinds=np.array(kinds), values=np.array(values), samples=np.array(samples), arcs=np.array(arcs))


def test_valid_graph_properties():
    g = make()
    assert g.num_nodes == 3 and g.num_arcs == 2
    assert g.maxima.tolist() == [0, 1] and g.saddles.tolist() == [2]
    assert sorted(g.saddle_arcs[2].tolist()) == [0, 1]   # catches wrong saddle->arc lookup
    assert (g.saddle_arcs[:2] == -1).all()                # maxima own no saddle arcs


def test_arrays_are_copied_and_read_only():
    values = np.array([5.0, 4.0, 3.0])
    g = make(values=values)
    values[0] = -1.0
    assert g.values[0] == 5.0                              # caller mutation can't leak in
    with pytest.raises(ValueError):
        g.values[0] = 0.0                                  # graph can't be mutated by Algorithm 1


def test_single_maximum_without_arcs_is_valid():
    g = GradientFlowGraph(kinds=np.array([M]), values=np.array([1.0]), samples=np.array([0]), arcs=np.empty((0, 2)))
    assert g.num_arcs == 0 and g.saddle_arcs.shape == (1, 2)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(arcs=((0, 1), (2, 1))),                 # arc starting at a maximum
        dict(arcs=((2, 0),)),                        # saddle with one arc
        dict(arcs=((2, 0), (2, 1), (2, 0))),         # saddle with three arcs
        dict(arcs=((2, 0), (2, 5))),                 # endpoint out of range
        dict(values=(5.0, 2.0, 3.0)),                # saddle above a maximum (uphill violated)
        dict(values=(5.0, np.nan, 3.0)),             # non-finite value
        dict(samples=(1, 3)),                        # length mismatch
        dict(kinds=(M, M, 7)),                       # unknown kind
    ],
)
def test_invalid_graphs_rejected(kwargs):
    with pytest.raises(ValueError):
        make(**kwargs)


def test_saddle_may_connect_same_maximum_twice():
    # Exact MS complexes (TTK) can produce loops; Algorithm 1 must receive them.
    g = make(kinds=(M, S), values=(5.0, 3.0), samples=(0, 1), arcs=((1, 0), (1, 0)))
    assert g.num_arcs == 2


def test_precedes_breaks_ties_by_sample():
    g = make(values=(4.0, 4.0, 3.0))
    assert g.precedes(0, 1)        # equal value, sample 1 < sample 3
    assert not g.precedes(1, 0)
    assert g.precedes(2, 0)        # lower value first

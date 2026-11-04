import numpy as np
import pytest

from topospine.core import sample_ranks, steepest_ascent
from topospine.core.neighborhoods import FreudenthalNeighborhood, GridNeighborhood, KnnNeighborhood


def adjacency(nb):
    """Materialise the undirected neighbour sets (tests only; small inputs)."""
    adj = [set() for _ in range(nb.num_samples)]
    for src, dst in nb.edge_blocks():
        for i, j in zip(src.tolist(), dst.tolist()):
            adj[i].add(j)
            adj[j].add(i)
    return adj


def num_edges(nb):
    return sum(len(a) for a in adjacency(nb)) // 2


@pytest.mark.parametrize(
    "shape,conn,expected",
    [
        ((9,), 2, 8),          # path graph
        ((3, 3), 4, 12),       # 2 * 3 * 2 axis edges
        ((3, 3), 8, 20),       # + 2 diagonals per 2x2 cell (4 cells)
        ((2, 2, 2), 6, 12),    # cube edges
        ((2, 2, 2), 18, 24),   # + 12 face diagonals, no body diagonals
        ((2, 2, 2), 26, 28),   # complete graph on 8 vertices
    ],
)
def test_grid_edge_counts(shape, conn, expected):
    assert num_edges(GridNeighborhood(shape, conn)) == expected   # catches wrong stencil / boundary slicing


def test_grid_each_edge_once_and_no_self_loops():
    nb = GridNeighborhood((4, 3, 2), 26)
    pairs = [tuple(sorted(p)) for s, d in nb.edge_blocks() for p in zip(s.tolist(), d.tolist())]
    assert len(pairs) == len(set(pairs))          # half-stencil really halves
    assert all(i != j for i, j in pairs)


def test_grid_uses_c_order():
    nb = GridNeighborhood((2, 3), 4)
    adj = adjacency(nb)
    assert adj[0] == {1, 3}                       # index = row * 3 + col


def test_grid_axis_of_length_one():
    assert num_edges(GridNeighborhood((1, 5), 8)) == 4   # degenerate axis: offsets along it vanish


@pytest.mark.parametrize("shape,conn", [((3, 3), 6), ((3, 3, 3), 8), ((5,), 4)])
def test_grid_rejects_invalid_connectivity(shape, conn):
    with pytest.raises(ValueError):
        GridNeighborhood(shape, conn)


# ------------------------------------------------------------ Freudenthal (TTK's mesh)

@pytest.mark.parametrize("shape,expected", [
    ((9,), 8),               # 1-D: same path graph
    ((3, 3), 16),            # 12 axis edges + ONE diagonal per 2x2 cell (4 cells)
    ((2, 2, 2), 19),         # 12 cube edges + 6 face diagonals + 1 body diagonal
])
def test_freudenthal_edge_counts(shape, expected):
    assert num_edges(FreudenthalNeighborhood(shape)) == expected


def test_freudenthal_neighbour_counts():
    assert (FreudenthalNeighborhood((5, 5)).connectivity, FreudenthalNeighborhood((5, 5, 5)).connectivity) == (6, 14)
    adj = adjacency(FreudenthalNeighborhood((5, 5, 5)))
    assert len(adj[2 * 25 + 2 * 5 + 2]) == 14                       # an interior sample


def test_freudenthal_diagonal_runs_down_x():
    # 3x3 grid, index = row * 3 + col. The centre (4) links to (row+1, col-1) = 6 and
    # (row-1, col+1) = 2, not to 0 and 8: TTK's orientation (last axis negated).
    assert adjacency(FreudenthalNeighborhood((3, 3)))[4] == {1, 2, 3, 5, 6, 7}


def test_freudenthal_each_edge_once_and_no_self_loops():
    nb = FreudenthalNeighborhood((4, 3, 5))
    pairs = [tuple(sorted(p)) for s, d in nb.edge_blocks() for p in zip(s.tolist(), d.tolist())]
    assert len(pairs) == len(set(pairs)) and all(i != j for i, j in pairs)


def test_freudenthal_rejects_bad_shapes():
    for shape in [(), (3, 0)]:
        with pytest.raises(ValueError, match="invalid grid shape"):
            FreudenthalNeighborhood(shape)


@pytest.mark.slow
@pytest.mark.parametrize("shape", [(23, 31), (9, 11, 13)])
def test_freudenthal_maxima_equal_ttk_pl_maxima(shape):
    """The reason this stencil exists: same local maxima as TTK's triangulation, vertex for vertex."""
    pytest.importorskip("topologytoolkit")
    from vtkmodules.util.numpy_support import vtk_to_numpy

    from topospine.sources.ttk_backend import import_ttk, numpy_to_image

    values = np.random.default_rng(len(shape)).random(shape)
    f = import_ttk().ttkScalarFieldCriticalPoints()
    f.SetInputDataObject(numpy_to_image(values, (1.0,) * len(shape), (0.0,) * len(shape)))
    f.SetInputArrayToProcess(0, 0, 0, 0, "f")
    f.Update()
    pd = f.GetOutput().GetPointData()
    local_maximum = 3                                                # TTK CriticalType code
    ttk_max = vtk_to_numpy(pd.GetArray("ttkVertexScalarField"))[vtk_to_numpy(pd.GetArray("CriticalType")) == local_maximum]
    nb = FreudenthalNeighborhood(shape)
    ours = np.flatnonzero(steepest_ascent(sample_ranks(values), nb) == np.arange(values.size))
    assert sorted(ours.tolist()) == sorted(ttk_max.tolist())
    full = GridNeighborhood(shape, 3 ** len(shape) - 1)                # today's default, for contrast
    assert sorted(np.flatnonzero(steepest_ascent(sample_ranks(values), full) == np.arange(values.size)).tolist()) \
        != sorted(ttk_max.tolist())


def test_knn_is_symmetrised():
    pts = np.array([[0.0], [1.0], [3.0], [10.0]])
    adj = adjacency(KnnNeighborhood(pts, k=1))
    # 3 -> 2 is one-directional in plain 1-NN; symmetrised, 2 also sees 3.
    assert adj == [{1}, {0, 2}, {1, 3}, {2}]


def test_knn_excludes_self_and_has_k_columns():
    rng = np.random.default_rng(0)
    nb = KnnNeighborhood(rng.normal(size=(50, 4)), k=5)
    assert nb.neighbors.shape == (50, 5)
    assert not (nb.neighbors == np.arange(50)[:, None]).any()


def test_knn_input_validation():
    with pytest.raises(ValueError):
        KnnNeighborhood(np.zeros((4, 2)) + np.arange(4)[:, None], k=4)   # k >= n
    with pytest.raises(ValueError):
        KnnNeighborhood(np.zeros(5), k=1)                                  # not (n, d)
    with pytest.raises(ValueError):
        KnnNeighborhood(np.zeros((5, 2)), k=1)                             # > k duplicates

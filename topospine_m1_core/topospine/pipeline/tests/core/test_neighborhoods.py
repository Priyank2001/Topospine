import numpy as np
import pytest

from topospine.core.neighborhoods import GridNeighborhood, KnnNeighborhood


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

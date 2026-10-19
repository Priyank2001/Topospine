import numpy as np
import pytest

from topospine.core.datasets import GridDataset, PointDataset, normalize_points


def test_grid_positions_are_xyz_and_physical():
    g = GridDataset("t", np.zeros((2, 3, 4)), spacing=(10.0, 2.0, 1.0), origin=(100.0, 0.0, 0.5))
    # flat index 1*12 + 2*4 + 3 = sample (z=1, y=2, x=3)
    assert g.positions(np.array([23])).tolist() == [[3.5, 4.0, 110.0]]   # catches z/x swaps


def test_grid_validation():
    with pytest.raises(ValueError):
        GridDataset("t", np.zeros((2, 2)), spacing=(1.0,), origin=(0.0, 0.0))
    with pytest.raises(ValueError):
        GridDataset("t", np.array([[0.0, np.nan]]), spacing=(1, 1), origin=(0, 0))


def test_with_values_keeps_geometry():
    g = GridDataset("t", np.arange(6.0).reshape(2, 3), (1.0, 2.0), (0.0, 0.0))
    h = g.with_values(-g.values.ravel())
    assert h.shape == (2, 3) and h.spacing == g.spacing and h.values[1, 2] == -5


@pytest.mark.parametrize("method", ["none", "zscore", "minmax"])
def test_normalize_roundtrip(method):
    p = np.array([[0.0, 5.0], [2.0, 5.0], [4.0, 5.0]])
    n, off, sc = normalize_points(p, method)
    assert np.allclose(n * sc + off, p)          # original recoverable
    assert np.isfinite(n).all()                  # constant column doesn't divide by zero


def test_normalize_unknown():
    with pytest.raises(ValueError):
        normalize_points(np.zeros((2, 2)), "robust")


def test_point_dataset_checks():
    with pytest.raises(ValueError):
        PointDataset("p", np.zeros((3, 2)), np.zeros(4), ("a", "b"))
    with pytest.raises(ValueError):
        PointDataset("p", np.zeros((3, 2)), np.zeros(3), ("a",))

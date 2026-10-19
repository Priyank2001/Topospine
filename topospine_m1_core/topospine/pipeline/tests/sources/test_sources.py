import numpy as np
import pytest

from topospine.core import GridNeighborhood, compute_persistence, decompose, graph_from_regions
from topospine.core.datasets import GridDataset
from topospine.io.synthetic import bumps_grid, sample_points
from topospine.sources import make_source
from topospine.sources.native_source import NativeSource
from topospine.sources.ttk_source import TtkSource, compact_labels, maximum_score, numpy_to_image, pick_maximum_regions


@pytest.fixture
def bumps3d():
    return bumps_grid((24, 20, 16), centers=[[0.3, 0.3, 0.5], [0.7, 0.6, 0.5]], heights=[1.0, 0.8], width=0.15)


def test_native_grid_defaults_to_full_stencil(bumps3d):
    assert NativeSource().neighborhood(bumps3d).connectivity == 26


def test_native_grid_and_points(bumps3d):
    assert NativeSource().compute(bumps3d).graph.maxima.size == 2
    pts = sample_points("mixture", 2, 1500, 0, 1, centers=[[0.3, 0.5], [0.7, 0.5]], heights=[1, 0.6], width=0.1)
    dec = NativeSource(k=20).compute(pts)
    assert (compute_persistence(dec.graph).persistence[dec.graph.maxima] >= 0.1).sum() == 2


def test_make_source():
    assert isinstance(make_source("native", k=5), NativeSource)
    with pytest.raises(ValueError):
        make_source("tachyon")


def test_compact_labels():
    assert compact_labels(np.array([7, 3, 7, 12])).tolist() == [1, 0, 1, 2]


def test_graph_from_regions_matches_native_after_relabel(bumps3d):
    native = NativeSource().compute(bumps3d)
    ttk_like = np.where(native.labels == 0, 41, 17)           # arbitrary ids, as TTK would give
    nb = GridNeighborhood(bumps3d.shape, 26)
    dec = graph_from_regions(bumps3d.values, compact_labels(ttk_like), nb)
    assert sorted(dec.graph.values.tolist()) == sorted(native.graph.values.tolist())


def test_picks_maxima_regions_over_minima_regions():
    g = bumps_grid((64, 64), centers=[[0.25, 0.25], [0.75, 0.75], [0.25, 0.75]], heights=[1, 0.9, 0.8], width=0.12)
    nb = GridNeighborhood(g.shape, 8)
    maxima_regions = decompose(g.values, nb).labels
    minima_regions = decompose(-g.values, nb).labels
    assert maximum_score(g.values, maxima_regions, nb) == 1.0
    name, _, scores = pick_maximum_regions(g.values, {"A": minima_regions, "B": maxima_regions}, nb)
    assert name == "B" and scores["A"] < 1.0                  # a name mix-up in TTK can't fool us


def test_ttk_source_with_fake_backend(bumps3d, monkeypatch):
    native = NativeSource().compute(bumps3d)
    src = TtkSource()
    monkeypatch.setattr(src, "_run_ttk", lambda ds: {"DescendingManifold": native.labels * 5 + 2})
    dec = src.compute(bumps3d)
    assert src.last_choice[0] == "DescendingManifold"
    assert np.array_equal(dec.graph.values, native.graph.values)


def test_ttk_source_rejects_points():
    with pytest.raises(ValueError):
        TtkSource().compute(sample_points("ackley", 2, 50, -1, 1))


def test_numpy_to_image_axis_order():
    pytest.importorskip("vtkmodules")
    img = numpy_to_image(np.zeros((2, 3, 4)), spacing=(3.0, 2.0, 1.0), origin=(0, 0, 0))
    assert img.GetDimensions() == (4, 3, 2) and img.GetSpacing() == (1.0, 2.0, 3.0)


@pytest.mark.slow
def test_real_ttk_matches_native(bumps3d):
    pytest.importorskip("topologytoolkit")
    nat = NativeSource().compute(bumps3d)
    ttk = TtkSource().compute(bumps3d)
    p_nat = np.sort(compute_persistence(nat.graph).persistence[nat.graph.maxima])
    p_ttk = np.sort(compute_persistence(ttk.graph).persistence[ttk.graph.maxima])
    assert p_ttk.size == p_nat.size and np.allclose(p_ttk, p_nat, rtol=0.05)

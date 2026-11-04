import numpy as np
import pytest

from tests.conftest import A, B, C, D, LINE_VALUES
from topospine.core import GridNeighborhood, decompose, sample_ranks
from topospine.core.datasets import GridDataset
from topospine.io.synthetic import bumps_grid, sample_points
from topospine.sources.base import ExtractionContext
from topospine.sources.composed_source import ComposedSource
from topospine.sources.native_blocks import AscentRegions, BoundarySaddles
from topospine.sources.native_source import NativeSource


def _line_ctx():
    ds = GridDataset("line", LINE_VALUES, spacing=(1.0,), origin=(0.0,))
    return ExtractionContext(ds, sample_ranks(LINE_VALUES), GridNeighborhood(LINE_VALUES.shape, 2))


def test_ascent_regions_on_the_line_example():
    assert AscentRegions().labels(_line_ctx()).tolist() == [A, A, A, B, C, C, C, D, D]


def test_boundary_saddles_on_the_line_example():
    ctx = _line_ctx()
    s = BoundarySaddles().saddles(ctx, AscentRegions().labels(ctx))
    assert s.samples.tolist() == [2, 4, 6]                        # lower end of each region pair's highest edge
    assert s.pairs.tolist() == [[A, B], [B, C], [C, D]]


def test_block_names_and_compatibility():
    assert (AscentRegions.name, BoundarySaddles.name) == ("ascent", "boundary")
    assert BoundarySaddles.requires_regions is None               # pairs with any region method (D-007)


def _same(dec, ref):
    assert dec.labels.tolist() == ref.labels.tolist()
    for field in ("kinds", "samples", "values", "arcs"):
        assert getattr(dec.graph, field).tolist() == getattr(ref.graph, field).tolist(), field


@pytest.mark.parametrize("dataset", [
    bumps_grid((24, 20, 16), centers=[[0.3, 0.3, 0.5], [0.7, 0.6, 0.5]], heights=[1.0, 0.8], width=0.15),
    bumps_grid((40, 30), centers=[[0.2, 0.3], [0.7, 0.7], [0.5, 0.2]], heights=[1.0, 0.9, 0.7], width=0.1),
], ids=["grid3d", "grid2d"])
@pytest.mark.parametrize("stencil", ["full", "face"])
def test_composed_native_equals_decompose_on_grids(dataset, stencil):
    conn = None if stencil == "full" else 2 * len(dataset.shape)
    src = NativeSource(connectivity=conn)
    _same(src.compute(dataset), decompose(dataset.values, src.neighborhood(dataset)))


def test_composed_native_equals_decompose_on_points():
    pts = sample_points("mixture", 2, 1200, 0, 1, centers=[[0.3, 0.5], [0.7, 0.5]], heights=[1, 0.6], width=0.1)
    src = NativeSource(k=12)
    _same(src.compute(pts), decompose(pts.values, src.neighborhood(pts)))


def test_native_source_is_the_ascent_boundary_preset():
    src = NativeSource(connectivity=6, k=7)
    assert isinstance(src, ComposedSource)
    assert (src.regions.name, src.saddles.name) == ("ascent", "boundary")
    assert (src.connectivity, src.k, src.name) == (6, 7, "native")   # name kept until file 7 (D-006)

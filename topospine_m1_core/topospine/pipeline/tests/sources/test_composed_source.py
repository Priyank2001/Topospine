import numpy as np
import pytest

from tests.conftest import A, B, C, D, LINE_VALUES
from topospine.core import SaddleSet, sample_ranks
from topospine.core.datasets import GridDataset
from topospine.io.synthetic import bumps_grid, sample_points
from topospine.sources.composed_source import ComposedSource

LINE_LABELS = np.array([A, A, A, B, C, C, C, D, D])
LINE_SADDLES = SaddleSet(np.array([2, 4, 6]), np.array([[A, B], [B, C], [C, D]]))


class FakeRegions:
    def __init__(self, labels, name="fake_r"):
        self.name, self._labels, self.seen = name, labels, None

    def labels(self, ctx):
        self.seen = ctx
        return self._labels


class FakeSaddles:
    def __init__(self, saddles=LINE_SADDLES, requires_regions=None, name="fake_s"):
        self.name, self._saddles, self.requires_regions, self.seen = name, saddles, requires_regions, None

    def saddles(self, ctx, labels):
        self.seen = (ctx, labels)
        return self._saddles


@pytest.fixture
def line_ds():
    return GridDataset("line", LINE_VALUES, spacing=(1.0,), origin=(0.0,))


def test_composes_the_line_example(line_example, line_ds):
    dec = ComposedSource(FakeRegions(LINE_LABELS), FakeSaddles()).compute(line_ds)
    ref = line_example[0].graph
    assert dec.graph.samples.tolist() == ref.samples.tolist()       # blocks wired into assemble_flow correctly
    assert dec.graph.arcs.tolist() == ref.arcs.tolist()
    assert dec.labels.tolist() == LINE_LABELS.tolist()


def test_both_blocks_share_one_context(line_ds):
    regions, saddles = FakeRegions(LINE_LABELS), FakeSaddles()
    ComposedSource(regions, saddles).compute(line_ds)
    ctx, labels = saddles.seen
    assert regions.seen is ctx                                       # one ctx: same ranks, same neighbourhood
    assert ctx.ranks.tolist() == sample_ranks(LINE_VALUES).tolist()
    assert labels is LINE_LABELS                                     # saddles see block 1's labels unchanged


def test_name_joins_block_names():
    assert ComposedSource(FakeRegions(LINE_LABELS), FakeSaddles()).name == "fake_r+fake_s"


def test_neighbourhood_defaults_and_overrides():
    grid = bumps_grid((8, 7, 6), centers=[[0.5, 0.5, 0.5]], heights=[1.0], width=0.2)
    pts = sample_points("ackley", 2, 60, -1, 1)
    src = ComposedSource(FakeRegions(None), FakeSaddles())
    assert src.neighborhood(grid).connectivity == 26                 # full 3-D stencil by default
    assert ComposedSource(FakeRegions(None), FakeSaddles(), connectivity=6).neighborhood(grid).connectivity == 6
    assert ComposedSource(FakeRegions(None), FakeSaddles(), k=9).neighborhood(pts).k == 9


def test_incompatible_blocks_rejected_before_any_data():
    # D-007: a saddle method tied to one region method can't be joined to another.
    with pytest.raises(ValueError, match="D-007"):
        ComposedSource(FakeRegions(LINE_LABELS, name="ascent"), FakeSaddles(requires_regions="ttk"))


def test_compatible_or_unrestricted_blocks_accepted():
    ComposedSource(FakeRegions(LINE_LABELS, name="ttk"), FakeSaddles(requires_regions="ttk"))
    ComposedSource(FakeRegions(LINE_LABELS, name="ascent"), FakeSaddles(requires_regions=None))


def test_bad_labels_from_a_region_method_are_rejected(line_ds):
    gap = np.array([0, 0, 0, 2, 2, 2, 2, 3, 3])                      # region 1 missing
    with pytest.raises(ValueError):
        ComposedSource(FakeRegions(gap), FakeSaddles(SaddleSet(np.empty(0), np.empty(0)))).compute(line_ds)


# ------------------------------------------------------------ connectivity: ttk (D-016, D-017)

def test_ttk_connectivity_gives_ttks_mesh():
    from topospine.core import FreudenthalNeighborhood
    src = ComposedSource(FakeRegions(LINE_LABELS), FakeSaddles(), connectivity="ttk")
    nb = src.neighborhood(bumps_grid((12, 10)))
    assert isinstance(nb, FreudenthalNeighborhood) and nb.connectivity == 6
    assert src.neighborhood(bumps_grid((6, 5, 4), centers=[[0.5, 0.5, 0.5]], heights=[1.0])).connectivity == 14


def test_unknown_stencil_name_fails_at_construction():
    with pytest.raises(ValueError, match=r"unknown connectivity 'tkk'.*\['ttk'\]"):
        ComposedSource(FakeRegions(LINE_LABELS), FakeSaddles(), connectivity="tkk")


def test_ttk_connectivity_is_for_grids_only():
    pts = sample_points("ackley", 2, 60, -1, 1)
    with pytest.raises(ValueError, match="applies to grids"):
        ComposedSource(FakeRegions(LINE_LABELS), FakeSaddles(), connectivity="ttk").neighborhood(pts)


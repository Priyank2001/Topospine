import numpy as np
import pytest

from topospine.core.datasets import GridDataset
from topospine.io.synthetic import bumps_grid, sample_points
from topospine.sources.ttk_simplify import TtkSimplifier, count_maxima_on_ttk_mesh

# 1-D: peaks at samples 1 (f=3) and 3 (f=2); the second has persistence 1.
LINE = np.array([0.0, 3.0, 1.0, 2.0, 0.0])
FLATTENED = np.array([0.0, 3.0, 1.0, 0.5, 0.0])      # what removing the small peak looks like


def _line():
    return GridDataset("line", LINE.copy(), spacing=(1.0,), origin=(0.0,))


class FakeRunner:
    def __init__(self, out=FLATTENED):
        self.out, self.calls = out, []

    def __call__(self, values, spacing, origin, threshold, absolute):
        self.calls.append((values.copy(), tuple(spacing), tuple(origin), threshold, absolute))
        return self.out.copy()


def test_returns_a_new_dataset_with_the_simplified_values():
    ds, runner = _line(), FakeRunner()
    out = TtkSimplifier(0.4, runner=runner).simplify(ds)
    assert out.values.tolist() == FLATTENED.tolist()
    assert (out.name, out.spacing, out.origin) == (ds.name, ds.spacing, ds.origin)
    assert ds.values.tolist() == LINE.tolist()                       # input untouched


def test_runner_gets_the_threshold_and_unit():
    runner = FakeRunner()
    TtkSimplifier(7.5, absolute=True, runner=runner).simplify(_line())
    assert runner.calls[0][1:] == ((1.0,), (0.0,), 7.5, True)


def test_report_counts_maxima_on_ttks_mesh():
    s = TtkSimplifier(0.4, runner=FakeRunner())
    assert s.report() == {"threshold": 0.4, "absolute": False}       # nothing run yet
    s.simplify(_line())
    assert s.report() == {"threshold": 0.4, "absolute": False, "maxima_before": 2, "maxima_after": 1}


def test_count_maxima_uses_ttks_mesh_not_the_full_stencil():
    # Peaks at (0,0) and (1,1). TTK's mesh links (0,1)-(1,0), NOT (0,0)-(1,1), so both are
    # maxima there; with both diagonals the lower one sees the higher one and isn't.
    from topospine.core import GridNeighborhood, sample_ranks, steepest_ascent
    values = np.array([[3.0, 0.0], [1.0, 2.0]])
    assert count_maxima_on_ttk_mesh(values) == 2
    full = steepest_ascent(sample_ranks(values), GridNeighborhood((2, 2), 8)) == np.arange(4)
    assert int(full.sum()) == 1


@pytest.mark.parametrize("threshold, absolute", [(0, False), (-0.1, False), (1.5, False), (0, True)])
def test_rejects_bad_thresholds(threshold, absolute):
    with pytest.raises(ValueError, match="simplify threshold"):
        TtkSimplifier(threshold, absolute=absolute, runner=FakeRunner())


def test_absolute_threshold_may_exceed_one():
    assert TtkSimplifier(12.0, absolute=True, runner=FakeRunner()).threshold == 12.0


def test_point_data_is_rejected_before_running():
    runner = FakeRunner()
    with pytest.raises(ValueError, match="grid data"):
        TtkSimplifier(0.1, runner=runner).simplify(sample_points("ackley", 2, 50, -1, 1))
    assert runner.calls == []


def test_a_runner_that_changes_the_shape_is_an_error():
    with pytest.raises(RuntimeError, match="changed the shape"):
        TtkSimplifier(0.1, runner=FakeRunner(np.zeros(3))).simplify(_line())


@pytest.mark.slow
def test_real_ttk_removes_every_feature_below_the_threshold():
    """The guarantee: after simplifying at t, no maximum has 0 < persistence < t, in any method.

    (Not "exactly 2 maxima": a border maximum with persistence 5.2 % > 5 % rightly survives
    on TTK's mesh; TTK's regions show it as a zero-persistence extra region.)
    """
    pytest.importorskip("topologytoolkit")
    from topospine.core import compute_persistence
    from topospine.sources import compose_source

    g = bumps_grid((24, 20, 16), centers=[[0.3, 0.3, 0.5], [0.7, 0.6, 0.5]], heights=[1.0, 0.8], width=0.15)
    noisy = g.with_values(g.values + 0.02 * np.random.default_rng(0).standard_normal(g.values.shape))
    t = 0.05
    s = TtkSimplifier(t)
    out = s.simplify(noisy)
    rng = float(np.ptp(noisy.values))
    assert s.report()["maxima_after"] < 0.05 * s.report()["maxima_before"]      # 297 -> 3
    assert np.abs(out.values - noisy.values).max() <= t * rng * 1.01             # flattened by at most t
    second = set()
    for r, sd in [("ascent", "boundary"), ("ttk", "boundary"), ("ttk", "ttk")]:
        gr = compose_source(r, sd, connectivity="ttk").compute(out).graph
        p = compute_persistence(gr).persistence[gr.maxima] / rng
        fin = p[np.isfinite(p)]
        assert not ((fin > 1e-9) & (fin < t)).any(), (r, sd, fin)               # nothing between 0 and t
        second.add(round(float(fin.max()), 6))
    assert len(second) == 1                                                      # all agree on the real 2nd peak

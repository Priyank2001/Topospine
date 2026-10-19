import numpy as np
import pytest

from topospine.core import GridNeighborhood, KnnNeighborhood, compute_persistence, decompose
from topospine.io.synthetic import ackley, bumps_grid, make_synthetic, ring_grid, sample_points


def test_bumps_maxima_at_centres():
    g = bumps_grid((64, 48), centers=[[0.25, 0.5], [0.75, 0.25]], heights=[1.0, 0.7], width=0.08)
    dec = decompose(g.values, GridNeighborhood(g.shape, 8))
    pos = g.positions(dec.graph.samples[dec.graph.maxima])
    assert dec.graph.maxima.size == 2
    assert np.allclose(sorted(pos.tolist()), [[0.25, 0.5], [0.75, 0.25]], atol=0.02)


def test_ring_has_a_cycle():
    g = ring_grid(96, count=6)
    dec = decompose(g.values, GridNeighborhood(g.shape, 8))
    pers = compute_persistence(dec.graph)
    assert dec.graph.maxima.size == 6
    cancellations = int((pers.merged_into >= 0).sum())
    assert dec.graph.saddles.size - cancellations >= 1     # at least one saddle closes the loop


def test_ackley_minima_count_2d():
    p = sample_points("ackley", dim=2, n=6000, low=-1.5, high=1.5, seed=0)
    dec = decompose(-p.values, KnnNeighborhood(p.points, 15))
    P = compute_persistence(dec.graph).persistence[dec.graph.maxima]
    assert (P >= 0.05).sum() == 9                           # 3^2 minima (paper Fig. 13a)


def test_ackley_global_minimum_at_origin():
    assert ackley(np.zeros((1, 3)))[0] == pytest.approx(0.0, abs=1e-12)


def test_generator_errors():
    with pytest.raises(ValueError):
        make_synthetic("spiral")
    with pytest.raises(ValueError):
        sample_points("rosenbrock", 2, 10, 0, 1)
    with pytest.raises(ValueError):
        bumps_grid((10, 10), centers=[[0.5, 0.5, 0.5]], heights=[1.0])

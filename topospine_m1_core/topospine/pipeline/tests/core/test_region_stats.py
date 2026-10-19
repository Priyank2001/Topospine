import numpy as np
import pytest

from tests.conftest import A, B, C, D, LINE_VALUES
from topospine.core import region_histograms, representatives


@pytest.fixture
def hist(line_example):
    dec, _ = line_example
    # 10 unit bins over [0, 10] so every integer value sits on a bin edge.
    return region_histograms(LINE_VALUES, dec.labels, num_regions=7, bins=10, value_range=(0, 10))


def test_sizes(hist):
    assert hist.sizes.tolist() == [3, 1, 3, 2, 0, 0, 0]          # region rows indexed by maximum node id


def test_counts_land_in_right_bins(hist):
    assert hist.counts[C].nonzero()[0].tolist() == [2, 6, 9]     # values 2, 6, 9


def test_count_between_exact_on_bin_edges(hist):
    # r_us for region A between isovalues 3 and 6: samples with f in [3, 6) -> {3, 5}
    assert hist.count_between(A, 3.0, 6.0) == pytest.approx(2.0)
    assert hist.count_between(A, 6.0, 3.0) == pytest.approx(2.0)  # argument order doesn't matter
    assert hist.count_at_or_above(A, -5.0) == 3 and hist.count_at_or_above(A, 50.0) == 0


def test_count_interpolates_inside_bin(hist):
    assert hist.count_at_or_above(B, 4.5) == pytest.approx(0.5)  # uniform-within-bin assumption


def test_merge_follows_representatives(line_example, hist):
    _, pers = line_example
    rep = representatives(pers, 2.5)
    merged = hist.merged(rep)
    assert merged.sizes[[A, B, C, D]].tolist() == [4, 0, 5, 0]   # B into A, D into C
    assert merged.sizes.sum() == 9                               # no samples lost


def test_values_outside_range_clip():
    h = region_histograms(np.array([-5.0, 0.5, 99.0]), np.array([0, 0, 0]), 1, bins=2, value_range=(0, 1))
    assert h.counts[0].tolist() == [1, 2]   # -5 -> bin 0; 0.5 (on the edge) and 99 -> bin 1


def test_constant_field_and_validation():
    h = region_histograms(np.ones(4), np.zeros(4, dtype=int), 1, bins=3)
    assert h.sizes.tolist() == [4]
    with pytest.raises(ValueError):
        region_histograms(np.ones(3), np.array([0, 1, 5]), 2)

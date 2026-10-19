"""Shared fixtures: the 9-sample worked example from the M1 walkthrough.

f = [1, 5, 3, 4, 2, 9, 6, 8, 0] on a line. Maxima A, B, C, D sit at samples
1, 3, 5, 7 (node ids 0..3); saddles s1, s2, s3 at samples 2, 4, 6 (node ids 4..6).
"""

import numpy as np
import pytest

from topospine.core import GridNeighborhood, compute_persistence, decompose

LINE_VALUES = np.array([1, 5, 3, 4, 2, 9, 6, 8, 0], dtype=float)
A, B, C, D, S1, S2, S3 = range(7)


@pytest.fixture
def line_example():
    dec = decompose(LINE_VALUES, GridNeighborhood((9,), connectivity=2))
    return dec, compute_persistence(dec.graph)

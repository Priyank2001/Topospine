"""Per-region value histograms: the data behind the spine's link radius.

Correa et al. 2011, Sec. 4.2: for maximum u, saddle s, a point p on the arc and an
isovalue c,

    r_us(c, p) = |{ x in D(u) : min(c, f(p)) < f(x) < max(c, f(p)) }|

i.e. how many samples of u's region lie between two isovalues. With a histogram of
f over each region, that is a difference of two "count at or above" lookups, so the
browser never needs per-sample data to size the spine. When simplification merges
regions, their histograms simply add up (`merged`).

Approximation: within a bin, samples are assumed uniformly spread, so lookups are
exact at bin edges and linearly interpolated inside a bin (docs/DEVIATIONS.md).
Counts are sample counts; multiply by the voxel volume for physical volume.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, eq=False)
class RegionHistograms:
    bin_edges: NDArray[np.float64]  # (B+1,) shared by all regions
    counts: NDArray[np.int64]       # (R, B)

    @property
    def sizes(self) -> NDArray[np.int64]:
        """Samples per region: the 'how much data each peak holds' encoding."""
        return self.counts.sum(axis=1)

    def merged(self, representative: NDArray[np.int64]) -> RegionHistograms:
        """Sum each region's row into its representative's row (others become zero)."""
        rep = np.asarray(representative, dtype=np.int64)
        if rep.shape != (self.counts.shape[0],):
            raise ValueError("need one representative per region")
        out = np.zeros_like(self.counts)
        np.add.at(out, rep, self.counts)
        return RegionHistograms(bin_edges=self.bin_edges, counts=out)

    def count_at_or_above(self, region: int, c: float) -> float:
        edges, h = self.bin_edges, self.counts[region]
        if c <= edges[0]:
            return float(h.sum())
        if c >= edges[-1]:
            return 0.0
        k = int(np.searchsorted(edges, c, side="right") - 1)  # edges[k] <= c < edges[k+1]
        frac_above = (edges[k + 1] - c) / (edges[k + 1] - edges[k])
        return float(h[k + 1:].sum() + frac_above * h[k])

    def count_between(self, region: int, c0: float, c1: float) -> float:
        """r_us: samples of `region` with value between c0 and c1 (order-agnostic)."""
        lo, hi = min(c0, c1), max(c0, c1)
        return self.count_at_or_above(region, lo) - self.count_at_or_above(region, hi)


def region_histograms(
    values: NDArray[np.floating],
    labels: NDArray[np.integer],
    num_regions: int,
    bins: int = 64,
    value_range: tuple[float, float] | None = None,
) -> RegionHistograms:
    """Histogram of f per region with shared bins. Values outside value_range clip
    into the end bins; the top edge is inclusive."""
    v = np.asarray(values, dtype=np.float64).ravel()
    lab = np.asarray(labels, dtype=np.int64).ravel()
    if v.shape != lab.shape:
        raise ValueError("values and labels must have the same number of samples")
    if bins < 1 or num_regions < 1:
        raise ValueError("bins and num_regions must be positive")
    if lab.size and (lab.min() < 0 or lab.max() >= num_regions):
        raise ValueError("label out of range")
    lo, hi = value_range if value_range is not None else (float(v.min()), float(v.max()))
    if hi <= lo:
        hi = lo + 1.0  # constant field: one meaningful bin, avoid divide-by-zero
    edges = np.linspace(lo, hi, bins + 1)
    b = np.clip(np.floor((v - lo) / (hi - lo) * bins).astype(np.int64), 0, bins - 1)
    counts = np.bincount(lab * bins + b, minlength=num_regions * bins).reshape(num_regions, bins)
    return RegionHistograms(bin_edges=edges, counts=counts.astype(np.int64))

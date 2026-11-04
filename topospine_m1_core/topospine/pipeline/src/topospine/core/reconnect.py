"""Join the pieces of a saddle set that leaves regions disconnected (DECISIONS.md D-011).

Some saddle methods (TTK's, after D-009 drops one-sided saddles) can leave the regions
in several pieces: groups of peaks with no saddle between them. Each piece's top would
then get infinite persistence, as if it were a second global maximum.

    kept saddles ─► union-find over regions ─► pieces
    candidates (e.g. boundary_saddles), highest first:
        joins two different pieces?  yes ─► add it, merge the pieces
                                      no  ─► skip (the kept saddles already cover it)

Highest first = Kruskal's algorithm for a maximum spanning forest: every piece is joined
to the rest at its highest pass, the same saddle a merge tree would use. Nothing is
added when the kept saddles already connect everything, and kept saddles are never removed.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from topospine.core.gradient_flow import SaddleSet


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = np.arange(n)

    def find(self, a: int) -> int:
        p = self._parent
        while p[a] != a:
            p[a] = p[p[a]]      # path halving
            a = int(p[a])
        return a

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self._parent[rb] = ra
        return True


def count_pieces(pairs: NDArray[np.int64], num_regions: int) -> int:
    """Number of connected groups of regions when every pair is an edge."""
    uf = _UnionFind(num_regions)
    joined = sum(uf.union(int(a), int(b)) for a, b in pairs)
    return num_regions - joined


def connect_pieces(saddles: SaddleSet, candidates: SaddleSet, ranks: NDArray[np.int64],
                   num_regions: int) -> tuple[SaddleSet, int]:
    """saddles plus the fewest candidates (highest first) that connect every piece.

    ranks: sample_ranks of the values, so "highest" breaks ties like the rest of core.
    Returns the combined set in increasing sample order and how many candidates were added.
    Regions that no candidate touches stay separate (nothing to join them with).
    """
    uf = _UnionFind(num_regions)
    for a, b in saddles.pairs:
        uf.union(int(a), int(b))
    order = np.argsort(-ranks[candidates.samples], kind="stable")
    added = [i for i in order if uf.union(int(candidates.pairs[i, 0]), int(candidates.pairs[i, 1]))]
    if not added:
        return saddles, 0
    samples = np.r_[saddles.samples, candidates.samples[added]].astype(np.int64)
    pairs = np.r_[saddles.pairs.reshape(-1, 2), candidates.pairs[added]].astype(np.int64)
    by_sample = np.argsort(samples, kind="stable")
    return SaddleSet(samples[by_sample], pairs[by_sample]), len(added)

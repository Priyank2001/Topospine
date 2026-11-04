"""Neighbourhoods: the only thing that differs between grid data and point data.

Steepest ascent and saddle detection (gradient_flow.py) only ever ask one question:
"give me the edges". So a neighbourhood is anything that can stream its undirected
edges in blocks of (src, dst) index arrays.

Why blocks instead of an adjacency matrix / CSR?
    A 128^3 grid with 26-connectivity has ~27M undirected edges; a full CSR in int64
    is ~430 MB. Streaming one block per stencil offset (13 blocks of ~2M edges each)
    keeps peak memory near 2 x 16 MB while staying fully vectorised.

Contract for implementations
    * edges are undirected: consumers treat (i, j) as i~j AND j~i;
    * every edge appears in at least one block (duplicates are allowed and harmless,
      because consumers only take maxima over edges);
    * no self-loops.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

EdgeBlock = tuple[NDArray[np.intp], NDArray[np.intp]]


class Neighborhood(Protocol):
    @property
    def num_samples(self) -> int: ...

    def edge_blocks(self) -> Iterator[EdgeBlock]: ...


def _grid_shape(shape: Sequence[int]) -> tuple[int, ...]:
    out = tuple(int(s) for s in shape)
    if not out or any(s < 1 for s in out):
        raise ValueError(f"invalid grid shape {shape!r}")
    return out


class _StencilNeighborhood:
    """A regular grid whose edges are given by a half stencil of offsets.

    Samples are flattened in C order (last axis fastest). `offsets` holds one offset of
    each +/- pair, so every undirected edge is produced exactly once.
    """

    def __init__(self, shape: Sequence[int], offsets: list[tuple[int, ...]]) -> None:
        self.shape = _grid_shape(shape)
        self._offsets = offsets

    @property
    def num_samples(self) -> int:
        return int(np.prod(self.shape))

    @property
    def connectivity(self) -> int:
        """Neighbours of an interior sample."""
        return 2 * len(self._offsets)

    def edge_blocks(self) -> Iterator[EdgeBlock]:
        index = np.arange(self.num_samples, dtype=np.intp).reshape(self.shape)
        for offset in self._offsets:
            src_sl, dst_sl = [], []
            for c in offset:
                if c == 1:
                    src_sl.append(slice(0, -1))
                    dst_sl.append(slice(1, None))
                elif c == -1:
                    src_sl.append(slice(1, None))
                    dst_sl.append(slice(0, -1))
                else:
                    src_sl.append(slice(None))
                    dst_sl.append(slice(None))
            src = index[tuple(src_sl)].ravel()
            if src.size:
                yield src, index[tuple(dst_sl)].ravel()


def _half(offsets: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    """One offset of each +/- pair: the one whose first non-zero component is positive."""
    return [o if next(c for c in o if c) > 0 else tuple(-c for c in o) for o in offsets]


class GridNeighborhood(_StencilNeighborhood):
    """Regular grid with a symmetric stencil.

    `connectivity` picks a stencil by its size: 1-D: 2; 2-D: 4 or 8;
    3-D: 6, 18 or 26 (faces / +edges / +corners). Internally this is "all offsets in
    {-1,0,1}^d with L1 norm <= r", which generalises to any dimension.
    """

    def __init__(self, shape: Sequence[int], connectivity: int) -> None:
        dim = len(_grid_shape(shape))
        super().__init__(shape, self._half_stencil(dim, int(connectivity)))

    @staticmethod
    def _half_stencil(dim: int, connectivity: int) -> list[tuple[int, ...]]:
        all_offsets = [o for o in itertools.product((-1, 0, 1), repeat=dim) if any(o)]
        sizes = {r: sum(1 for o in all_offsets if sum(map(abs, o)) <= r) for r in range(1, dim + 1)}
        radius = next((r for r, size in sizes.items() if size == connectivity), None)
        if radius is None:
            raise ValueError(f"connectivity {connectivity} invalid for {dim}-D; choose one of {sorted(sizes.values())}")
        return [o for o in all_offsets if sum(map(abs, o)) <= radius and next(c for c in o if c) > 0]


class FreudenthalNeighborhood(_StencilNeighborhood):
    """The edges of TTK's grid triangulation (config name `connectivity: ttk`, D-016).

    TTK splits each grid square (cube) into triangles (tetrahedra) along ONE diagonal
    direction (the Freudenthal / Kuhn subdivision), so a sample has 6 neighbours in 2-D and
    14 in 3-D, not 8 / 26. Offsets: every non-zero vector in {0,1}^d with the LAST array
    axis (x, the fastest) negated; 2-D: (0,1), (1,0), (1,-1).

    Why it matters: with both diagonals, two regions can touch across a diagonal above the
    true saddle, so saddles come out too high and persistence too low (M3_NOTES.md §3).
    The orientation was found by experiment: on this stencil our local maxima equal TTK's
    piecewise-linear maxima vertex for vertex (temp/evidence/ttk_mesh_orientation.py);
    the other orientations don't.
    """

    def __init__(self, shape: Sequence[int]) -> None:
        dim = len(_grid_shape(shape))
        flip = (1,) * (dim - 1) + (-1,)
        offsets = [tuple(f * c for f, c in zip(flip, o)) for o in itertools.product((0, 1), repeat=dim) if any(o)]
        super().__init__(shape, _half(offsets))


class KnnNeighborhood:
    """Symmetrised k-nearest-neighbour graph of a point cloud (Euclidean distance).

    Symmetrised means i~j if j is among i's k nearest OR i among j's. That falls out
    of the "edges are undirected" contract: block t is (i, t-th neighbour of i), and
    consumers apply each edge in both directions. Without symmetry a region boundary
    could be visible from one side only, making saddles depend on visiting order.

    Scale matters: distances mix all coordinates, so normalise features with
    different units before building this (done in the reader/source, not here).
    """

    def __init__(self, points: NDArray[np.floating], k: int) -> None:
        from scipy.spatial import cKDTree  # local import: only point data needs SciPy

        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2:
            raise ValueError("points must have shape (n, d)")
        n = pts.shape[0]
        if not 1 <= k < n:
            raise ValueError(f"need 1 <= k < n, got k={k}, n={n}")
        if not np.isfinite(pts).all():
            raise ValueError("points must be finite")
        _, idx = cKDTree(pts).query(pts, k=k + 1)
        not_self = idx != np.arange(n)[:, None]
        if (not_self.sum(axis=1) != k).any():
            # Self is missing from its own k+1 list only if > k exact duplicates exist.
            raise ValueError("more than k duplicate points; deduplicate the input first")
        self.k = int(k)
        self.neighbors: NDArray[np.intp] = idx[not_self].reshape(n, k).astype(np.intp)

    @property
    def num_samples(self) -> int:
        return int(self.neighbors.shape[0])

    def edge_blocks(self) -> Iterator[EdgeBlock]:
        src = np.arange(self.num_samples, dtype=np.intp)
        for t in range(self.k):
            yield src, self.neighbors[:, t]

"""Approximate Morse-Smale complex by steepest ascent (Correa et al. 2011, Sec. 3.4).

1. Every sample points to its highest neighbour if that neighbour is higher; samples
   with no higher neighbour are maxima. Following the pointers gives each sample's
   region (the descending manifold D(u) of its maximum u).
2. For every pair of neighbouring regions, the highest edge between them gives a
   saddle: "the highest shared point between descending manifolds must be an
   (n-1)-saddle". The edge's height is min(f(i), f(j)) - the level at which the two
   regions first touch - and its lower endpoint is the saddle sample.

Steps 1 and 2 are separate blocks (DECISIONS.md D-004): any region labelling can be
paired with any saddle method, and every saddle method hands a `SaddleSet` to the one
`assemble_flow`, so the graph is always built the same way.

Ties: all comparisons use the strict total order (f, sample index) ("simulation of
simplicity"), so plateaus never create ambiguous maxima or saddles.

Cost: O(E) for ascent and boundary scan, plus O(n log L) pointer jumping where L is
the longest ascent path. Memory O(n) plus one edge block at a time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from topospine.core.graph import GradientFlowGraph, NodeKind
from topospine.core.neighborhoods import Neighborhood


@dataclass(frozen=True, eq=False)
class FlowDecomposition:
    """Output of `decompose`.

    graph  : gradient flow graph; maxima are nodes 0..M-1 (in increasing sample
             index), saddles are nodes M..M+S-1.
    labels : (n,) node id of the maximum whose region each sample belongs to.
             Region ids == maximum node ids, so labels index straight into
             persistence arrays and fit in uint16 for the browser when M < 65536.
    """

    graph: GradientFlowGraph
    labels: NDArray[np.int64]


@dataclass(frozen=True, eq=False)
class SaddleSet:
    """What a saddle method finds, before the saddles become graph nodes.

    samples : (S,) sample index of each saddle.
    pairs   : (S, 2) the two region ids each saddle joins. Both may be equal (a loop),
              and several saddles may join the same pair: exact Morse-Smale complexes
              produce both; our boundary rule produces neither.
    """

    samples: NDArray[np.int64]
    pairs: NDArray[np.int64]

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.int64)
        pairs = np.asarray(self.pairs, dtype=np.int64)
        if pairs.size == 0:
            pairs = pairs.reshape(0, 2)
        if samples.ndim != 1 or pairs.ndim != 2 or pairs.shape != (samples.size, 2):
            raise ValueError("a SaddleSet needs samples (S,) and pairs (S, 2)")
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "pairs", pairs)


def sample_ranks(values: NDArray[np.floating]) -> NDArray[np.int64]:
    """Position of each sample in the order (f, index): a permutation of 0..n-1."""
    v = np.asarray(values, dtype=np.float64).ravel()
    if not np.isfinite(v).all():
        raise ValueError("values must be finite (mask or fill NaNs before decomposing)")
    order = np.argsort(v, kind="stable")  # stable => equal f ordered by index
    ranks = np.empty(v.size, dtype=np.int64)
    ranks[order] = np.arange(v.size, dtype=np.int64)
    return ranks


def steepest_ascent(ranks: NDArray[np.int64], neighborhood: Neighborhood) -> NDArray[np.int64]:
    """For each sample, its highest neighbour if higher than itself, else itself."""
    n = ranks.size
    if neighborhood.num_samples != n:
        raise ValueError("neighbourhood and values disagree on the number of samples")
    best = ranks.copy()  # start with "myself"; any higher neighbour replaces it
    for src, dst in neighborhood.edge_blocks():
        # ufunc.at handles repeated indices (kNN reverse direction) correctly.
        np.maximum.at(best, src, ranks[dst])
        np.maximum.at(best, dst, ranks[src])
    sample_at_rank = np.argsort(ranks)
    return sample_at_rank[best]


def _follow_to_roots(ascent: NDArray[np.int64]) -> NDArray[np.int64]:
    """Pointer jumping: each pass doubles the distance travelled, so O(log L) passes."""
    root = ascent.copy()
    while True:
        nxt = root[root]
        if np.array_equal(nxt, root):
            return root
        root = nxt


def _max_per_key(keys: NDArray[np.int64], vals: NDArray[np.int64]) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Keep the largest value for every distinct key."""
    order = np.lexsort((vals, keys))  # by key, then value ascending
    keys, vals = keys[order], vals[order]
    last = np.r_[keys[1:] != keys[:-1], True]
    return keys[last], vals[last]


def regions_by_ascent(ranks: NDArray[np.int64], neighborhood: Neighborhood) -> NDArray[np.int64]:
    """Region id per sample; regions are numbered by increasing sample index of their maximum."""
    n = ranks.size
    ascent = steepest_ascent(ranks, neighborhood)
    roots = _follow_to_roots(ascent)
    max_samples = np.flatnonzero(ascent == np.arange(n))
    region_of_max = np.full(n, -1, dtype=np.int64)
    region_of_max[max_samples] = np.arange(max_samples.size)
    return region_of_max[roots]


def _region_count(labels: NDArray[np.int64], n: int) -> int:
    """M for labels 0..M-1; rejects gaps, negatives and a wrong length."""
    if labels.shape != (n,):
        raise ValueError("one label per sample required")
    m = int(labels.max()) + 1 if labels.size else 0
    if labels.size and (labels.min() < 0 or np.bincount(labels, minlength=m).min() == 0):
        raise ValueError("labels must be 0..M-1 with every region non-empty")
    return m


def _sample_at_rank(ranks: NDArray[np.int64]) -> NDArray[np.int64]:
    """Inverse permutation of ranks, in O(n) (no sort needed).

    Only valid for a permutation of 0..n-1: a repeated rank would be overwritten and a
    missing one left as uninitialised memory, both silently. Callers may pass their own
    ranks, so this is checked (O(n), cheap next to the sort that made them; D-008).
    """
    n = ranks.size
    if n and (ranks.min() < 0 or ranks.max() >= n or np.bincount(ranks, minlength=n).max() != 1):
        raise ValueError("ranks must be a permutation of 0..n-1 (as made by sample_ranks)")
    out = np.empty_like(ranks)
    out[ranks] = np.arange(ranks.size, dtype=np.int64)
    return out


def boundary_saddles(
    ranks: NDArray[np.int64], labels: NDArray[np.integer], neighborhood: Neighborhood
) -> SaddleSet:
    """Our saddle rule (Sec. 3.4): one saddle per pair of touching regions, at the lower
    endpoint of their highest boundary edge (DEVIATIONS.md #2).

    Saddles come out ordered by region pair (a, b) with a < b.
    """
    labels = np.asarray(labels, dtype=np.int64).ravel()
    m = _region_count(labels, ranks.size)

    # Highest boundary edge per region pair, reduced block by block to bound memory.
    acc_keys = np.empty(0, dtype=np.int64)
    acc_rank = np.empty(0, dtype=np.int64)
    for src, dst in neighborhood.edge_blocks():
        la, lb = labels[src], labels[dst]
        cross = la != lb
        if not cross.any():
            continue
        a = np.minimum(la[cross], lb[cross])
        b = np.maximum(la[cross], lb[cross])
        edge_rank = np.minimum(ranks[src[cross]], ranks[dst[cross]])
        acc_keys, acc_rank = _max_per_key(
            np.concatenate([acc_keys, a * m + b]), np.concatenate([acc_rank, edge_rank])
        )

    pairs = np.stack([acc_keys // max(m, 1), acc_keys % max(m, 1)], axis=1)
    return SaddleSet(samples=_sample_at_rank(ranks)[acc_rank], pairs=pairs)


def assemble_flow(
    values: NDArray[np.floating],
    labels: NDArray[np.integer],
    saddles: SaddleSet,
    ranks: NDArray[np.int64] | None = None,
) -> FlowDecomposition:
    """Regions + saddles -> G. The one place the graph is built, whatever the methods.

    labels must be 0..M-1 with every id used. Region r becomes maximum node r, placed at
    the region's highest sample; saddle i becomes node M+i with arcs to its two regions.
    Pass `ranks` if you already have them, to skip a sort.
    """
    v = np.asarray(values, dtype=np.float64).ravel()
    labels = np.asarray(labels, dtype=np.int64).ravel()
    m = _region_count(labels, v.size)
    if ranks is None:
        ranks = sample_ranks(v)
    elif np.shape(ranks) != v.shape:
        raise ValueError("one rank per sample required")
    s = saddles.samples.size
    if s and (saddles.pairs.min() < 0 or saddles.pairs.max() >= m):
        raise ValueError("a saddle refers to a region that doesn't exist")
    if s and (saddles.samples.min() < 0 or saddles.samples.max() >= v.size):
        raise ValueError("a saddle sample index is out of range")

    top_rank = np.full(m, -1, dtype=np.int64)
    np.maximum.at(top_rank, labels, ranks)
    max_samples = _sample_at_rank(ranks)[top_rank]

    saddle_nodes = np.arange(m, m + s, dtype=np.int64)
    kinds = np.r_[np.full(m, NodeKind.MAXIMUM), np.full(s, NodeKind.SADDLE)]
    samples = np.r_[max_samples, saddles.samples].astype(np.int64)
    arcs = np.empty((2 * s, 2), dtype=np.int64)
    arcs[0::2, 0] = saddle_nodes
    arcs[0::2, 1] = saddles.pairs[:, 0]
    arcs[1::2, 0] = saddle_nodes
    arcs[1::2, 1] = saddles.pairs[:, 1]

    graph = GradientFlowGraph(kinds=kinds, values=v[samples], samples=samples, arcs=arcs)
    return FlowDecomposition(graph=graph, labels=labels)


def graph_from_regions(
    values: NDArray[np.floating], labels: NDArray[np.integer], neighborhood: Neighborhood
) -> FlowDecomposition:
    """Build G from any region labelling (ours, or TTK's) with our boundary saddles."""
    ranks = sample_ranks(values)
    return assemble_flow(values, labels, boundary_saddles(ranks, labels, neighborhood), ranks)


def decompose(values: NDArray[np.floating], neighborhood: Neighborhood) -> FlowDecomposition:
    """Steepest-ascent regions + boundary saddles -> gradient flow graph (Sec. 3.4)."""
    if neighborhood.num_samples != np.size(values):
        raise ValueError("neighbourhood and values disagree on the number of samples")
    labels = regions_by_ascent(sample_ranks(values), neighborhood)
    return graph_from_regions(values, labels, neighborhood)

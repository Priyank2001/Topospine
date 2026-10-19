"""Approximate Morse-Smale complex by steepest ascent (Correa et al. 2011, Sec. 3.4).

1. Every sample points to its highest neighbour if that neighbour is higher; samples
   with no higher neighbour are maxima. Following the pointers gives each sample's
   region (the descending manifold D(u) of its maximum u).
2. For every pair of neighbouring regions, the highest edge between them gives a
   saddle: "the highest shared point between descending manifolds must be an
   (n-1)-saddle". The edge's height is min(f(i), f(j)) - the level at which the two
   regions first touch - and its lower endpoint is the saddle sample.

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


def graph_from_regions(
    values: NDArray[np.floating], labels: NDArray[np.integer], neighborhood: Neighborhood
) -> FlowDecomposition:
    """Build G from any region labelling (ours, or TTK's descending manifolds).

    labels must be 0..M-1 with every id used. Region r becomes maximum node r, placed at
    the region's highest sample; saddles come from the highest boundary edge per pair.
    """
    v = np.asarray(values, dtype=np.float64).ravel()
    labels = np.asarray(labels, dtype=np.int64).ravel()
    if labels.shape != v.shape:
        raise ValueError("one label per sample required")
    ranks = sample_ranks(v)
    sample_at_rank = np.argsort(ranks)
    m = int(labels.max()) + 1 if labels.size else 0
    if labels.size and (labels.min() < 0 or np.bincount(labels, minlength=m).min() == 0):
        raise ValueError("labels must be 0..M-1 with every region non-empty")

    top_rank = np.full(m, -1, dtype=np.int64)
    np.maximum.at(top_rank, labels, ranks)
    max_samples = sample_at_rank[top_rank]

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

    s = acc_keys.size
    pair_a, pair_b = acc_keys // max(m, 1), acc_keys % max(m, 1)
    saddle_samples = sample_at_rank[acc_rank]
    saddle_nodes = np.arange(m, m + s, dtype=np.int64)

    kinds = np.r_[np.full(m, NodeKind.MAXIMUM), np.full(s, NodeKind.SADDLE)]
    samples = np.r_[max_samples, saddle_samples].astype(np.int64)
    arcs = np.empty((2 * s, 2), dtype=np.int64)
    arcs[0::2, 0] = saddle_nodes
    arcs[0::2, 1] = pair_a
    arcs[1::2, 0] = saddle_nodes
    arcs[1::2, 1] = pair_b

    graph = GradientFlowGraph(kinds=kinds, values=v[samples], samples=samples, arcs=arcs)
    return FlowDecomposition(graph=graph, labels=labels)


def decompose(values: NDArray[np.floating], neighborhood: Neighborhood) -> FlowDecomposition:
    """Steepest-ascent regions + boundary saddles -> gradient flow graph (Sec. 3.4)."""
    if neighborhood.num_samples != np.size(values):
        raise ValueError("neighbourhood and values disagree on the number of samples")
    labels = regions_by_ascent(sample_ranks(values), neighborhood)
    return graph_from_regions(values, labels, neighborhood)

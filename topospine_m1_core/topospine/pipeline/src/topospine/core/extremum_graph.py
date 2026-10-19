"""Extremum graph G_R for a threshold range R = [p_lo, p_hi] (Correa et al. 2011, Eqs. 1-3).

    maximum u kept  <=>  R n [0, P(u)]       != {}   <=>  p_lo <= P(u)
    saddle s kept   <=>  R n [P(s), P(s)]    != {}   <=>  p_lo <= P(s) <= p_hi
    arc (s, u) kept <=>  R n [P(s), P*(s)]   != {}   <=>  P(s) <= p_hi  and  P*(s) >= p_lo

p_lo is the noise threshold (removes small peaks); p_hi the variation threshold
(cuts connections through high-persistence saddles). The inequality symbols were
lost in the PDF text we work from; the reconstruction above is logged in
docs/DEVIATIONS.md and checked against the paper's examples in the tests.

This module is the Python reference. The browser re-implements the same three
inequalities in TypeScript; both are tested on the same worked example.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from topospine.core.graph import GradientFlowGraph, NodeKind
from topospine.core.persistence import Persistence


@dataclass(frozen=True, eq=False)
class ThresholdedGraph:
    node_mask: NDArray[np.bool_]   # (N,)
    arc_mask: NDArray[np.bool_]    # (A,)
    p_lo: float
    p_hi: float


def _check_range(p_lo: float, p_hi: float) -> None:
    if not (0.0 <= p_lo <= p_hi):
        raise ValueError(f"need 0 <= p_lo <= p_hi, got [{p_lo}, {p_hi}]")


def filter_graph(graph: GradientFlowGraph, pers: Persistence, p_lo: float, p_hi: float = np.inf) -> ThresholdedGraph:
    _check_range(p_lo, p_hi)
    P, Psat = pers.persistence, pers.saturated
    is_max = graph.kinds == NodeKind.MAXIMUM
    node_mask = np.where(is_max, P >= p_lo, (P >= p_lo) & (P <= p_hi))
    s = graph.arcs[:, 0]
    arc_mask = (P[s] <= p_hi) & (Psat[s] >= p_lo)
    return ThresholdedGraph(node_mask=node_mask, arc_mask=arc_mask, p_lo=float(p_lo), p_hi=float(p_hi))


def representatives(pers: Persistence, p_lo: float) -> NDArray[np.int64]:
    """For each node, the surviving maximum it belongs to at noise threshold p_lo.

    Follows merged_into while the current maximum was cancelled below p_lo.
    Saddles map to themselves. Per-sample regions at p_lo: representatives(...)[labels].
    """
    if p_lo < 0:
        raise ValueError("p_lo must be non-negative")
    n = pers.persistence.size
    cancelled = (pers.merged_into >= 0) & (pers.persistence < p_lo)
    rep = np.arange(n, dtype=np.int64)
    while True:  # pointer jumping on a forest; merges point to higher-persistence maxima
        nxt = np.where(cancelled[rep], pers.merged_into[rep], rep)
        if np.array_equal(nxt, rep):
            return rep
        rep = nxt


def extrema_curve(graph: GradientFlowGraph, pers: Persistence, thresholds: NDArray[np.floating]) -> NDArray[np.int64]:
    """Number of maxima kept for each noise threshold p_lo (the paper's blue curve)."""
    p = np.sort(pers.persistence[graph.maxima])
    t = np.asarray(thresholds, dtype=np.float64)
    return (p.size - np.searchsorted(p, t, side="left")).astype(np.int64)


def arc_curve(graph: GradientFlowGraph, pers: Persistence, thresholds: NDArray[np.floating]) -> NDArray[np.int64]:
    """Number of arcs kept for each variation threshold p_hi at p_lo = 0 (red curve)."""
    p = np.sort(pers.persistence[graph.arcs[:, 0]])
    t = np.asarray(thresholds, dtype=np.float64)
    return np.searchsorted(p, t, side="right").astype(np.int64)

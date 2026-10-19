"""Algorithm 1 of Correa et al. 2011: persistence P and saturated persistence P*.

Input : gradient flow graph G (arcs saddle -> maximum).
Output: P(node) for maxima and saddles, P*(saddle), and for every cancelled maximum
        the maximum it merged into.

Mechanics
---------
Arcs get a direction flag. Initially every arc points saddle -> maximum, so a live
maximum has no outgoing arc and an unprocessed saddle has two. Cancelling saddle s
with maximum u_hat reverses every arc on the path s -> u -> ... -> u_hat. Afterwards
u_hat (and every maximum on that path) has exactly one outgoing arc, and every
processed saddle exactly one, so following outgoing arcs from any cancelled maximum
leads uniquely to a live one: the paper's "redirect flow from u_hat to v_hat".

PATH(G, s, u) is `_ReversibleFlow.path`, REVERSE(G, P) is `_ReversibleFlow.cancel`.

Lazy priority queue: a saddle's persistence can only grow as maxima around it are
cancelled (its paths then end at higher survivors). Queue keys are therefore lower
bounds; a popped saddle is recomputed and re-inserted unless it is still the
smallest. This makes the finalised p values non-decreasing, which is why the P*
update below (a running max) equals the paper's plain assignment.

Cost: O(S log S) queue work with near-constant union-find lookups, plus one full
traversal of both paths per saddle at finalisation (O(S * L), L = average path
length). L grows with how much has already been simplified, so very noisy inputs
(hundreds of thousands of saddles) are the slow case; see the benchmark notes.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from topospine.core.graph import GradientFlowGraph


@dataclass(frozen=True, eq=False)
class Persistence:
    """persistence : (N,) P; +inf for maxima never cancelled (e.g. the global max).
    saturated   : (N,) P* for saddles; NaN for maxima.
    merged_into : (N,) node id of the maximum a cancelled maximum merged into at
                  cancellation time, else -1.
    """

    persistence: NDArray[np.float64]
    saturated: NDArray[np.float64]
    merged_into: NDArray[np.int64]
    saturated_cancel: NDArray[np.float64] | None = None


@dataclass
class _Path:
    terminal: int          # live maximum reached (u_hat)
    saddles: list[int]     # s, then every processed saddle passed through
    arcs: list[int]        # arc ids in traversal order
    maxima: list[int]      # u, ..., u_hat (maxima[k] was reached via arcs[2k])


class _ReversibleFlow:
    """Arc directions plus a union-find over maxima.

    The union-find answers "which live maximum does u flow to?" in near O(1): after
    cancelling u_hat into v_hat every path from u_hat ends at v_hat, so the terminal
    of a path equals the merge-forest root of its first maximum. The lazy queue only
    needs terminals, so full PATH traversal (needed for P* and REVERSE) runs once
    per saddle, at finalisation.

    State lives in Python lists, not NumPy arrays: this loop does millions of
    scalar reads, and list indexing is several times faster than ndarray indexing.
    """

    def __init__(self, graph: GradientFlowGraph) -> None:
        self._arc_saddle: list[int] = graph.arcs[:, 0].tolist()
        self._arc_max: list[int] = graph.arcs[:, 1].tolist()
        self._saddle_arcs: list[list[int]] = graph.saddle_arcs.tolist()
        self._forward: list[bool] = [True] * graph.num_arcs      # True: saddle -> max
        self._max_out: list[int] = [-1] * graph.num_nodes          # reversed arc leaving a max
        self._root: list[int] = list(range(graph.num_nodes))        # union-find over maxima
        self._step_limit = graph.num_arcs + 1

    def first_max(self, arc: int) -> int:
        return self._arc_max[arc]

    def terminal(self, m: int) -> int:
        root = self._root
        while root[m] != m:
            root[m] = root[root[m]]  # path halving
            m = root[m]
        return m

    def path(self, start_arc: int) -> _Path:
        s = self._arc_saddle[start_arc]
        node = self._arc_max[start_arc]
        p = _Path(terminal=node, saddles=[s], arcs=[start_arc], maxima=[node])
        for _ in range(self._step_limit):
            arc_in = self._max_out[node]
            if arc_in < 0:
                p.terminal = node
                return p
            saddle = self._arc_saddle[arc_in]
            arc_out = self._forward_arc(saddle)
            node = self._arc_max[arc_out]
            p.saddles.append(saddle)
            p.arcs += (arc_in, arc_out)
            p.maxima.append(node)
        raise RuntimeError("flow path did not terminate; graph state is corrupt")

    def _forward_arc(self, saddle: int) -> int:
        a0, a1 = self._saddle_arcs[saddle]
        f0, f1 = self._forward[a0], self._forward[a1]
        if f0 == f1:
            raise RuntimeError("a processed saddle must have exactly one forward arc")
        return a0 if f0 else a1

    def cancel(self, p: _Path, survivor: int) -> None:
        """REVERSE(G, p) and record that p.terminal now flows to `survivor`."""
        fwd = self._forward
        for a in p.arcs:
            fwd[a] = not fwd[a]
        for k, m in enumerate(p.maxima):
            self._max_out[m] = p.arcs[2 * k]  # now flows back along the arc it was reached by
        self._root[p.terminal] = survivor


def compute_persistence(graph: GradientFlowGraph) -> Persistence:
    n = graph.num_nodes
    f: list[float] = graph.values.tolist()
    pers = [np.inf] * n
    sat = [np.nan] * n
    sat_cancel = [np.nan] * n
    for s in graph.saddles.tolist():
        sat[s] = -np.inf
        sat_cancel[s] = -np.inf
    merged = [-1] * n
    order_key = list(zip(f, graph.samples.tolist(), range(n)))  # same order as graph.precedes

    flow = _ReversibleFlow(graph)
    saddle_arcs = graph.saddle_arcs.tolist()

    def current_persistence(s: int) -> tuple[float, int, int]:
        a_u, a_v = saddle_arcs[s]
        u_hat = flow.terminal(flow.first_max(a_u))
        v_hat = flow.terminal(flow.first_max(a_v))
        return min(abs(f[u_hat] - f[s]), abs(f[v_hat] - f[s])), u_hat, v_hat

    # Seeding with the exact initial persistence (instead of the paper's 0) is an
    # equivalent but cheaper start: it is still a valid lower bound.
    queue: list[tuple[float, int]] = [(current_persistence(s)[0], s) for s in graph.saddles.tolist()]
    heapq.heapify(queue)  # ties broken by node id => deterministic

    while queue:
        _, s = heapq.heappop(queue)
        p, u_hat, v_hat = current_persistence(s)
        if queue and p > queue[0][0]:          # no longer the lowest: lazy re-insert
            heapq.heappush(queue, (p, s))
            continue

        a_u, a_v = saddle_arcs[s]
        U, V = flow.path(a_u), flow.path(a_v)
        assert U.terminal == u_hat and V.terminal == v_hat  # union-find agrees with PATH

        pers[s] = p
        for t in U.saddles:                    # P*(SADDLES(U u V)) <- p
            if p > sat[t]:
                sat[t] = p
        for t in V.saddles:
            if p > sat[t]:
                sat[t] = p
        if p > sat_cancel[s]:
            sat_cancel[s] = p
        if u_hat != v_hat:                     # otherwise: cycle, saddle only removed
            # For maxima, |f(u)-f(s)| < |f(v)-f(s)| <=> f(u) < f(v); the order key adds
            # the (sample, id) tie-break so equal heights still cancel deterministically.
            if order_key[u_hat] < order_key[v_hat]:
                lower, upper, path = u_hat, v_hat, U
            else:
                lower, upper, path = v_hat, u_hat, V
            pers[lower] = p
            merged[lower] = upper
            for t in U.saddles + V.saddles:    # cancellation-only variant of P*
                if p > sat_cancel[t]:
                    sat_cancel[t] = p
            flow.cancel(path, upper)

    return Persistence(
        persistence=np.asarray(pers, dtype=np.float64),
        saturated=np.asarray(sat, dtype=np.float64),
        merged_into=np.asarray(merged, dtype=np.int64),
        saturated_cancel=np.asarray(sat_cancel, dtype=np.float64),
    )

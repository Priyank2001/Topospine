"""The directed gradient flow graph G = (N, E) of Correa et al. 2011, Sec. 3.4.

Every extremum-graph source (our steepest ascent on a grid or kNN graph, the TTK
adapter, the TACHYON adapter) produces this one structure, so Algorithm 1
(persistence.py) is written exactly once.

Conventions
-----------
* This is the graph for MAXIMA. The minimum graph is obtained by running the same
  pipeline on -f; no second code path exists.
* Nodes are maxima or saddles. Arcs always point saddle -> maximum and every saddle
  has exactly two arcs (the two regions it separates). Both arcs may end at the
  same maximum (a loop); our approximation never creates one, but exact Morse-Smale
  complexes from TTK can, and Algorithm 1 handles it.
* Nodes refer to the dataset only through `samples` (an index into the flattened
  sample array). Coordinates live with the dataset, not here, so the core never
  depends on whether the domain is a 3D grid or an 8-D point cloud.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from functools import cached_property

import numpy as np
from numpy.typing import NDArray


class NodeKind(IntEnum):
    MAXIMUM = 0
    SADDLE = 1


def _frozen(array: NDArray, dtype: type) -> NDArray:
    """Copy into the canonical dtype and make read-only, so a graph can't be mutated
    behind Algorithm 1's back."""
    out = np.array(array, dtype=dtype, copy=True)
    out.setflags(write=False)
    return out


@dataclass(frozen=True, eq=False)
class GradientFlowGraph:
    """Immutable gradient flow graph.

    Attributes
    ----------
    kinds   : (N,) int8   NodeKind per node.
    values  : (N,) float  f at the node.
    samples : (N,) int64  index of the node's sample in the flattened dataset.
    arcs    : (A, 2) int64, rows are (saddle_node, maximum_node).
    """

    kinds: NDArray[np.int8]
    values: NDArray[np.float64]
    samples: NDArray[np.int64]
    arcs: NDArray[np.int64]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kinds", _frozen(self.kinds, np.int8))
        object.__setattr__(self, "values", _frozen(self.values, np.float64))
        object.__setattr__(self, "samples", _frozen(self.samples, np.int64))
        arcs = np.asarray(self.arcs, dtype=np.int64)
        if arcs.size == 0:
            arcs = arcs.reshape(0, 2)
        object.__setattr__(self, "arcs", _frozen(arcs, np.int64))
        self._validate()

    # ------------------------------------------------------------------ checks
    def _validate(self) -> None:
        n = self.kinds.shape[0]
        if self.kinds.ndim != 1 or self.values.shape != (n,) or self.samples.shape != (n,):
            raise ValueError("kinds, values and samples must be 1-D arrays of equal length")
        if self.arcs.ndim != 2 or self.arcs.shape[1] != 2:
            raise ValueError("arcs must have shape (A, 2)")
        if not np.isin(self.kinds, (NodeKind.MAXIMUM, NodeKind.SADDLE)).all():
            raise ValueError("unknown node kind")
        if not np.isfinite(self.values).all():
            raise ValueError("node values must be finite")
        if (self.samples < 0).any():
            raise ValueError("sample indices must be non-negative")
        if self.arcs.size == 0:
            if (self.kinds == NodeKind.SADDLE).any():
                raise ValueError("every saddle needs exactly two arcs")
            return
        if self.arcs.min() < 0 or self.arcs.max() >= n:
            raise ValueError("arc endpoint out of range")
        s, m = self.arcs[:, 0], self.arcs[:, 1]
        if (self.kinds[s] != NodeKind.SADDLE).any():
            raise ValueError("arcs must start at a saddle")
        if (self.kinds[m] != NodeKind.MAXIMUM).any():
            raise ValueError("arcs must end at a maximum")
        arcs_per_node = np.bincount(s, minlength=n)
        if (arcs_per_node[self.kinds == NodeKind.SADDLE] != 2).any():
            raise ValueError("every saddle needs exactly two arcs")
        # Gradient flow goes uphill, so a saddle can't be above a maximum it flows to.
        if (self.values[s] > self.values[m]).any():
            raise ValueError("a saddle lies above a maximum it is connected to")

    # ------------------------------------------------------------- properties
    @property
    def num_nodes(self) -> int:
        return int(self.kinds.shape[0])

    @property
    def num_arcs(self) -> int:
        return int(self.arcs.shape[0])

    @cached_property
    def maxima(self) -> NDArray[np.int64]:
        return np.flatnonzero(self.kinds == NodeKind.MAXIMUM).astype(np.int64)

    @cached_property
    def saddles(self) -> NDArray[np.int64]:
        return np.flatnonzero(self.kinds == NodeKind.SADDLE).astype(np.int64)

    @cached_property
    def saddle_arcs(self) -> NDArray[np.int64]:
        """(N, 2) arc ids of each saddle's two arcs; rows of maxima are -1."""
        out = np.full((self.num_nodes, 2), -1, dtype=np.int64)
        if self.num_arcs:
            order = np.argsort(self.arcs[:, 0], kind="stable")
            out[self.arcs[order[0::2], 0], 0] = order[0::2]
            out[self.arcs[order[1::2], 0], 1] = order[1::2]
        out.setflags(write=False)
        return out

    def precedes(self, a: int, b: int) -> bool:
        """Strict total order on nodes: by value, then sample index, then node id.

        Same "simulation of simplicity" tie-break as gradient_flow.sample_ranks, so
        equal values never make a cancellation ambiguous.
        """
        ka = (self.values[a], self.samples[a], a)
        kb = (self.values[b], self.samples[b], b)
        return ka < kb

"""What TTK's Morse-Smale output means: maxima and saddles, read from MorseSmaleOutput.

This is the one place that knows TTK's output layout (it changes between releases).
Layout of TTK 1.3.0, checked by tests/sources/test_ttk_blocks.py (slow):
    critical points : CellDimension, CellId, ttkVertexScalarField (= our sample index)
    separatrices    : SourceId, DestinationId (CellIds), SeparatrixId, SeparatrixType

    - Ports are found by the arrays they hold, not by number; names can be overridden.
    - TTK's dimension d = the highest CellDimension (the global maximum is a d-cell).
    - Uphill separatrix (saddle -> maximum) = SeparatrixType d-1, from a (d-1)-cell to a
      d-cell. CellIds are numbered per dimension, so lookups are per dimension.
    - Separatrices are grouped per saddle CELL: two critical cells can share their highest
      vertex, so one sample may carry two saddles.
    - Two uphill separatrices -> one saddle (a loop if both reach the same peak).
      Fewer (a path ran off the domain border) -> dropped (D-009, DEVIATIONS.md #17).
      More (a degenerate saddle) -> error (D-010).

Pure NumPy on already-converted arrays: no TTK or VTK import here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from topospine.core.gradient_flow import SaddleSet
from topospine.sources.ttk_backend import MorseSmaleOutput


@dataclass(frozen=True)
class TtkArrayNames:
    """TTK's array names, overridable in case a release renames them."""

    dimension: str = "CellDimension"
    cell_id: str = "CellId"
    vertex: str = "ttkVertexScalarField"
    source: str = "SourceId"
    destination: str = "DestinationId"
    separatrix: str = "SeparatrixId"
    separatrix_type: str = "SeparatrixType"

    @property
    def critical_points(self) -> tuple[str, ...]:
        return (self.dimension, self.cell_id, self.vertex)

    @property
    def separatrices(self) -> tuple[str, ...]:
        return (self.source, self.destination, self.separatrix, self.separatrix_type)


def _port_with(out: MorseSmaleOutput, kind: str, names: Sequence[str]) -> Mapping[str, NDArray]:
    for port in out.ports:
        arrays: Mapping[str, NDArray] = getattr(port, kind)
        if all(n in arrays for n in names):
            return arrays
    raise RuntimeError(f"no TTK output port has {kind} arrays {list(names)}; "
                       "check the names in your TTK version and pass `arrays`.")


def _vertices(cp: Mapping[str, NDArray], names: TtkArrayNames, dim: int,
              ids: NDArray[np.int64], what: str) -> NDArray[np.int64]:
    """Sample index of each critical `dim`-cell in `ids` (CellIds are per dimension)."""
    mask = cp[names.dimension] == dim
    cell_ids = cp[names.cell_id][mask].astype(np.int64)
    order = np.argsort(cell_ids)
    sorted_ids, verts = cell_ids[order], cp[names.vertex][mask].astype(np.int64)[order]
    pos = np.minimum(np.searchsorted(sorted_ids, ids), max(sorted_ids.size - 1, 0))
    found = (sorted_ids[pos] == ids) if sorted_ids.size else np.zeros(ids.size, dtype=bool)
    if not found.all():
        raise RuntimeError(f"a separatrix refers to {what} cell {int(ids[~found][0])}, "
                           "which is not among TTK's critical points")
    return verts[pos]


def ttk_maxima(out: MorseSmaleOutput, names: TtkArrayNames = TtkArrayNames()) -> NDArray[np.int64]:
    """Sample index of every maximum TTK found (its d-cells)."""
    cp = _port_with(out, "point", names.critical_points)
    dims = cp[names.dimension]
    return cp[names.vertex][dims == dims.max()].astype(np.int64)


def ttk_saddles(out: MorseSmaleOutput, labels: NDArray[np.int64],
                names: TtkArrayNames = TtkArrayNames()) -> tuple[SaddleSet, int]:
    """TTK's saddles joining maxima (increasing sample order), and how many were dropped."""
    cp = _port_with(out, "point", names.critical_points)
    sep = _port_with(out, "cell", names.separatrices)
    d = int(cp[names.dimension].max())
    _, first = np.unique(sep[names.separatrix], return_index=True)    # one row per separatrix
    up = first[sep[names.separatrix_type][first] == d - 1]
    saddle_cell = sep[names.source][up].astype(np.int64)
    peak_v = _vertices(cp, names, d, sep[names.destination][up].astype(np.int64), "maximum")

    order = np.lexsort((peak_v, saddle_cell))
    saddle_cell, peak_v = saddle_cell[order], peak_v[order]
    cells, start, count = np.unique(saddle_cell, return_index=True, return_counts=True)
    samples = _vertices(cp, names, d - 1, cells, "saddle")
    if (count > 2).any():
        i = int(np.argmax(count > 2))
        raise ValueError(f"degenerate saddle (cell {int(cells[i])}, sample {int(samples[i])}) has "
                         f"{int(count[i])} uphill separatrices; not supported (docs/DECISIONS.md D-010)")
    keep = count == 2
    pairs = np.sort(np.stack([labels[peak_v[start[keep]]], labels[peak_v[start[keep] + 1]]], axis=1), axis=1)
    by_sample = np.argsort(samples[keep], kind="stable")
    dropped = int((cp[names.dimension] == d - 1).sum()) - int(keep.sum())
    return SaddleSet(samples[keep][by_sample].astype(np.int64), pairs[by_sample].astype(np.int64)), dropped

"""Optional noise cut before extraction: TTK's persistence simplification (D-014, D-015).

    work field ─► TtkSimplifier.simplify ─► simplified field ─► (every) region + saddle method

ttkTopologicalSimplificationByPersistence removes every maximum whose persistence is below
the threshold by flattening it down to its saddle, so noise peaks and their saddles never
reach extraction. Every method then sees the same simplified field (D-015).

Two settings found by experiment (temp/evidence/simplify_precheck.py), not options:
    - pair type 2 = maximum-saddle pairs only. The pipeline always computes a MAXIMUM graph
      (a minimum graph negates the field first), so only maxima are noise to remove.
    - perturbation ON. Flattening creates plateaus; without TTK's tiny perturbation the
      plateaus break ties differently downstream and spurious maxima come back
      (noisy 3-D at 2 %: 83 maxima instead of 26).

What this does NOT do: decide which field is exported or recorded (run.py), or work on
point data (TTK simplifies meshes; points have none).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from topospine.core.datasets import Dataset, GridDataset
from topospine.core.gradient_flow import sample_ranks, steepest_ascent
from topospine.core.neighborhoods import FreudenthalNeighborhood
from topospine.sources.ttk_backend import SCALAR_NAME, import_ttk, numpy_to_image

MAXIMUM_SADDLE_PAIRS = 2        # ttkTopologicalSimplificationByPersistence::PairType

# (values, spacing, origin, threshold, absolute) -> simplified values, same shape
Runner = Callable[[NDArray[np.float64], Sequence[float], Sequence[float], float, bool], NDArray[np.float64]]


def run_ttk_simplification(values: NDArray[np.float64], spacing: Sequence[float], origin: Sequence[float],
                           threshold: float, absolute: bool) -> NDArray[np.float64]:
    from vtkmodules.util.numpy_support import vtk_to_numpy

    f = import_ttk().ttkTopologicalSimplificationByPersistence()
    f.SetInputDataObject(numpy_to_image(values, spacing, origin))
    f.SetInputArrayToProcess(0, 0, 0, 0, SCALAR_NAME)
    f.SetPersistenceThreshold(float(threshold))
    f.SetThresholdIsAbsolute(bool(absolute))
    f.SetPairType(MAXIMUM_SADDLE_PAIRS)
    f.SetComputePerturbation(True)
    f.Update()
    out = f.GetOutputDataObject(0).GetPointData().GetArray(SCALAR_NAME)
    if out is None:
        raise RuntimeError(f"TTK simplification returned no array {SCALAR_NAME!r}")
    return np.array(vtk_to_numpy(out), dtype=np.float64).reshape(np.shape(values))


def count_maxima_on_ttk_mesh(values: NDArray[np.floating]) -> int:
    """Local maxima on TTK's grid mesh, i.e. the maxima TTK's simplification acts on."""
    nb = FreudenthalNeighborhood(np.shape(values))
    return int((steepest_ascent(sample_ranks(values), nb) == np.arange(np.size(values))).sum())


class TtkSimplifier:
    def __init__(self, threshold: float, absolute: bool = False,
                 runner: Runner = run_ttk_simplification) -> None:
        """threshold: a fraction of the value range (0 < t <= 1) unless `absolute` (D-015)."""
        t = float(threshold)
        if not t > 0 or (not absolute and t > 1):
            raise ValueError(f"simplify threshold must be in (0, 1] as a fraction of the value range "
                             f"(or > 0 with absolute: true), got {threshold!r}")
        self.threshold = t
        self.absolute = bool(absolute)
        self._runner = runner
        self._counts: tuple[int, int] | None = None

    def simplify(self, dataset: Dataset) -> GridDataset:
        if not isinstance(dataset, GridDataset):
            raise ValueError("simplification needs grid data (TTK simplifies a mesh); point data has none")
        values = self._runner(dataset.values, dataset.spacing, dataset.origin, self.threshold, self.absolute)
        if np.shape(values) != dataset.shape:
            raise RuntimeError(f"simplification changed the shape {dataset.shape} -> {np.shape(values)}")
        self._counts = (count_maxima_on_ttk_mesh(dataset.values), count_maxima_on_ttk_mesh(values))
        return dataset.with_values(values)

    def report(self) -> dict[str, Any]:
        """For graph.json and the run summary: the threshold and its effect."""
        out: dict[str, Any] = {"threshold": self.threshold, "absolute": self.absolute}
        if self._counts is not None:
            out.update(maxima_before=self._counts[0], maxima_after=self._counts[1])
        return out

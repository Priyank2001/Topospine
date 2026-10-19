"""TTK backend: regions from TTK's Morse-Smale complex, saddles by our boundary scan.

Why only the segmentation?
    TTK's separatrix outputs (port names, array names, separatrix type codes) have
    changed between TTK releases. The per-vertex manifold ids are the most stable
    part of its output, and they are all we need: G follows from any region
    labelling via core.graph_from_regions. Regions then come from TTK's exact
    discrete gradient, saddles from the same rule our native source uses, so any
    difference between the two backends is a difference in regions - easy to
    compare and to explain in the report.

Which array holds the maxima's regions?
    The name depends on TTK's ascending/descending convention, so we don't trust a
    name blindly: each candidate array is scored by the fraction of its regions that
    contain exactly one local maximum, and the best one wins (`pick_maximum_regions`).
    TTK's triangulation and our stencil define "neighbour" slightly differently, so
    the score of the right array is high but not always 1.0 on noisy data.

TTK is imported lazily, so the rest of the package (and its tests) work without it.
Not yet run against a real TTK install: first run on your machine is the M1 spike.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from topospine.core.datasets import Dataset, GridDataset
from topospine.core.gradient_flow import FlowDecomposition, graph_from_regions, sample_ranks, steepest_ascent
from topospine.core.neighborhoods import GridNeighborhood

DEFAULT_CANDIDATES = ("DescendingManifold", "AscendingManifold")


def compact_labels(raw: NDArray) -> NDArray[np.int64]:
    """Map arbitrary region ids (TTK uses critical-point ids) to 0..M-1."""
    _, inverse = np.unique(np.asarray(raw).ravel(), return_inverse=True)
    return inverse.astype(np.int64)


def maximum_score(values: NDArray, labels: NDArray[np.int64], neighborhood: GridNeighborhood) -> float:
    """Fraction of regions that contain exactly one local maximum (1.0 = perfect).

    Regions of maxima each hold exactly one maximum. Regions of minima don't: maxima
    sit on their boundaries, so a minimum's region holds zero or several. (Scoring by
    "is the region's top a local max" would not discriminate, because the top of a
    minimum's region is often a maximum on its boundary.)
    """
    ranks = sample_ranks(values)
    is_local_max = steepest_ascent(ranks, neighborhood) == np.arange(ranks.size)
    m = int(labels.max()) + 1
    maxima_per_region = np.bincount(labels[is_local_max], minlength=m)
    return float((maxima_per_region == 1).mean())


def pick_maximum_regions(
    values: NDArray, arrays: Mapping[str, NDArray], neighborhood: GridNeighborhood
) -> tuple[str, NDArray[np.int64], dict[str, float]]:
    scores, labelled = {}, {}
    for name, raw in arrays.items():
        labelled[name] = compact_labels(raw)
        scores[name] = maximum_score(values, labelled[name], neighborhood)
    best = max(scores, key=scores.get)
    return best, labelled[best], scores


def numpy_to_image(values: NDArray, spacing: Sequence[float], origin: Sequence[float], name: str = "f"):
    """(z, y, x) NumPy array -> vtkImageData with one point array (x fastest in both)."""
    from vtkmodules.util.numpy_support import numpy_to_vtk
    from vtkmodules.vtkCommonDataModel import vtkImageData

    v = np.ascontiguousarray(values, dtype=np.float64)
    dims = list(v.shape[::-1]) + [1] * (3 - v.ndim)
    sp = list(spacing[::-1]) + [1.0] * (3 - v.ndim)
    org = list(origin[::-1]) + [0.0] * (3 - v.ndim)
    img = vtkImageData()
    img.SetDimensions(*dims)
    img.SetSpacing(*sp)
    img.SetOrigin(*org)
    arr = numpy_to_vtk(v.ravel(), deep=True)
    arr.SetName(name)
    img.GetPointData().AddArray(arr)
    img.GetPointData().SetActiveScalars(name)
    return img


class TtkSource:
    name = "ttk"

    def __init__(self, connectivity: int | None = None, candidates: Sequence[str] = DEFAULT_CANDIDATES,
                 min_score: float = 0.5) -> None:
        self.connectivity = connectivity
        self.candidates = tuple(candidates)
        self.min_score = float(min_score)
        self.last_choice: tuple[str, dict[str, float]] | None = None   # for logging / the report

    def _run_ttk(self, dataset: GridDataset) -> dict[str, NDArray]:
        try:
            import topologytoolkit as ttk
            from vtkmodules.util.numpy_support import vtk_to_numpy
        except ImportError as exc:
            raise RuntimeError(
                "TTK not importable. Install it with "
                "`conda install -c conda-forge topologytoolkit` and run inside that env."
            ) from exc
        img = numpy_to_image(dataset.values, dataset.spacing, dataset.origin)
        msc = ttk.ttkMorseSmaleComplex()
        msc.SetInputDataObject(img)
        msc.SetInputArrayToProcess(0, 0, 0, 0, "f")
        msc.Update()
        found: dict[str, NDArray] = {}
        for port in range(msc.GetNumberOfOutputPorts()):   # don't hard-code the port number
            pd = msc.GetOutputDataObject(port).GetPointData()
            for name in self.candidates:
                arr = pd.GetArray(name)
                if arr is not None and arr.GetNumberOfTuples() == dataset.num_samples:
                    found[name] = vtk_to_numpy(arr)
        if not found:
            raise RuntimeError(f"TTK output has none of the arrays {self.candidates}; "
                               "check the names in your TTK version and pass `candidates`.")
        return found

    def compute(self, dataset: Dataset) -> FlowDecomposition:
        if not isinstance(dataset, GridDataset):
            raise ValueError("the TTK source handles grid datasets; use the native source for point data")
        nb = GridNeighborhood(dataset.shape, self.connectivity or (3 ** len(dataset.shape) - 1))
        name, labels, scores = pick_maximum_regions(dataset.values, self._run_ttk(dataset), nb)
        self.last_choice = (name, scores)
        if scores[name] < self.min_score:
            raise RuntimeError(f"no TTK array looks like maxima regions (scores {scores})")
        return graph_from_regions(dataset.values, labels, nb)

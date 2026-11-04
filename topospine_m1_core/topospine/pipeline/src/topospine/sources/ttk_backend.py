"""The only module that talks to TTK/VTK: run ttkMorseSmaleComplex once, hand back NumPy.

    GridDataset ─► numpy_to_image ─► ttkMorseSmaleComplex ─► read_ports ─► MorseSmaleOutput
                                                                          (plain, read-only NumPy)

TtkBackend caches the last result, so when the regions block and the saddles block of
a `ttk+ttk` run share one backend, TTK runs once per dataset, not twice.

What this module does NOT do: decide what the arrays mean. Which port holds the
saddles, which segmentation array is the maxima's, what SeparatrixType codes stand for:
all of that changes between TTK releases and lives in the blocks (ttk_blocks.py), next
to the checks that catch a wrong guess. Here every port is copied as it is.

TTK and VTK are imported lazily, so the package and its tests work without them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from topospine.core.datasets import Dataset, GridDataset

SCALAR_NAME = "f"          # name of the input array TTK is told to process
INSTALL_HINT = "install it with `conda install -c conda-forge topologytoolkit` and run inside that env"


def import_ttk() -> ModuleType:
    try:
        import topologytoolkit as ttk
    except ImportError as exc:
        raise RuntimeError(f"TTK not importable; {INSTALL_HINT}.") from exc
    return ttk


def numpy_to_image(values: NDArray, spacing: Sequence[float], origin: Sequence[float], name: str = SCALAR_NAME):
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


@dataclass(frozen=True)
class PortArrays:
    """One output port as NumPy: its named point arrays and cell arrays (copies, read-only)."""

    point: Mapping[str, NDArray]
    cell: Mapping[str, NDArray]


@dataclass(frozen=True)
class MorseSmaleOutput:
    """Everything ttkMorseSmaleComplex produced for one dataset, one PortArrays per port."""

    ports: tuple[PortArrays, ...]

    def per_sample_arrays(self, num_samples: int) -> dict[str, NDArray]:
        """Point arrays with one value per input sample, from any port (the segmentation).

        Searched by length rather than by port number, because the port has moved
        between TTK releases. If two ports share a name, the first port wins.
        """
        found: dict[str, NDArray] = {}
        for port in self.ports:
            for name, arr in port.point.items():
                if arr.shape[0] == num_samples and name not in found:
                    found[name] = arr
        return found


def _to_numpy(field_data: Any) -> dict[str, NDArray]:
    """vtkFieldData -> {name: read-only copy}. Non-numeric arrays (strings) are skipped."""
    from vtkmodules.util.numpy_support import vtk_to_numpy

    out: dict[str, NDArray] = {}
    for i in range(field_data.GetNumberOfArrays()):
        arr = field_data.GetArray(i)          # None for vtkStringArray and other non-data arrays
        if arr is None or not arr.GetName():
            continue
        a = np.array(vtk_to_numpy(arr), copy=True)   # don't keep a view into memory VTK owns
        a.setflags(write=False)                       # cached and shared by two blocks
        out[arr.GetName()] = a
    return out


def read_ports(algorithm: Any) -> MorseSmaleOutput:
    """Copy every output port of an updated VTK algorithm into a MorseSmaleOutput."""
    ports = []
    for p in range(algorithm.GetNumberOfOutputPorts()):
        obj = algorithm.GetOutputDataObject(p)
        if obj is None or not hasattr(obj, "GetPointData"):
            ports.append(PortArrays({}, {}))
            continue
        ports.append(PortArrays(_to_numpy(obj.GetPointData()), _to_numpy(obj.GetCellData())))
    return MorseSmaleOutput(tuple(ports))


def run_morse_smale(dataset: GridDataset) -> MorseSmaleOutput:
    """Run ttkMorseSmaleComplex with TTK's defaults on the dataset's values."""
    ttk = import_ttk()
    msc = ttk.ttkMorseSmaleComplex()
    msc.SetInputDataObject(numpy_to_image(dataset.values, dataset.spacing, dataset.origin))
    msc.SetInputArrayToProcess(0, 0, 0, 0, SCALAR_NAME)
    msc.Update()
    return read_ports(msc)


class TtkBackend:
    """Runs TTK on demand and remembers the last dataset's result.

    runner: what actually computes the output (default: real TTK). Tests pass a fake.
    The cache holds one entry, keyed on dataset identity: datasets are immutable, and
    a minimum graph negates values into a NEW dataset, so it can't hit a stale entry.
    """

    def __init__(self, runner: Callable[[GridDataset], MorseSmaleOutput] = run_morse_smale) -> None:
        self._runner = runner
        self._last: tuple[GridDataset, MorseSmaleOutput] | None = None

    def morse_smale(self, dataset: Dataset) -> MorseSmaleOutput:
        if not isinstance(dataset, GridDataset):
            raise ValueError("TTK methods handle grid datasets; use the native methods for point data")
        if self._last is None or self._last[0] is not dataset:
            self._last = (dataset, self._runner(dataset))
        return self._last[1]

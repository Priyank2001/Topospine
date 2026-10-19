"""Readers: files on disk -> GridDataset / PointDataset.

Supported
    raw         headerless binary volume; dims given in (x, y, z) order as data
                catalogues list them, x fastest
    npy         NumPy array holding a grid
    vti         VTK XML image data (needs the `vtk` package; imported lazily)
    csv         point table with a header row
    points_npy  (n, d+1) NumPy table, value in the last column

Adding a format = one new function + one entry in READERS (Open/Closed).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from topospine.core.datasets import Dataset, GridDataset, NormalizeMethod, PointDataset, normalize_points


def _axis_tuple(values_xyz: Sequence[float] | None, nd: int, default: float) -> tuple[float, ...]:
    """Config gives (x, y, z); arrays are (z, y, x)."""
    vals = list(values_xyz) if values_xyz is not None else [default] * nd
    if len(vals) != nd:
        raise ValueError(f"expected {nd} entries, got {vals}")
    return tuple(float(v) for v in vals[::-1])


def read_raw(
    path: str | Path,
    dims_xyz: Sequence[int],
    dtype: str = "uint8",
    byte_order: str = "little",
    spacing_xyz: Sequence[float] | None = None,
    origin_xyz: Sequence[float] | None = None,
    name: str | None = None,
    value_name: str = "f",
) -> GridDataset:
    path = Path(path)
    dims = [int(d) for d in dims_xyz]
    dt = np.dtype(dtype).newbyteorder("<" if byte_order == "little" else ">")
    data = np.fromfile(path, dtype=dt)
    expected = int(np.prod(dims))
    if data.size != expected:
        raise ValueError(f"{path.name}: {data.size} values on disk, dims {dims} need {expected}")
    values = data.reshape(dims[::-1]).astype(np.float64)   # x fastest => numpy shape (z, y, x)
    nd = len(dims)
    return GridDataset(name or path.stem, values, _axis_tuple(spacing_xyz, nd, 1.0),
                       _axis_tuple(origin_xyz, nd, 0.0), value_name)


def read_npy_grid(
    path: str | Path,
    spacing_xyz: Sequence[float] | None = None,
    origin_xyz: Sequence[float] | None = None,
    name: str | None = None,
    value_name: str = "f",
) -> GridDataset:
    path = Path(path)
    values = np.load(path).astype(np.float64)
    nd = values.ndim
    return GridDataset(name or path.stem, values, _axis_tuple(spacing_xyz, nd, 1.0),
                       _axis_tuple(origin_xyz, nd, 0.0), value_name)


def read_vti(path: str | Path, array: str | None = None, name: str | None = None) -> GridDataset:
    try:
        from vtkmodules.util.numpy_support import vtk_to_numpy
        from vtkmodules.vtkIOXML import vtkXMLImageDataReader
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("reading .vti needs the `vtk` package (pip install vtk, or the TTK conda env)") from exc
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    reader = vtkXMLImageDataReader()
    reader.SetFileName(str(path))
    reader.Update()
    img = reader.GetOutput()
    pd = img.GetPointData()
    arr = pd.GetArray(array) if array else (pd.GetScalars() or pd.GetArray(0))
    if arr is None:
        raise ValueError(f"{path.name}: no point array {array!r}")
    if arr.GetNumberOfComponents() != 1:
        raise ValueError(f"{path.name}: array {arr.GetName()!r} is not scalar")
    dims, spacing, origin = list(img.GetDimensions()), list(img.GetSpacing()), list(img.GetOrigin())
    while len(dims) > 1 and dims[-1] == 1:       # 2-D images are stored with nz = 1
        dims.pop(), spacing.pop(), origin.pop()
    values = vtk_to_numpy(arr).astype(np.float64).reshape(dims[::-1])
    return GridDataset(name or path.stem, values, tuple(spacing[::-1]), tuple(origin[::-1]), arr.GetName() or "f")


def _points_dataset(table, names, value_column, feature_columns, normalize, name) -> PointDataset:
    if value_column not in names:
        raise ValueError(f"value column {value_column!r} not found; have {names}")
    features = list(feature_columns) if feature_columns else [c for c in names if c != value_column]
    missing = [c for c in features if c not in names]
    if missing:
        raise ValueError(f"feature columns not found: {missing}")
    cols = {c: i for i, c in enumerate(names)}
    pts, off, sc = normalize_points(table[:, [cols[c] for c in features]], normalize)
    return PointDataset(name, pts, table[:, cols[value_column]], tuple(features), value_column, off, sc)


def read_points_csv(
    path: str | Path,
    value_column: str,
    feature_columns: Sequence[str] | None = None,
    normalize: NormalizeMethod = "zscore",
    delimiter: str = ",",
    name: str | None = None,
) -> PointDataset:
    path = Path(path)
    with path.open() as fh:
        header = [h.strip() for h in fh.readline().split(delimiter)]
    table = np.loadtxt(path, delimiter=delimiter, skiprows=1, ndmin=2)
    if table.shape[1] != len(header):
        raise ValueError(f"{path.name}: header has {len(header)} columns, rows have {table.shape[1]}")
    return _points_dataset(table, header, value_column, feature_columns, normalize, name or path.stem)


def read_points_npy(path: str | Path, normalize: NormalizeMethod = "zscore", name: str | None = None) -> PointDataset:
    path = Path(path)
    table = np.load(path).astype(np.float64)
    if table.ndim != 2 or table.shape[1] < 2:
        raise ValueError("point table must be (n, d+1) with the value in the last column")
    names = [f"x{i}" for i in range(table.shape[1] - 1)] + ["f"]
    return _points_dataset(table, names, "f", None, normalize, name or path.stem)


READERS: dict[str, Callable[..., Dataset]] = {
    "raw": read_raw,
    "npy": read_npy_grid,
    "vti": read_vti,
    "csv": read_points_csv,
    "points_npy": read_points_npy,
}


def read_dataset(kind: str, path: str | Path, **params: Any) -> Dataset:
    if kind not in READERS:
        raise ValueError(f"unknown dataset type {kind!r}; choose from {sorted(READERS)}")
    return READERS[kind](path, **params)

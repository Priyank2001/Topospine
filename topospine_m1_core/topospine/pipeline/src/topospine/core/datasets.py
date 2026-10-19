"""Dataset containers: what every reader and synthetic generator returns.

Two kinds, chosen once by the reader; everything downstream branches on
`dataset.kind` in exactly one place per consumer (source selection, export):

* GridDataset  - values on a regular grid. Array axes are (z, y, x) / (y, x) / (x,)
                 and the flattened C order has x fastest, which is also VTK's and
                 WebGL's 3D-texture order, so sample indices mean the same thing in
                 NumPy, TTK and the browser.
* PointDataset - scattered samples in d dimensions with one value each. `points`
                 are already in the space the kNN graph is built in (normalised);
                 `offset`/`scale` recover the original units.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union

import numpy as np
from numpy.typing import NDArray

NormalizeMethod = Literal["none", "zscore", "minmax"]


@dataclass(frozen=True, eq=False)
class GridDataset:
    name: str
    values: NDArray[np.float64]           # shape in array order (z, y, x)
    spacing: tuple[float, ...]            # per array axis, same order as values.shape
    origin: tuple[float, ...]             # per array axis
    value_name: str = "f"
    kind: Literal["grid"] = field(default="grid", init=False)

    def __post_init__(self) -> None:
        v = np.ascontiguousarray(self.values, dtype=np.float64)
        if v.ndim not in (1, 2, 3):
            raise ValueError("grid values must be 1-, 2- or 3-D")
        if len(self.spacing) != v.ndim or len(self.origin) != v.ndim:
            raise ValueError("spacing and origin need one entry per array axis")
        if not np.isfinite(v).all():
            raise ValueError("grid values must be finite")
        object.__setattr__(self, "values", v)

    @property
    def num_samples(self) -> int:
        return int(self.values.size)

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(self.values.shape)

    def positions(self, samples: NDArray[np.integer]) -> NDArray[np.float64]:
        """Physical coordinates of flat sample indices, returned in (x, y, z) order."""
        idx = np.stack(np.unravel_index(np.asarray(samples, dtype=np.int64), self.shape), axis=1)
        phys = np.asarray(self.origin) + idx * np.asarray(self.spacing)
        return phys[:, ::-1].astype(np.float64)

    def with_values(self, values: NDArray[np.floating]) -> GridDataset:
        return GridDataset(self.name, np.asarray(values).reshape(self.shape), self.spacing, self.origin, self.value_name)


@dataclass(frozen=True, eq=False)
class PointDataset:
    name: str
    points: NDArray[np.float64]           # (n, d) in neighbourhood space (normalised)
    values: NDArray[np.float64]           # (n,)
    feature_names: tuple[str, ...]
    value_name: str = "f"
    offset: NDArray[np.float64] | None = None   # original = points * scale + offset
    scale: NDArray[np.float64] | None = None
    kind: Literal["points"] = field(default="points", init=False)

    def __post_init__(self) -> None:
        p = np.ascontiguousarray(self.points, dtype=np.float64)
        v = np.ascontiguousarray(self.values, dtype=np.float64).ravel()
        if p.ndim != 2 or p.shape[0] != v.size:
            raise ValueError("points must be (n, d) with one value per point")
        if len(self.feature_names) != p.shape[1]:
            raise ValueError("one feature name per dimension required")
        if not (np.isfinite(p).all() and np.isfinite(v).all()):
            raise ValueError("points and values must be finite")
        d = p.shape[1]
        off = np.zeros(d) if self.offset is None else np.asarray(self.offset, dtype=np.float64)
        sc = np.ones(d) if self.scale is None else np.asarray(self.scale, dtype=np.float64)
        object.__setattr__(self, "points", p)
        object.__setattr__(self, "values", v)
        object.__setattr__(self, "offset", off)
        object.__setattr__(self, "scale", sc)

    @property
    def num_samples(self) -> int:
        return int(self.values.size)

    @property
    def dim(self) -> int:
        return int(self.points.shape[1])

    def positions(self, samples: NDArray[np.integer]) -> NDArray[np.float64]:
        return self.points[np.asarray(samples, dtype=np.int64)]

    def with_values(self, values: NDArray[np.floating]) -> PointDataset:
        return PointDataset(self.name, self.points, values, self.feature_names, self.value_name, self.offset, self.scale)


Dataset = Union[GridDataset, PointDataset]


def normalize_points(points: NDArray[np.floating], method: NormalizeMethod) -> tuple[NDArray, NDArray, NDArray]:
    """Return (normalised, offset, scale) with original = normalised * scale + offset.

    kNN distances mix all features, so features in different units must be put on a
    common scale first. Constant features get scale 1 (no division by zero).
    """
    p = np.asarray(points, dtype=np.float64)
    if method == "none":
        off, sc = np.zeros(p.shape[1]), np.ones(p.shape[1])
    elif method == "zscore":
        off, sc = p.mean(axis=0), p.std(axis=0)
    elif method == "minmax":
        off, sc = p.min(axis=0), p.max(axis=0) - p.min(axis=0)
    else:
        raise ValueError(f"unknown normalisation {method!r}")
    sc = np.where(sc > 0, sc, 1.0)
    return (p - off) / sc, off, sc

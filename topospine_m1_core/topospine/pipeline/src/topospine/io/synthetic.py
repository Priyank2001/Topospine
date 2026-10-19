"""Synthetic datasets with known topology: ground truth for tests and demos.

Grid fields
    bumps   sum of Gaussian bumps (count and positions of maxima known)
    ring    bumps on a circle around a lower centre: a cycle in the extremum graph,
            like the paper's Fig. 5 "cycle of hills"
Point samples (any dimension), generator "points" with function=
    mixture   Gaussian mixture
    ackley    Ackley's path function; on [-1.5, 1.5]^d it has 3^d local minima
              (paper Fig. 13a; use with extremum: minima)
    schwefel  Schwefel's function (paper Fig. 13b)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from topospine.core.datasets import Dataset, GridDataset, PointDataset


def _bump_field(coords: NDArray, centers: NDArray, heights: NDArray, width: float) -> NDArray:
    out = np.zeros(coords.shape[0])
    for c, h in zip(centers, heights):   # loop over bumps: memory O(n), not O(n * bumps)
        out += h * np.exp(-((coords - c) ** 2).sum(axis=1) / (2 * width**2))
    return out


def bumps_grid(
    dims_xyz: Sequence[int] = (128, 128),
    centers: Sequence[Sequence[float]] = ((0.3, 0.5), (0.7, 0.5)),
    heights: Sequence[float] = (1.0, 0.6),
    width: float = 0.08,
    noise: float = 0.0,
    seed: int = 0,
    name: str = "bumps",
) -> GridDataset:
    """Bumps on the unit square/cube; centres given as (x, y[, z]) in [0, 1]."""
    dims = [int(n) for n in dims_xyz]
    centers_arr = np.asarray(centers, float)
    if centers_arr.ndim != 2 or centers_arr.shape[1] != len(dims):
        raise ValueError("each centre needs one coordinate per grid axis")
    if len(heights) != len(centers_arr):
        raise ValueError("one height per centre")
    axes = [np.linspace(0, 1, n) for n in dims]
    mesh = np.meshgrid(*axes[::-1], indexing="ij")              # array order (z, y, x)
    coords = np.stack([m.ravel() for m in mesh[::-1]], axis=1)  # columns x, y, z
    f = _bump_field(coords, centers_arr, np.asarray(heights, float), width)
    if noise:
        f = f + noise * np.random.default_rng(seed).normal(size=f.shape)
    spacing = tuple(1.0 / max(n - 1, 1) for n in dims[::-1])
    return GridDataset(name, f.reshape(dims[::-1]), spacing, (0.0,) * len(dims))


def ring_grid(n: int = 128, count: int = 8, radius: float = 0.3, width: float = 0.06,
              noise: float = 0.0, seed: int = 0, name: str = "ring") -> GridDataset:
    t = np.arange(count) * 2 * np.pi / count
    centers = np.stack([0.5 + radius * np.cos(t), 0.5 + radius * np.sin(t)], axis=1)
    heights = 1.0 + 0.1 * np.cos(3 * t)        # slightly uneven so persistence isn't degenerate
    return bumps_grid((n, n), centers, heights, width, noise, seed, name)


def ackley(x: NDArray) -> NDArray:
    d = x.shape[1]
    return (-20 * np.exp(-0.2 * np.sqrt((x**2).sum(axis=1) / d))
            - np.exp(np.cos(2 * np.pi * x).sum(axis=1) / d) + 20 + np.e)


def schwefel(x: NDArray) -> NDArray:
    return 418.9829 * x.shape[1] - (x * np.sin(np.sqrt(np.abs(x)))).sum(axis=1)


def mixture(x: NDArray, centers: Sequence[Sequence[float]], heights: Sequence[float], width: float = 0.15) -> NDArray:
    return _bump_field(x, np.asarray(centers, float), np.asarray(heights, float), width)


POINT_FUNCTIONS: dict[str, Callable[..., NDArray]] = {"ackley": ackley, "schwefel": schwefel, "mixture": mixture}


def sample_points(
    function: str, dim: int, n: int, low: float, high: float, seed: int = 0,
    name: str | None = None, **function_params: Any,
) -> PointDataset:
    """Uniform random samples of an analytic function on [low, high]^dim."""
    if function not in POINT_FUNCTIONS:
        raise ValueError(f"unknown function {function!r}; choose from {sorted(POINT_FUNCTIONS)}")
    x = np.random.default_rng(seed).uniform(low, high, size=(n, dim))
    f = POINT_FUNCTIONS[function](x, **function_params)
    return PointDataset(name or f"{function}{dim}d", x, f, tuple(f"x{i}" for i in range(dim)))


GENERATORS: dict[str, Callable[..., Dataset]] = {"bumps": bumps_grid, "ring": ring_grid, "points": sample_points}


def make_synthetic(generator: str, **params: Any) -> Dataset:
    if generator not in GENERATORS:
        raise ValueError(f"unknown generator {generator!r}; choose from {sorted(GENERATORS)}")
    return GENERATORS[generator](**params)

"""Extremum graph sources: everything that turns a Dataset into a FlowDecomposition.

Two ways to ask for one (DECISIONS.md D-004, D-005):

    make_source("native", connectivity=8)            a PRESET by name (old configs)
    compose_source("ttk", "ttk", connectivity=26)    any region method + saddle method

    REGION_METHODS  name -> factory(shared, **params) -> RegionMethod
    SADDLE_METHODS  name -> factory(shared, **params) -> SaddleMethod
    PRESETS         name -> class (each a fixed pair, kept so old configs and code work)
    PRESET_METHODS  name -> (region method, saddle method) of each preset

Adding a method = one class implementing RegionMethod or SaddleMethod plus one entry
here. `shared` holds what both blocks of ONE run share (e.g. the TTK backend, so a
`ttk+ttk` run calls TTK once); each compose_source call gets a fresh one.
Which pairs are allowed is checked by ComposedSource (D-007), not here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from topospine.sources.base import ExtremumGraphSource, RegionMethod, SaddleMethod
from topospine.sources.composed_source import DEFAULT_K, ComposedSource, Connectivity
from topospine.sources.native_blocks import AscentRegions, BoundarySaddles
from topospine.sources.native_source import NativeSource
from topospine.sources.ttk_backend import TtkBackend
from topospine.sources.ttk_blocks import TtkRegions, TtkSaddles
from topospine.sources.ttk_output import TtkArrayNames
from topospine.sources.ttk_source import TtkSource


class SharedResources:
    """Expensive helpers both blocks of one run may need, created on first use."""

    def __init__(self) -> None:
        self._ttk: TtkBackend | None = None

    @property
    def ttk_backend(self) -> TtkBackend:
        if self._ttk is None:
            self._ttk = TtkBackend()
        return self._ttk


def _ttk_params(params: dict[str, Any]) -> dict[str, Any]:
    """YAML gives `arrays` as a plain mapping; the TTK blocks want TtkArrayNames."""
    if isinstance(params.get("arrays"), Mapping):
        params = {**params, "arrays": TtkArrayNames(**params["arrays"])}
    return params


REGION_METHODS: dict[str, Callable[..., RegionMethod]] = {
    "ascent": lambda shared, **p: AscentRegions(**p),
    "ttk": lambda shared, **p: TtkRegions(shared.ttk_backend, **_ttk_params(p)),
}

SADDLE_METHODS: dict[str, Callable[..., SaddleMethod]] = {
    "boundary": lambda shared, **p: BoundarySaddles(**p),
    "ttk": lambda shared, **p: TtkSaddles(shared.ttk_backend, **_ttk_params(p)),
}

PRESETS: dict[str, Callable[..., ComposedSource]] = {
    "native": NativeSource,     # ascent + boundary
    "ttk": TtkSource,           # ttk + boundary
}

# preset -> (region method, saddle method), so --regions/--saddles can start from a preset.
PRESET_METHODS: dict[str, tuple[str, str]] = {"native": NativeSource.METHODS, "ttk": TtkSource.METHODS}


def _build(registry: Mapping[str, Callable[..., Any]], kind: str, name: str,
           shared: SharedResources, params: Mapping[str, Any] | None) -> Any:
    if name not in registry:
        raise ValueError(f"unknown {kind} method {name!r}; choose from {sorted(registry)}")
    try:
        return registry[name](shared, **dict(params or {}))
    except TypeError as exc:                       # a misspelt or unsupported YAML key
        raise ValueError(f"bad parameters for {kind} method {name!r}: {exc}") from exc


def compose_source(regions: str, saddles: str, *, regions_params: Mapping[str, Any] | None = None,
                   saddles_params: Mapping[str, Any] | None = None, connectivity: Connectivity = None,
                   k: int = DEFAULT_K) -> ComposedSource:
    """Join one region method and one saddle method by name into a source."""
    shared = SharedResources()
    return ComposedSource(_build(REGION_METHODS, "region", regions, shared, regions_params),
                          _build(SADDLE_METHODS, "saddle", saddles, shared, saddles_params),
                          connectivity=connectivity, k=k)


def make_source(kind: str, **params: Any) -> ComposedSource:
    """A preset by name, e.g. `source: {type: native}` in an old config."""
    if kind not in PRESETS:
        raise ValueError(f"unknown source {kind!r}; choose from {sorted(PRESETS)}")
    return PRESETS[kind](**params)


__all__ = [
    "PRESETS",
    "PRESET_METHODS",
    "REGION_METHODS",
    "SADDLE_METHODS",
    "ComposedSource",
    "ExtremumGraphSource",
    "NativeSource",
    "SharedResources",
    "TtkSource",
    "compose_source",
    "make_source",
]

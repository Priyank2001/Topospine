"""Extremum graph sources: everything that turns a Dataset into a FlowDecomposition.

Adding a backend (e.g. TACHYON) = one new module implementing ExtremumGraphSource
plus one entry in SOURCES. Nothing downstream changes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from topospine.sources.base import ExtremumGraphSource
from topospine.sources.native_source import NativeSource
from topospine.sources.ttk_source import TtkSource

SOURCES: dict[str, Callable[..., ExtremumGraphSource]] = {
    "native": NativeSource,
    "ttk": TtkSource,
}


def make_source(kind: str, **params: Any) -> ExtremumGraphSource:
    if kind not in SOURCES:
        raise ValueError(f"unknown source {kind!r}; choose from {sorted(SOURCES)}")
    return SOURCES[kind](**params)


__all__ = ["SOURCES", "ExtremumGraphSource", "NativeSource", "TtkSource", "make_source"]

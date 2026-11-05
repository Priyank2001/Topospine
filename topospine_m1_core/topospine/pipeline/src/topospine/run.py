"""Pipeline orchestration: config -> dataset -> source -> Algorithm 1 -> histograms -> export.

graph.json records how the graph was made (D-006): `source` (preset or "<regions>+<saddles>")
and `extraction` (each block's method and report, plus the neighbourhood settings), and
`simplify` (threshold and maxima before/after) when the field was simplified (D-015).

With `simplify`, the field is simplified once, before extraction, and every method sees it;
the simplified field is also what is exported, so spine heights match the shown field.

Kept separate from cli.py so tests (and notebooks) can call `run_pipeline` directly.
"""

from __future__ import annotations

import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from topospine.config import RunConfig, SimplifyConfig, SourceConfig
from topospine.core.datasets import Dataset
from topospine.core.persistence import Persistence, compute_persistence
from topospine.core.region_stats import region_histograms
from topospine.core.gradient_flow import FlowDecomposition
from topospine.io.exporter import write_export
from topospine.io.readers import read_dataset
from topospine.io.synthetic import make_synthetic
from topospine.sources import ComposedSource, compose_source, make_source
from topospine.sources.ttk_simplify import TtkSimplifier

SIMPLIFY_STENCIL_WARNING = (
    "simplify works on TTK's mesh; with another stencil some features below the threshold "
    "remain (klacansky_foot, 8-stencil, 5 %: 87 left). Set `connectivity: ttk` (D-019).")

SimplifierFactory = Callable[[float, bool], TtkSimplifier]


@dataclass
class RunResult:
    dataset: Dataset
    decomposition: FlowDecomposition
    persistence: Persistence
    output: Path
    timings: dict[str, float] = field(default_factory=dict)
    source_name: str = ""
    extraction: dict[str, Any] = field(default_factory=dict)
    simplify: dict[str, Any] | None = None

    def summary(self) -> str:
        g, P = self.decomposition.graph, self.persistence.persistence
        finite = np.sort(P[g.maxima][np.isfinite(P[g.maxima])])[::-1]
        top = ", ".join(f"{p:.4g}" for p in finite[:5]) or "-"
        t = "  ".join(f"{k} {v:.2f}s" for k, v in self.timings.items())
        return (
            f"dataset   {self.dataset.name} ({self.dataset.kind}, {self.dataset.num_samples} samples)\n"
            f"source    {self.source_name}{_describe(self.extraction)}\n"
            f"{_describe_simplify(self.simplify)}"
            f"graph     {g.maxima.size} extrema, {g.saddles.size} saddles, {g.num_arcs} arcs\n"
            f"top persistence  {top}\n"
            f"timings   {t}\n"
            f"written   {self.output}"
        )


def _describe(extraction: dict[str, Any]) -> str:
    """'  (regions: ttk, array AscendingManifold, score 0.99; saddles: ttk, kept 9, ...)'."""
    parts = []
    for block in ("regions", "saddles"):
        info = dict(extraction.get(block, {}))
        method = info.pop("method", "?")
        parts.append(", ".join([f"{block}: {method}", *(f"{k} {v}" for k, v in info.items())]))
    return f"  ({'; '.join(parts)})" if parts else ""


def _describe_simplify(report: dict[str, Any] | None) -> str:
    """'simplify  2% of range, maxima 297 -> 3\n', or '' when off."""
    if not report:
        return ""
    t = f"{report['threshold']:g} absolute" if report["absolute"] else f"{report['threshold']:.4g} of range"
    counts = f", maxima {report['maxima_before']} -> {report['maxima_after']}" if "maxima_after" in report else ""
    return f"simplify  {t}{counts}\n"


def build_simplifier(cfg: SimplifyConfig | None,
                     factory: SimplifierFactory = TtkSimplifier) -> TtkSimplifier | None:
    return None if cfg is None else factory(cfg.threshold, cfg.absolute)


def build_source(cfg: SourceConfig) -> ComposedSource:
    """A preset (`type`) or two named blocks (`regions` + `saddles`) from the config."""
    if cfg.regions is not None and cfg.saddles is not None:
        return compose_source(cfg.regions.type, cfg.saddles.type, regions_params=cfg.regions.params,
                              saddles_params=cfg.saddles.params, **cfg.params)
    assert cfg.type is not None
    return make_source(cfg.type, **cfg.params)


def load_dataset(cfg: RunConfig) -> Dataset:
    d = cfg.dataset
    if d.type == "synthetic":
        return make_synthetic(d.generator, **d.params)
    return read_dataset(d.type, d.path, **d.params)


def run_pipeline(cfg: RunConfig, output: Path | None = None,
                 simplifier_factory: SimplifierFactory = TtkSimplifier) -> RunResult:
    """`simplifier_factory` lets tests swap TTK for a fake; runs use TtkSimplifier."""
    timings: dict[str, float] = {}
    source = build_source(cfg.source)       # first: a bad method pair fails before any data loads
    simplifier = build_simplifier(cfg.simplify, simplifier_factory)    # ...and so does a bad threshold
    if simplifier is not None and cfg.source.params.get("connectivity") != "ttk":
        warnings.warn(SIMPLIFY_STENCIL_WARNING, stacklevel=2)          # D-019
    t0 = time.perf_counter()
    dataset = load_dataset(cfg)
    timings["load"] = time.perf_counter() - t0

    # Sources only compute maxima; a minimum graph is the maximum graph of -f.
    flip = cfg.extremum == "minima"
    work = dataset.with_values(-dataset.values) if flip else dataset
    if simplifier is not None:
        # After the flip, so TTK always removes maximum-saddle pairs (= minima of the original).
        t0 = time.perf_counter()
        work = simplifier.simplify(work)
        dataset = work.with_values(-work.values) if flip else work    # export the simplified field
        timings["simplify"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    dec = source.compute(work)
    timings["regions+saddles"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    pers = compute_persistence(dec.graph)
    timings["persistence"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    simplified = simplifier.report() if simplifier is not None else None
    meta: dict[str, Any] = {"source": source.name, "extraction": source.report(), "config": cfg.name}
    if simplified is not None:
        meta["simplify"] = simplified
    hist = region_histograms(dataset.values, dec.labels, int(dec.graph.maxima.size), cfg.histogram_bins)
    out = write_export(
        output or cfg.output, dataset, dec, pers, hist, cfg.extremum, cfg.field_encoding,
        extra_meta=meta,
    )
    timings["export"] = time.perf_counter() - t0
    return RunResult(dataset, dec, pers, out, timings, source.name, source.report(), simplified)

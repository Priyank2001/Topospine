"""Pipeline orchestration: config -> dataset -> source -> Algorithm 1 -> histograms -> export.

Kept separate from cli.py so tests (and notebooks) can call `run_pipeline` directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from topospine.config import RunConfig
from topospine.core.datasets import Dataset
from topospine.core.persistence import Persistence, compute_persistence
from topospine.core.region_stats import region_histograms
from topospine.core.gradient_flow import FlowDecomposition
from topospine.io.exporter import write_export
from topospine.io.readers import read_dataset
from topospine.io.synthetic import make_synthetic
from topospine.sources import make_source


@dataclass
class RunResult:
    dataset: Dataset
    decomposition: FlowDecomposition
    persistence: Persistence
    output: Path
    timings: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        g, P = self.decomposition.graph, self.persistence.persistence
        finite = np.sort(P[g.maxima][np.isfinite(P[g.maxima])])[::-1]
        top = ", ".join(f"{p:.4g}" for p in finite[:5]) or "-"
        t = "  ".join(f"{k} {v:.2f}s" for k, v in self.timings.items())
        return (
            f"dataset   {self.dataset.name} ({self.dataset.kind}, {self.dataset.num_samples} samples)\n"
            f"graph     {g.maxima.size} extrema, {g.saddles.size} saddles, {g.num_arcs} arcs\n"
            f"top persistence  {top}\n"
            f"timings   {t}\n"
            f"written   {self.output}"
        )


def load_dataset(cfg: RunConfig) -> Dataset:
    d = cfg.dataset
    if d.type == "synthetic":
        return make_synthetic(d.generator, **d.params)
    return read_dataset(d.type, d.path, **d.params)


def run_pipeline(cfg: RunConfig, output: Path | None = None) -> RunResult:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    dataset = load_dataset(cfg)
    timings["load"] = time.perf_counter() - t0

    # Sources only compute maxima; a minimum graph is the maximum graph of -f.
    work = dataset if cfg.extremum == "maxima" else dataset.with_values(-dataset.values)
    source = make_source(cfg.source.type, **cfg.source.params)
    t0 = time.perf_counter()
    dec = source.compute(work)
    timings["regions+saddles"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    pers = compute_persistence(dec.graph)
    timings["persistence"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    hist = region_histograms(dataset.values, dec.labels, int(dec.graph.maxima.size), cfg.histogram_bins)
    out = write_export(
        output or cfg.output, dataset, dec, pers, hist, cfg.extremum, cfg.field_encoding,
        extra_meta={"source": source.name, "config": cfg.name},
    )
    timings["export"] = time.perf_counter() - t0
    return RunResult(dataset, dec, pers, out, timings)

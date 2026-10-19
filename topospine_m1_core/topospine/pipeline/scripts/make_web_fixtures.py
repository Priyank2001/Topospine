"""Export small datasets into web/tests/fixtures so TypeScript tests run on real pipeline output.

    python scripts/make_web_fixtures.py

line   the 9-sample worked example (unit histogram bins, so counts are exact at integers)
ring   noisy ring of 6 hills, 64x64: cycles, merging, both P* variants
ackley 2-D Ackley minima from 1500 random points: a minimum graph from point data
"""

from pathlib import Path

import numpy as np

from topospine.core import compute_persistence, region_histograms
from topospine.core.datasets import GridDataset
from topospine.io.exporter import write_export
from topospine.io.synthetic import ring_grid, sample_points
from topospine.sources.native_source import NativeSource

OUT = Path(__file__).resolve().parents[2] / "web" / "tests" / "fixtures"


def export(name, dataset, extremum="maxima", bins=32, value_range=None, **source):
    work = dataset if extremum == "maxima" else dataset.with_values(-dataset.values)
    dec = NativeSource(**source).compute(work)
    pers = compute_persistence(dec.graph)
    hist = region_histograms(dataset.values, dec.labels, dec.graph.maxima.size, bins, value_range)
    write_export(OUT / name, dataset, dec, pers, hist, extremum, extra_meta={"source": "native", "config": name})
    print(f"{name}: {dec.graph.maxima.size} extrema, {dec.graph.saddles.size} saddles")


if __name__ == "__main__":
    line = GridDataset("line", np.array([1, 5, 3, 4, 2, 9, 6, 8, 0], float), (1.0,), (0.0,))
    export("line", line, bins=9, value_range=(0, 9), connectivity=2)
    export("ring", ring_grid(64, count=6, radius=0.3, width=0.08, noise=0.01, seed=3), connectivity=8)
    export("ackley", sample_points("ackley", 2, 1500, -1.5, 1.5, seed=0), extremum="minima", k=12)

#!/usr/bin/env python3
"""
export_to_topospine.py  (v1)

Run the high-dimensional extremum graph and write it in the file format of the
Topospine web viewer, so the interactive spine view can open it.

It reuses Topospine's own pipeline (steepest ascent, Algorithm 1, histograms,
exporter) and only replaces the neighbour search: the exact KD-tree is swapped for
an approximate nearest-neighbour graph (pynndescent), which is what makes 300-D
data feasible. The graph is built in the FULL space unless you pass --pca-dims.

Setup (once)
    pip install numpy scipy pyyaml scikit-learn pynndescent
    git clone https://github.com/Priyank2001/Topospine.git
    pip install -e Topospine/topospine_m1_core/topospine/pipeline

Run
    python3 export_to_topospine.py mydata.npy --name mydata --k 20 \
        --out Topospine/topospine_m1_core/topospine/pipeline/out

View
    cd Topospine/topospine_m1_core/topospine/web
    npm install
    npm run sync-data          # copies ../pipeline/out/* into public/data
    npm run dev                # open http://localhost:5173/?dataset=mydata

Input: .npy with the scalar in the last column, a .csv (--value-column), or .npz
with "X" and "f" (same as hd_extremum_graph.py, which must sit next to this file).

points.bin (n x d float32) is not read by the viewer's drawing code, and for 300
dimensions it is large, so it is left out by default. Use --keep-points to write it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

import hd_extremum_graph as H

try:
    from topospine.core.datasets import PointDataset
    from topospine.core.gradient_flow import decompose
    from topospine.core.persistence import compute_persistence
    from topospine.core.region_stats import region_histograms
    from topospine.io.exporter import write_export
except ImportError as exc:                                    # pragma: no cover
    sys.exit(f"Topospine is not installed ({exc}).\nSee the setup lines at the top of this file.")


class AnnNeighborhood:
    """Neighbourhood backed by a precomputed (approximate) kNN table.

    Same contract as topospine.core.neighborhoods.KnnNeighborhood: undirected edges
    streamed as (src, dst) blocks; consumers apply each edge in both directions.
    """

    def __init__(self, neighbors: np.ndarray) -> None:
        self.neighbors = np.asarray(neighbors, dtype=np.intp)

    @property
    def num_samples(self) -> int:
        return int(self.neighbors.shape[0])

    def edge_blocks(self):
        src = np.arange(self.num_samples, dtype=np.intp)
        for t in range(self.neighbors.shape[1]):
            yield src, self.neighbors[:, t]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help=".npy / .csv / .npz point table")
    p.add_argument("--name", help="dataset name in the viewer (default: input file name)")
    p.add_argument("--value-column", help="csv column holding the scalar (default: last)")
    p.add_argument("--value-name", default="f", help="label for the scalar in the viewer")
    p.add_argument("--k", type=int, default=20)
    p.add_argument("--mode", choices=["max", "min"], default="max")
    p.add_argument("--pca-dims", type=int, default=None, help="optional PCA before the kNN graph")
    p.add_argument("--no-standardize", action="store_true")
    p.add_argument("--backend", choices=["auto", "pynndescent", "sklearn", "numpy"], default="auto")
    p.add_argument("--bins", type=int, default=64, help="histogram bins per region")
    p.add_argument("--keep-points", action="store_true", help="also write points.bin (large in high dimensions)")
    p.add_argument("--out", default="out", help="parent folder; the dataset goes to <out>/<name>/")
    args = p.parse_args(argv)

    name = args.name or Path(args.input).stem
    X, f = H.load_points(args.input, args.value_column)
    print(f"[load] {X.shape[0]} points, {X.shape[1]} dimensions")
    X, f, _kept = H.prepare(X, f, standardize=not args.no_standardize, pca_dims=args.pca_dims)

    t0 = time.perf_counter()
    nb = AnnNeighborhood(H.knn_graph(X, args.k, args.backend))
    print(f"[knn] {time.perf_counter() - t0:.1f}s")

    dataset = PointDataset(
        name=name, points=X, values=f,
        feature_names=tuple(f"x{i}" for i in range(X.shape[1])),
        value_name=args.value_name,
    )
    extremum = "minima" if args.mode == "min" else "maxima"
    work = dataset if extremum == "maxima" else dataset.with_values(-dataset.values)

    t0 = time.perf_counter()
    dec = decompose(work.values, nb)
    pers = compute_persistence(dec.graph)
    print(f"[topology] {dec.graph.maxima.size} extrema, {dec.graph.saddles.size} saddles "
          f"({time.perf_counter() - t0:.1f}s)")

    hist = region_histograms(dataset.values, dec.labels, int(dec.graph.maxima.size), args.bins)
    out_dir = Path(args.out) / name
    write_export(out_dir, dataset, dec, pers, hist, extremum,
                 extra_meta={"source": "ann-knn", "config": f"hd k={args.k}"})

    if not args.keep_points:
        doc_path = out_dir / "graph.json"
        doc = json.loads(doc_path.read_text())
        entry = doc["files"].pop("points", None)
        if entry:
            (out_dir / entry["path"]).unlink(missing_ok=True)
            doc_path.write_text(json.dumps(doc, allow_nan=False, separators=(",", ":")))

    print(f"[export] wrote {out_dir}")
    print(f"\nnext:  npm run sync-data -- {Path(args.out).resolve()}   (from the web folder)\n"
          f"       npm run dev   then open ?dataset={name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

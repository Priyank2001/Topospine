"""Write (and read back) the file contract consumed by the web app.

One directory per dataset:

    graph.json   metadata, nodes (column arrays), arcs, histogram bin edges, file index
    labels.bin   per sample: maximum node id of its region (uint16, or uint32 if > 65535 maxima)
    regions.bin  per maximum: value histogram, uint32, shape (M, B), row-major
    field.bin    grid only: the field, uint8 over valueRange (or float32)
    points.bin   point data only: float32 (n, d), in the normalised space kNN used

All binaries are little-endian, row-major, no header; graph.json["files"] records
dtype, shape and byte length of each so the browser can validate before use.

Conventions in graph.json
    * Node `value` and the histograms use the ORIGINAL f, also for minimum graphs
      (dataset.extremum == "minima"); persistence is a height difference, so it is
      sign-independent.
    * JSON has no Infinity/NaN: P = +inf (never cancelled) and P* of maxima (undefined)
      are written as null.
    * `saturated` is the paper's P*; `saturatedCancel` the cancellation-only variant
      (DEVIATIONS.md #8). The browser lets the user switch between them.
    * `position`: grids in physical (x, y, z); points in normalised feature space.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from topospine.core.datasets import Dataset, GridDataset
from topospine.core.gradient_flow import FlowDecomposition
from topospine.core.graph import GradientFlowGraph
from topospine.core.persistence import Persistence
from topospine.core.region_stats import RegionHistograms

FORMAT_VERSION = 1
Extremum = Literal["maxima", "minima"]


def _nullable(a: NDArray) -> list[float | None]:
    return [float(x) if np.isfinite(x) else None for x in a]


def _write_bin(directory: Path, name: str, array: NDArray, dtype: str) -> dict[str, Any]:
    data = np.ascontiguousarray(array, dtype=np.dtype(dtype).newbyteorder("<"))
    (directory / name).write_bytes(data.tobytes())
    return {"path": name, "dtype": dtype, "shape": list(data.shape), "bytes": int(data.nbytes)}


def write_export(
    out_dir: str | Path,
    dataset: Dataset,
    decomposition: FlowDecomposition,
    persistence: Persistence,
    histograms: RegionHistograms,
    extremum: Extremum = "maxima",
    field_encoding: Literal["uint8", "float32"] = "uint8",
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    """`dataset` holds the ORIGINAL values; `decomposition`/`persistence` were computed on
    values (maxima) or -values (minima)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    g = decomposition.graph
    sign = -1.0 if extremum == "minima" else 1.0
    m = int(g.maxima.size)
    if not np.array_equal(g.maxima, np.arange(m)):
        raise ValueError("expected maxima to be nodes 0..M-1 (as produced by graph_from_regions)")
    if histograms.counts.shape[0] != m:
        raise ValueError("need one histogram row per maximum")

    values = dataset.values.ravel()
    lo, hi = float(values.min()), float(values.max())

    files: dict[str, Any] = {}
    label_dtype = "uint16" if m <= 0xFFFF else "uint32"
    files["labels"] = _write_bin(out, "labels.bin", decomposition.labels, label_dtype)
    files["regions"] = _write_bin(out, "regions.bin", histograms.counts, "uint32")

    meta: dict[str, Any] = {
        "name": dataset.name,
        "kind": dataset.kind,
        "extremum": extremum,
        "numSamples": dataset.num_samples,
        "valueName": dataset.value_name,
        "valueRange": [lo, hi],
    }
    if isinstance(dataset, GridDataset):
        meta["grid"] = {
            "dimsXYZ": list(dataset.shape[::-1]),
            "spacingXYZ": list(dataset.spacing[::-1]),
            "originXYZ": list(dataset.origin[::-1]),
        }
        if field_encoding == "uint8":
            q = np.round((values - lo) / ((hi - lo) or 1.0) * 255.0)
            files["field"] = _write_bin(out, "field.bin", q, "uint8")
        else:
            files["field"] = _write_bin(out, "field.bin", values, "float32")
    else:
        meta["points"] = {
            "dim": dataset.dim,
            "featureNames": list(dataset.feature_names),
            "offset": dataset.offset.tolist(),
            "scale": dataset.scale.tolist(),
        }
        files["points"] = _write_bin(out, "points.bin", dataset.points, "float32")
    if extra_meta:
        meta.update(extra_meta)

    doc = {
        "version": FORMAT_VERSION,
        "dataset": meta,
        "nodes": {
            "kind": g.kinds.astype(int).tolist(),
            "value": (sign * g.values).tolist(),
            "sample": g.samples.tolist(),
            "position": dataset.positions(g.samples).tolist(),
            "persistence": _nullable(persistence.persistence),
            "saturated": _nullable(persistence.saturated),
            "saturatedCancel": _nullable(
                persistence.saturated if persistence.saturated_cancel is None else persistence.saturated_cancel
            ),
            "mergedInto": persistence.merged_into.tolist(),
        },
        "arcs": g.arcs.tolist(),
        "regions": {"binEdges": histograms.bin_edges.tolist(), "numRegions": m},
        "files": files,
    }
    (out / "graph.json").write_text(json.dumps(doc, allow_nan=False, separators=(",", ":")))
    return out


@dataclass(frozen=True, eq=False)
class ExportBundle:
    """Everything in an export directory, rebuilt as core objects (graph in maxima space)."""

    meta: dict[str, Any]
    graph: GradientFlowGraph
    persistence: Persistence
    labels: NDArray[np.int64]
    histograms: RegionHistograms
    positions: NDArray[np.float64]
    field: NDArray[np.float64] | None     # grid only, dequantised, array order (z, y, x)
    points: NDArray[np.float32] | None    # point data only


def _read_bin(directory: Path, entry: dict[str, Any]) -> NDArray:
    raw = (directory / entry["path"]).read_bytes()
    if len(raw) != entry["bytes"]:
        raise ValueError(f"{entry['path']}: {len(raw)} bytes on disk, index says {entry['bytes']}")
    return np.frombuffer(raw, dtype=np.dtype(entry["dtype"]).newbyteorder("<")).reshape(entry["shape"])


def read_export(directory: str | Path) -> ExportBundle:
    d = Path(directory)
    doc = json.loads((d / "graph.json").read_text())
    if doc.get("version") != FORMAT_VERSION:
        raise ValueError(f"unsupported export version {doc.get('version')}")
    meta, nodes, files = doc["dataset"], doc["nodes"], doc["files"]
    sign = -1.0 if meta["extremum"] == "minima" else 1.0

    def floats(xs, none_as):
        return np.array([none_as if x is None else x for x in xs], dtype=np.float64)

    graph = GradientFlowGraph(
        kinds=np.array(nodes["kind"]),
        values=sign * np.array(nodes["value"], dtype=np.float64),
        samples=np.array(nodes["sample"]),
        arcs=np.array(doc["arcs"], dtype=np.int64).reshape(-1, 2),
    )
    pers = Persistence(
        persistence=floats(nodes["persistence"], np.inf),
        saturated=floats(nodes["saturated"], np.nan),
        merged_into=np.array(nodes["mergedInto"], dtype=np.int64),
        saturated_cancel=floats(nodes["saturatedCancel"], np.nan),
    )
    field = points = None
    if "field" in files:
        raw = _read_bin(d, files["field"]).astype(np.float64)
        lo, hi = meta["valueRange"]
        if files["field"]["dtype"] == "uint8":
            raw = lo + raw / 255.0 * (hi - lo)
        field = raw.reshape(meta["grid"]["dimsXYZ"][::-1])
    if "points" in files:
        points = _read_bin(d, files["points"])
    return ExportBundle(
        meta=meta,
        graph=graph,
        persistence=pers,
        labels=_read_bin(d, files["labels"]).astype(np.int64),
        histograms=RegionHistograms(np.array(doc["regions"]["binEdges"]),
                                    _read_bin(d, files["regions"]).astype(np.int64)),
        positions=np.array(nodes["position"], dtype=np.float64),
        field=field,
        points=points,
    )

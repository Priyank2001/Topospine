import json
from pathlib import Path

import numpy as np
import pytest

from topospine.core import compute_persistence, region_histograms
from topospine.io.exporter import read_export, write_export
from topospine.io.synthetic import bumps_grid, sample_points
from topospine.sources.native_source import NativeSource

SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "spine.schema.json"


def export(tmp_path, dataset, extremum="maxima", **kw):
    work = dataset if extremum == "maxima" else dataset.with_values(-dataset.values)
    dec = NativeSource(k=12).compute(work)
    pers = compute_persistence(dec.graph)
    hist = region_histograms(dataset.values, dec.labels, dec.graph.maxima.size, 16)
    out = write_export(tmp_path / "e", dataset, dec, pers, hist, extremum, **kw)
    return out, dec, pers


@pytest.fixture
def grid():
    return bumps_grid((40, 30), centers=[[0.3, 0.5], [0.7, 0.5]], heights=[1.0, 0.6], width=0.1)


def test_roundtrip_grid(tmp_path, grid):
    out, dec, pers = export(tmp_path, grid)
    b = read_export(out)
    assert np.array_equal(b.graph.arcs, dec.graph.arcs) and np.array_equal(b.labels, dec.labels)
    assert np.array_equal(b.persistence.persistence, pers.persistence)       # inf survives via null
    assert np.allclose(b.field, grid.values, atol=np.ptp(grid.values) / 255)   # uint8 quantisation error
    assert b.positions.shape == (dec.graph.num_nodes, 2)
    assert {p.name for p in out.iterdir()} == {"graph.json", "labels.bin", "regions.bin", "field.bin"}


def test_json_is_strict_and_matches_schema(tmp_path, grid):
    jsonschema = pytest.importorskip("jsonschema")
    out, _, _ = export(tmp_path, grid)
    doc = json.loads((out / "graph.json").read_text())   # would fail on Infinity/NaN tokens
    jsonschema.validate(doc, json.loads(SCHEMA.read_text()))
    assert doc["files"]["labels"]["dtype"] == "uint16"
    assert None in doc["nodes"]["persistence"]


def test_minima_export_keeps_original_values(tmp_path):
    pts = sample_points("ackley", 2, 800, -1.5, 1.5)
    out, dec, _ = export(tmp_path, pts, extremum="minima")
    doc = json.loads((out / "graph.json").read_text())
    assert doc["nodes"]["value"] == (-dec.graph.values).tolist()   # original f, not -f
    b = read_export(out)                                            # reloads as a valid maxima-space graph
    assert np.array_equal(b.graph.values, dec.graph.values)
    assert b.points.shape == (800, 2) and b.field is None


def test_float32_field(tmp_path, grid):
    out, _, _ = export(tmp_path, grid, field_encoding="float32")
    assert np.allclose(read_export(out).field, grid.values, atol=1e-6)


def test_truncated_binary_detected(tmp_path, grid):
    out, _, _ = export(tmp_path, grid)
    (out / "labels.bin").write_bytes((out / "labels.bin").read_bytes()[:-2])
    with pytest.raises(ValueError, match="bytes"):
        read_export(out)


@pytest.mark.slow
def test_many_regions_use_uint32_labels(tmp_path):
    from topospine.core.datasets import GridDataset

    f = np.zeros(140_003)
    f[1::2] = 1 + np.random.default_rng(0).random(70_001)     # 70k separate peaks
    ds = GridDataset("many", f, (1.0,), (0.0,))
    out, _, _ = export(tmp_path, ds)
    assert json.loads((out / "graph.json").read_text())["files"]["labels"]["dtype"] == "uint32"

import json
from pathlib import Path

import pytest

from topospine.cli import main
from topospine.config import load_config, parse_config
from topospine.run import run_pipeline

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


def test_relative_paths_resolve_against_config_dir(tmp_path):
    cfg = parse_config({"name": "x", "dataset": {"type": "raw", "path": "data/v.raw", "dims_xyz": [2, 2]},
                        "output": "out/x"}, tmp_path)
    assert cfg.dataset.path == (tmp_path / "data/v.raw").resolve()
    assert cfg.dataset.params == {"dims_xyz": [2, 2]}          # inline params accepted
    assert cfg.output == (tmp_path / "out/x").resolve()


@pytest.mark.parametrize(
    "raw",
    [
        {"dataset": {"type": "synthetic", "generator": "bumps"}},                 # no name
        {"name": "x", "dataset": {"type": "hdf5", "path": "a"}},                  # unknown type
        {"name": "x", "dataset": {"type": "synthetic"}},                         # no generator
        {"name": "x", "dataset": {"type": "raw"}},                               # no path
        {"name": "x", "dataset": {"type": "synthetic", "generator": "bumps"}, "extremum": "saddles"},
    ],
)
def test_invalid_configs(raw, tmp_path):
    with pytest.raises(ValueError):
        parse_config(raw, tmp_path)


def test_shipped_configs_parse():
    for path in CONFIGS.glob("*.yaml"):
        load_config(path)                                       # every example config stays valid


def test_run_pipeline_end_to_end(tmp_path):
    cfg = load_config(CONFIGS / "gauss2d.yaml")
    res = run_pipeline(cfg, tmp_path / "o")
    assert res.decomposition.graph.maxima.size == 2
    meta = json.loads((tmp_path / "o" / "graph.json").read_text())["dataset"]
    assert meta["source"] == "native" and meta["config"] == "gauss2d"
    assert "2 extrema, 1 saddles" in res.summary()


def test_cli_with_preview(tmp_path, capsys):
    pytest.importorskip("matplotlib")
    assert main([str(CONFIGS / "gauss2d.yaml"), "--out", str(tmp_path / "o"), "--preview"]) == 0
    assert (tmp_path / "o" / "preview.png").stat().st_size > 10_000
    assert "preview" in capsys.readouterr().out

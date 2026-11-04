"""The `source:` config forms, the --regions/--saddles override (D-006) and what a run records."""

import json
from pathlib import Path

import pytest
import yaml

from topospine.cli import main
from topospine.config import MethodConfig, load_config, parse_config, parse_source, with_methods
from topospine.run import run_pipeline
from topospine.sources import PRESET_METHODS, PRESETS

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
DATASET = {"type": "synthetic", "generator": "bumps", "params": {"dims_xyz": [48, 40]}}


def _cfg(tmp_path, source):
    return parse_config({"name": "t", "dataset": DATASET, "source": source, "output": "out/t"}, tmp_path)


# ------------------------------------------------------------------ parsing

def test_preset_form_is_unchanged():
    src = parse_source({"type": "ttk", "connectivity": 26})
    assert (src.type, src.params, src.composed) == ("ttk", {"connectivity": 26}, False)
    assert parse_source({}).type == "native"


def test_block_form_accepts_names_and_mappings():
    src = parse_source({"regions": "ttk", "connectivity": 26,
                        "saddles": {"type": "ttk", "arrays": {"separatrix_type": "Kind"}}})
    assert src.composed and src.type is None and src.params == {"connectivity": 26}
    assert src.regions == MethodConfig("ttk")
    assert src.saddles == MethodConfig("ttk", {"arrays": {"separatrix_type": "Kind"}})


@pytest.mark.parametrize("raw, match", [
    ({"type": "native", "regions": "ascent", "saddles": "boundary"}, "not both"),
    ({"regions": "ascent"}, "go together"),
    ({"regions": "ttk", "saddles": "ttk", "min_score": 0.7}, r"unknown keys \['min_score'\]"),
    ({"regions": {"min_score": 0.7}, "saddles": "ttk"}, "mapping with `type`"),
])
def test_bad_source_forms(raw, match):
    with pytest.raises(ValueError, match=match):
        parse_source(raw)


def test_preset_methods_match_the_presets():
    for name, cls in PRESETS.items():
        src = cls()
        assert PRESET_METHODS[name] == (src.regions.name, src.saddles.name)


# ------------------------------------------------------------------ with_methods (D-006)

def test_no_flags_change_nothing(tmp_path):
    cfg = _cfg(tmp_path, {"type": "native"})
    assert with_methods(cfg, PRESET_METHODS) is cfg


def test_flags_repeating_the_config_change_nothing(tmp_path):
    preset = _cfg(tmp_path, {"type": "native", "connectivity": 8})
    assert with_methods(preset, PRESET_METHODS, regions="ascent", saddles="boundary") is preset
    blocks = _cfg(tmp_path, {"regions": "ttk", "saddles": "ttk"})
    assert with_methods(blocks, PRESET_METHODS, saddles="ttk") is blocks


def test_flag_turns_a_preset_into_blocks_with_a_suffix(tmp_path):
    cfg = with_methods(_cfg(tmp_path, {"type": "native", "connectivity": 8}), PRESET_METHODS, regions="ttk")
    src = cfg.source
    assert (src.regions, src.saddles) == (MethodConfig("ttk"), MethodConfig("boundary"))
    assert src.params == {"connectivity": 8}                        # shared keys carry over
    assert cfg.output == (tmp_path / "out" / "t_ttk-boundary").resolve()


def test_changed_block_loses_its_params_unchanged_block_keeps_them(tmp_path):
    cfg = _cfg(tmp_path, {"regions": {"type": "ttk", "min_score": 0.7}, "saddles": {"type": "ttk", "arrays": {}}})
    out = with_methods(cfg, PRESET_METHODS, saddles="boundary").source
    assert out.regions == MethodConfig("ttk", {"min_score": 0.7})
    assert out.saddles == MethodConfig("boundary")


def test_preset_params_that_belong_to_one_block_are_refused(tmp_path):
    cfg = _cfg(tmp_path, {"type": "ttk", "min_score": 0.7})
    with pytest.raises(ValueError, match=r"preset parameters \['min_score'\]"):
        with_methods(cfg, PRESET_METHODS, saddles="ttk")


# ------------------------------------------------------------------ run + CLI

def test_run_records_how_the_graph_was_made(tmp_path):
    cfg = _cfg(tmp_path, {"regions": "ascent", "saddles": "boundary", "connectivity": 8})
    res = run_pipeline(cfg, tmp_path / "o")
    meta = json.loads((tmp_path / "o" / "graph.json").read_text())["dataset"]
    assert meta["source"] == "ascent+boundary"
    assert meta["extraction"] == {"regions": {"method": "ascent"}, "saddles": {"method": "boundary"},
                                  "connectivity": 8, "k": 15}
    assert "source    ascent+boundary  (regions: ascent; saddles: boundary)" in res.summary()


def test_bad_pair_fails_before_anything_is_written(tmp_path):
    cfg = with_methods(_cfg(tmp_path, {"type": "native"}), PRESET_METHODS, saddles="ttk")
    with pytest.raises(ValueError, match="D-007"):
        run_pipeline(cfg)
    assert not (tmp_path / "out").exists()


def test_cli_flags_write_a_suffixed_folder(tmp_path, capsys):
    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({"name": "c", "dataset": DATASET, "output": "out/c",
                                      "source": {"type": "ttk", "connectivity": 8}}))
    assert main([str(config), "--regions", "ascent"]) == 0          # ttk preset -> ascent+boundary, no TTK needed
    meta = json.loads((tmp_path / "out" / "c_ascent-boundary" / "graph.json").read_text())["dataset"]
    assert meta["extraction"]["regions"]["method"] == "ascent" and meta["extraction"]["connectivity"] == 8
    assert not (tmp_path / "out" / "c").exists()
    assert "c_ascent-boundary" in capsys.readouterr().out


def test_cli_rejects_unknown_methods(tmp_path):
    with pytest.raises(SystemExit):
        main([str(CONFIGS / "gauss2d.yaml"), "--regions", "tachyon"])


def test_shipped_configs_still_parse_as_presets():
    for path in CONFIGS.glob("*.yaml"):
        src = load_config(path).source
        assert src.composed or src.type in PRESETS, path.name

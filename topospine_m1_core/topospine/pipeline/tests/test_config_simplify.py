"""`simplify:` in the config, --simplify on the CLI, and what a simplified run exports (D-014, D-015)."""

import json

import numpy as np
import pytest
import yaml

from topospine.cli import main
from topospine.config import SimplifyConfig, parse_config, parse_simplify, with_simplify
from topospine.run import run_pipeline
from topospine.sources.ttk_simplify import TtkSimplifier

DATASET = {"type": "synthetic", "generator": "bumps", "params": {"dims_xyz": [48, 40]}}


def _cfg(tmp_path, **extra):
    return parse_config({"name": "t", "dataset": DATASET, "output": "out/t", **extra}, tmp_path)


class Recorder:
    """A simplifier factory that never calls TTK: it flattens values above 0.5 and remembers its input."""

    def __init__(self):
        self.made, self.inputs = [], []

    def runner(self, values, spacing, origin, threshold, absolute):
        self.inputs.append(values.copy())
        return np.minimum(values, 0.5)

    def __call__(self, threshold, absolute):
        self.made.append((threshold, absolute))
        return TtkSimplifier(threshold, absolute, runner=self.runner)


# ------------------------------------------------------------------ parsing

@pytest.mark.parametrize("raw, want", [
    (None, None),
    (0.02, SimplifyConfig(0.02)),
    (1, SimplifyConfig(1.0)),
    ({"threshold": 5, "absolute": True}, SimplifyConfig(5.0, True)),
    ({"threshold": 0.1}, SimplifyConfig(0.1)),
])
def test_simplify_forms(raw, want):
    assert parse_simplify(raw) == want


@pytest.mark.parametrize("raw", [True, "0.02", {"absolute": True}, {"threshold": 0.1, "abs": True}])
def test_bad_simplify_forms(raw):
    with pytest.raises(ValueError, match="simplify"):
        parse_simplify(raw)


def test_off_by_default(tmp_path):
    assert _cfg(tmp_path).simplify is None


# ------------------------------------------------------------------ --simplify

def test_flag_sets_a_fraction_and_suffixes_the_folder(tmp_path):
    cfg = with_simplify(_cfg(tmp_path), 0.02)
    assert cfg.simplify == SimplifyConfig(0.02)
    assert cfg.output.name == "t_s0.02"


def test_flag_repeating_the_config_changes_nothing(tmp_path):
    cfg = _cfg(tmp_path, simplify=0.02)
    assert with_simplify(cfg, 0.02) is cfg
    assert with_simplify(cfg, None) is cfg


def test_flag_after_a_method_flag_stacks_suffixes(tmp_path, capsys, monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(run_pipeline, "__defaults__", (None, rec))
    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({"name": "c", "dataset": DATASET, "output": "out/c",
                                      "source": {"type": "native", "connectivity": 8}}))
    assert main([str(config), "--regions", "ascent", "--saddles", "boundary", "--simplify", "0.1"]) == 0
    assert (tmp_path / "out" / "c_s0.1" / "graph.json").exists()           # methods repeat the preset
    assert rec.made == [(0.1, False)]
    assert "simplify  0.1 of range" in capsys.readouterr().out


# ------------------------------------------------------------------ run

def test_bad_threshold_fails_before_anything_is_written(tmp_path):
    with pytest.raises(ValueError, match="simplify threshold"):
        run_pipeline(_cfg(tmp_path, simplify=1.5), simplifier_factory=Recorder())
    assert not (tmp_path / "out").exists()


def test_methods_see_and_export_the_simplified_field(tmp_path):
    rec = Recorder()
    res = run_pipeline(_cfg(tmp_path, simplify=0.05, field_encoding="float32"), tmp_path / "o", rec)
    assert res.dataset.values.max() == pytest.approx(0.5)                   # the exported field is simplified
    meta = json.loads((tmp_path / "o" / "graph.json").read_text())["dataset"]
    assert meta["simplify"]["threshold"] == 0.05 and meta["simplify"]["absolute"] is False
    assert {"maxima_before", "maxima_after"} <= set(meta["simplify"])     # counts recorded (fake: no real cut)
    assert "simplify  0.05 of range, maxima" in res.summary()


def test_minima_are_simplified_as_maxima_of_minus_f_and_exported_unflipped(tmp_path):
    rec = Recorder()
    plain = run_pipeline(_cfg(tmp_path, extremum="minima"), tmp_path / "a")
    res = run_pipeline(_cfg(tmp_path, extremum="minima", simplify=0.05), tmp_path / "b", rec)
    np.testing.assert_array_equal(rec.inputs[0], -plain.dataset.values)      # TTK got -f
    np.testing.assert_array_equal(res.dataset.values, np.maximum(plain.dataset.values, -0.5))


def test_no_simplify_records_nothing(tmp_path):
    res = run_pipeline(_cfg(tmp_path), tmp_path / "o")
    assert "simplify" not in json.loads((tmp_path / "o" / "graph.json").read_text())["dataset"]
    assert res.simplify is None and "\nsimplify  " not in res.summary()


def test_simplify_without_the_ttk_stencil_warns(tmp_path):
    with pytest.warns(UserWarning, match="connectivity: ttk"):
        run_pipeline(_cfg(tmp_path, simplify=0.05), tmp_path / "o", Recorder())


def test_simplify_with_the_ttk_stencil_is_quiet(tmp_path, recwarn):
    run_pipeline(_cfg(tmp_path, simplify=0.05, source={"type": "native", "connectivity": "ttk"}),
                 tmp_path / "o", Recorder())
    assert not [w for w in recwarn if "connectivity: ttk" in str(w.message)]

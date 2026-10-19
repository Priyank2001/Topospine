import pytest

from topospine.config import load_config
from topospine.run import run_pipeline
from tests.test_config_and_run import CONFIGS

pytest.importorskip("matplotlib")
from topospine.viz.preview2d import render_preview  # noqa: E402


@pytest.mark.parametrize("config,saturation", [("ring2d", "paper"), ("ring2d", "cancel"), ("ackley2d", "paper")])
def test_preview_renders(tmp_path, config, saturation):
    out = run_pipeline(load_config(CONFIGS / f"{config}.yaml"), tmp_path / config).output
    png = render_preview(out, p_lo=0.05, p_hi=0.9, saturation=saturation)
    assert png.stat().st_size > 10_000


def test_preview_rejects_3d(tmp_path):
    from topospine.io.synthetic import bumps_grid
    from topospine.config import parse_config

    cfg = parse_config({"name": "v", "dataset": {"type": "synthetic", "generator": "bumps",
                        "params": {"dims_xyz": [8, 8, 8], "centers": [[0.5, 0.5, 0.5]], "heights": [1]}}}, tmp_path)
    out = run_pipeline(cfg, tmp_path / "v").output
    with pytest.raises(ValueError, match="2-D"):
        render_preview(out)

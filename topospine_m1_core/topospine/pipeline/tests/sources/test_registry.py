import pytest

from topospine.io.synthetic import bumps_grid
from topospine.sources import (
    PRESETS,
    REGION_METHODS,
    SADDLE_METHODS,
    NativeSource,
    SharedResources,
    TtkSource,
    compose_source,
    make_source,
)


def test_registries_list_the_methods():
    assert sorted(REGION_METHODS) == ["ascent", "ttk"]
    assert sorted(SADDLE_METHODS) == ["boundary", "ttk"]
    assert sorted(PRESETS) == ["native", "ttk"]


@pytest.mark.parametrize("registry", [REGION_METHODS, SADDLE_METHODS])
def test_every_entry_builds_without_ttk_installed(registry):
    for name, factory in registry.items():
        assert factory(SharedResources()).name == name                  # TTK is only imported on first run


def test_composed_ascent_boundary_equals_the_native_preset():
    g = bumps_grid((40, 30), centers=[[0.2, 0.3], [0.7, 0.7]], heights=[1.0, 0.8], width=0.1)
    src = compose_source("ascent", "boundary", connectivity=4)
    assert src.name == "ascent+boundary"
    a, b = src.compute(g), NativeSource(connectivity=4).compute(g)
    assert a.labels.tolist() == b.labels.tolist() and a.graph.arcs.tolist() == b.graph.arcs.tolist()


def test_ttk_blocks_of_one_run_share_one_backend():
    src = compose_source("ttk", "ttk")
    assert src.regions.backend is src.saddles.backend                 # one TTK run per dataset
    assert compose_source("ttk", "ttk").regions.backend is not src.regions.backend   # runs don't share


def test_disallowed_pair_is_rejected():
    with pytest.raises(ValueError, match="D-007"):
        compose_source("ascent", "ttk")


@pytest.mark.parametrize("regions, saddles, match", [
    ("tachyon", "boundary", r"unknown region method 'tachyon'; choose from \['ascent', 'ttk'\]"),
    ("ascent", "exact", r"unknown saddle method 'exact'; choose from \['boundary', 'ttk'\]"),
])
def test_unknown_method_names(regions, saddles, match):
    with pytest.raises(ValueError, match=match):
        compose_source(regions, saddles)


def test_bad_parameters_name_the_method():
    with pytest.raises(ValueError, match="bad parameters for region method 'ttk'"):
        compose_source("ttk", "boundary", regions_params={"min_scor": 0.9})


def test_parameters_reach_the_blocks():
    src = compose_source("ttk", "ttk", regions_params={"min_score": 0.9, "candidates": ["AscendingManifold"]},
                         saddles_params={"arrays": {"separatrix_type": "Kind"}}, connectivity=6, k=9)
    assert (src.regions.min_score, src.regions.candidates) == (0.9, ("AscendingManifold",))
    assert src.saddles.arrays.separatrix_type == "Kind"                # YAML mapping -> TtkArrayNames
    assert (src.connectivity, src.k) == (6, 9)


def test_presets_keep_old_configs_working():
    assert isinstance(make_source("native", k=5), NativeSource)
    ttk = make_source("ttk", connectivity=26, min_score=0.7)
    assert isinstance(ttk, TtkSource) and ttk.name == "ttk"
    with pytest.raises(ValueError, match="unknown source"):
        make_source("ascent")                                          # methods are not presets

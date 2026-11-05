"""Run configuration: one YAML file per dataset, so every result is one command away.

Relative paths inside a config are resolved against the config file's own directory,
so `configs/foo.yaml` works no matter where you run the CLI from.

Example
-------
name: gauss2d
dataset:
  type: synthetic          # synthetic | raw | npy | vti | csv | points_npy
  generator: bumps         # synthetic only
  params: {dims_xyz: [128, 128]}
extremum: maxima           # maxima | minima
source: {type: native, connectivity: 8}   # a preset: native | ttk
# connectivity: a stencil size (2-D 4|8, 3-D 6|18|26) or `ttk` = TTK's mesh (D-016)
# or pick the two blocks of extraction yourself (docs/DECISIONS.md D-004):
# source: {regions: ttk, saddles: {type: ttk}, connectivity: 26}
simplify: 0.02            # optional (D-014/D-015): drop features below 2 % of the value range
# simplify: {threshold: 5.0, absolute: true}   # or in raw field units; use with connectivity: ttk
histogram_bins: 64
field_encoding: uint8
output: ../out/gauss2d
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

DATASET_TYPES = {"synthetic", "raw", "npy", "vti", "csv", "points_npy"}


@dataclass(frozen=True)
class DatasetConfig:
    type: str
    path: Path | None = None
    generator: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


SHARED_SOURCE_KEYS = ("connectivity", "k")   # neighbourhood settings both blocks share


@dataclass(frozen=True)
class MethodConfig:
    """One block of extraction: a method name from the registry and its parameters."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceConfig:
    """Either a preset (`type` + its params) or two blocks (`regions`, `saddles`).

    For two blocks, `params` holds only the shared keys (connectivity, k) and `type` is None.
    """

    type: str | None = "native"
    params: dict[str, Any] = field(default_factory=dict)
    regions: MethodConfig | None = None
    saddles: MethodConfig | None = None

    @property
    def composed(self) -> bool:
        return self.regions is not None


@dataclass(frozen=True)
class SimplifyConfig:
    """TTK persistence simplification before extraction (D-014, D-015).

    `threshold` is a fraction of the value range unless `absolute`; its range is checked
    by TtkSimplifier, the one place that knows what the number means.
    """

    threshold: float
    absolute: bool = False


@dataclass(frozen=True)
class RunConfig:
    name: str
    dataset: DatasetConfig
    source: SourceConfig
    output: Path
    extremum: str = "maxima"
    histogram_bins: int = 64
    field_encoding: str = "uint8"
    simplify: SimplifyConfig | None = None


def parse_config(raw: dict[str, Any], base_dir: Path) -> RunConfig:
    def resolve(p: str | None) -> Path | None:
        if p is None:
            return None
        path = Path(p).expanduser()
        return path if path.is_absolute() else (base_dir / path).resolve()

    if "name" not in raw or "dataset" not in raw:
        raise ValueError("config needs at least `name` and `dataset`")
    ds = dict(raw["dataset"])
    ds_type = ds.pop("type", None)
    if ds_type not in DATASET_TYPES:
        raise ValueError(f"dataset.type must be one of {sorted(DATASET_TYPES)}, got {ds_type!r}")
    path = resolve(ds.pop("path", None))
    generator = ds.pop("generator", None)
    params = dict(ds.pop("params", {}))
    params.update(ds)  # allow params inline next to `type`
    if ds_type == "synthetic" and not generator:
        raise ValueError("synthetic datasets need `generator`")
    if ds_type != "synthetic" and path is None:
        raise ValueError(f"dataset type {ds_type!r} needs `path`")

    extremum = raw.get("extremum", "maxima")
    if extremum not in ("maxima", "minima"):
        raise ValueError("extremum must be 'maxima' or 'minima'")
    encoding = raw.get("field_encoding", "uint8")
    if encoding not in ("uint8", "float32"):
        raise ValueError("field_encoding must be 'uint8' or 'float32'")
    bins = int(raw.get("histogram_bins", 64))
    if bins < 1:
        raise ValueError("histogram_bins must be positive")

    return RunConfig(
        name=str(raw["name"]),
        dataset=DatasetConfig(ds_type, path, generator, params),
        source=parse_source(raw.get("source", {})),
        output=resolve(raw.get("output", f"../out/{raw['name']}")),
        extremum=extremum,
        histogram_bins=bins,
        field_encoding=encoding,
        simplify=parse_simplify(raw.get("simplify")),
    )


def parse_simplify(raw: Any) -> SimplifyConfig | None:
    """`simplify: 0.02` or `simplify: {threshold: 5, absolute: true}`; absent or null = off."""
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, Mapping)):
        raise ValueError(f"simplify must be a number or {{threshold, absolute}}, got {raw!r}")
    if not isinstance(raw, Mapping):
        return SimplifyConfig(float(raw))
    extra = sorted(set(raw) - {"threshold", "absolute"})
    if extra or "threshold" not in raw:
        raise ValueError(f"simplify needs `threshold` (and optionally `absolute`); unknown keys {extra}")
    return SimplifyConfig(float(raw["threshold"]), bool(raw.get("absolute", False)))


def _method(raw: Any, block: str) -> MethodConfig:
    if isinstance(raw, str):
        return MethodConfig(raw)
    if not isinstance(raw, Mapping) or "type" not in raw:
        raise ValueError(f"source.{block} must be a method name or a mapping with `type`")
    m = dict(raw)
    kind = str(m.pop("type"))
    params = dict(m.pop("params", {}))
    params.update(m)                       # allow params inline next to `type`
    return MethodConfig(kind, params)


def parse_source(raw: Mapping[str, Any]) -> SourceConfig:
    src = dict(raw)
    params = dict(src.pop("params", {}))
    params.update({k: v for k, v in src.items() if k not in ("type", "regions", "saddles")})
    has_blocks = "regions" in src or "saddles" in src
    if not has_blocks:
        return SourceConfig(str(src.get("type", "native")), params)
    if "type" in src:
        raise ValueError("source: give either a preset `type` or `regions` + `saddles`, not both")
    if "regions" not in src or "saddles" not in src:
        raise ValueError("source: `regions` and `saddles` go together")
    extra = sorted(set(params) - set(SHARED_SOURCE_KEYS))
    if extra:
        raise ValueError(f"source: unknown keys {extra}; method parameters go under "
                         f"`regions:` / `saddles:`, shared ones are {list(SHARED_SOURCE_KEYS)}")
    return SourceConfig(None, params, _method(src["regions"], "regions"), _method(src["saddles"], "saddles"))


def with_methods(cfg: RunConfig, preset_methods: Mapping[str, tuple[str, str]],
                 regions: str | None = None, saddles: str | None = None) -> RunConfig:
    """Override the config's methods (the --regions / --saddles flags, D-006).

    A block whose method changes loses its YAML parameters; an unchanged block keeps them.
    If a method changed, the output folder gets a `_<regions>-<saddles>` suffix so runs of
    different combinations never overwrite each other. A preset config becomes two blocks;
    only its shared keys (connectivity, k) carry over, since the others belong to one block.
    """
    if regions is None and saddles is None:
        return cfg
    src = cfg.source
    if src.composed:
        assert src.regions is not None and src.saddles is not None
        cur_r, cur_s = src.regions, src.saddles
    else:
        if src.type not in preset_methods:
            raise ValueError(f"unknown source {src.type!r}; choose from {sorted(preset_methods)}")
        own = sorted(set(src.params) - set(SHARED_SOURCE_KEYS))
        if own:
            raise ValueError(f"preset parameters {own} can't be carried into --regions/--saddles; "
                             "write the config's source as `regions:` + `saddles:` instead")
        r, s = preset_methods[src.type]
        cur_r, cur_s = MethodConfig(r), MethodConfig(s)
    new_r = cur_r if regions in (None, cur_r.type) else MethodConfig(regions)
    new_s = cur_s if saddles in (None, cur_s.type) else MethodConfig(saddles)
    if (new_r, new_s) == (cur_r, cur_s):
        return cfg                                            # flags repeat the config: nothing changed
    shared = {k: v for k, v in src.params.items() if k in SHARED_SOURCE_KEYS}
    output = cfg.output.with_name(f"{cfg.output.name}_{new_r.type}-{new_s.type}")
    return replace(cfg, source=SourceConfig(None, shared, new_r, new_s), output=output)


def with_simplify(cfg: RunConfig, threshold: float | None) -> RunConfig:
    """Override the config's simplification (the --simplify flag, a fraction of the range).

    If it changes anything, the output folder gets a `_s<threshold>` suffix (e.g. `_s0.02`)
    so simplified and unsimplified runs never overwrite each other.
    """
    if threshold is None:
        return cfg
    new = SimplifyConfig(float(threshold))
    if new == cfg.simplify:
        return cfg
    return replace(cfg, simplify=new, output=cfg.output.with_name(f"{cfg.output.name}_s{new.threshold:g}"))


def load_config(path: str | Path) -> RunConfig:
    path = Path(path).resolve()
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return parse_config(raw, path.parent)

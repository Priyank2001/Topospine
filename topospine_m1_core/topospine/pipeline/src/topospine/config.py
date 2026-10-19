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
source: {type: native, connectivity: 8}
histogram_bins: 64
field_encoding: uint8
output: ../out/gauss2d
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class SourceConfig:
    type: str = "native"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunConfig:
    name: str
    dataset: DatasetConfig
    source: SourceConfig
    output: Path
    extremum: str = "maxima"
    histogram_bins: int = 64
    field_encoding: str = "uint8"


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

    src = dict(raw.get("source", {}))
    src_type = src.pop("type", "native")
    src_params = dict(src.pop("params", {}))
    src_params.update(src)

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
        source=SourceConfig(src_type, src_params),
        output=resolve(raw.get("output", f"../out/{raw['name']}")),
        extremum=extremum,
        histogram_bins=bins,
        field_encoding=encoding,
    )


def load_config(path: str | Path) -> RunConfig:
    path = Path(path).resolve()
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return parse_config(raw, path.parent)

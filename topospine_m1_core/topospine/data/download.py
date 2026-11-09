#!/usr/bin/env python3
"""Download Klacansky's Open SciVis Datasets and cut 2-D scalar fields out of them.

The catalogue (http://klacansky.com/open-scivis-datasets/) only holds 3-D volumes, so each
download is a headerless .raw volume (x fastest) from which one axis-aligned slice is saved
as a 2-D .npy plus a pipeline config next to the other configs.

    python download.py                      # default set, middle z-slice
    python download.py --list               # catalogue with sizes
    python download.py fuel neghip          # chosen datasets
    python download.py tooth --axis y --index 40
    python download.py --keep-raw           # keep the full volumes in data/raw/

Layout written
    data/raw/<name>/...raw              only with --keep-raw (deleted after slicing otherwise)
    data/slices/<name>_<axis><index>.npy  2-D float arrays, shape (rows, cols)
    pipeline/configs/klacansky_<name>.yaml

The server refuses HTTPS from some networks, so plain HTTP is used; integrity comes from
the SHA-512 sums in datasets.json. Standard library + NumPy only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

BASE = "http://klacansky.com/open-scivis-datasets/"
CATALOGUE = BASE + "datasets.json"

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
SLICE_DIR = HERE / "slices"
CONFIG_DIR = HERE.parent / "pipeline" / "configs"

# Small volumes (< 30 MB each); chosen to give varied 2-D scalar fields.
DEFAULTS = [
    "fuel", "neghip", "hydrogen_atom", "marschner_lobb", "nucleon", "silicium", "tooth",
    "blunt_fin", "engine", "lobster", "frog", "aneurism", "bonsai", "foot", "skull",
]
AXES = {"x": 2, "y": 1, "z": 0}      # numpy axis of the (z, y, x) array


def fetch(url: str, dest: Path, expected_sha512: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and sha512(dest) == expected_sha512:
        print(f"  have {dest.name} (checksum ok)")
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {dest.name}: {done / 1e6:.1f}/{total / 1e6:.1f} MB", end="", flush=True)
    print()
    if sha512(tmp) != expected_sha512:
        tmp.unlink()
        raise RuntimeError(f"{dest.name}: SHA-512 mismatch, download discarded")
    tmp.replace(dest)


def sha512(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def cut_slice(raw: Path, dims_xyz: list[int], dtype: str, axis: str, index: int | None) -> tuple[np.ndarray, int]:
    vol = np.fromfile(raw, dtype=np.dtype(dtype).newbyteorder("<")).reshape(dims_xyz[::-1])
    ax = AXES[axis]
    idx = vol.shape[ax] // 2 if index is None else index
    if not 0 <= idx < vol.shape[ax]:
        raise ValueError(f"--index {idx} outside 0..{vol.shape[ax] - 1} for axis {axis}")
    return np.take(vol, idx, axis=ax).astype(np.float64), idx


def write_config(name: str, npy: Path, spacing_xy: list[float]) -> Path:
    cfg = CONFIG_DIR / f"klacansky_{name}.yaml"
    rel = Path("..") / ".." / "data" / "slices" / npy.name
    cfg.write_text(
        f"# 2-D slice of Klacansky's `{name}` volume (made by data/download.py)\n"
        f"name: klacansky_{name}\n"
        "dataset:\n"
        "  type: npy\n"
        f"  path: {rel}\n"
        f"  spacing_xyz: {spacing_xy}\n"
        "extremum: maxima\n"
        "source: {type: native, connectivity: 8}\n"
        f"output: ../out/klacansky_{name}\n"
    )
    return cfg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help=f"dataset keys (default: {' '.join(DEFAULTS)})")
    ap.add_argument("--list", action="store_true", help="print the catalogue and exit")
    ap.add_argument("--axis", choices=AXES, default="z", help="slice axis (default z)")
    ap.add_argument("--index", type=int, default=None, help="slice index (default: middle)")
    ap.add_argument("--keep-raw", action="store_true", help="keep the full .raw volumes")
    args = ap.parse_args()

    with urllib.request.urlopen(CATALOGUE, timeout=60) as resp:
        catalogue: dict = json.load(resp)

    if args.list:
        for key, d in catalogue.items():
            mb = np.prod(d["size"]) * np.dtype(d["type"]).itemsize / 1e6
            print(f"{key:28s} {'x'.join(map(str, d['size'])):16s} {d['type']:8s} {mb:10.1f} MB  {d['category']}")
        return 0

    names = args.names or DEFAULTS
    unknown = [n for n in names if n not in catalogue]
    if unknown:
        print(f"unknown dataset(s): {unknown}; see --list", file=sys.stderr)
        return 2

    SLICE_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for name in names:
        d = catalogue[name]
        print(f"{name}: {d['size']} {d['type']}")
        raw = RAW_DIR / name / Path(d["url"]).name
        try:
            fetch(d["url"], raw, d["sha512sum"])
            sl, idx = cut_slice(raw, d["size"], d["type"], args.axis, args.index)
        except Exception as exc:                      # keep going; report at the end
            print(f"  FAILED: {exc}", file=sys.stderr)
            failed.append(name)
            continue
        npy = SLICE_DIR / f"{name}_{args.axis}{idx}.npy"
        np.save(npy, sl)
        keep = [s for i, s in zip("xyz", d.get("spacing", [1, 1, 1])) if i != args.axis]
        cfg = write_config(name, npy, keep)
        print(f"  slice {sl.shape} -> {npy.relative_to(HERE.parent)}; config {cfg.relative_to(HERE.parent)}")
        if not args.keep_raw:
            raw.unlink()
            raw.parent.rmdir()
    if failed:
        print(f"failed: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Command line: python -m topospine.cli configs/gauss2d.yaml [--out DIR] [--preview]
                                     [--regions ascent|ttk] [--saddles boundary|ttk] [--simplify T]

--regions / --saddles override the config's methods (DECISIONS.md D-006); the output folder
then gets a `_<regions>-<saddles>` suffix unless --out names it explicitly.
--simplify T removes features below T x the value range with TTK first (D-014, D-015);
the folder gets a `_s<T>` suffix, again unless --out.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from topospine.config import load_config, with_methods, with_simplify
from topospine.run import run_pipeline
from topospine.sources import PRESET_METHODS, REGION_METHODS, SADDLE_METHODS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="topospine", description="Compute and export an extremum graph.")
    ap.add_argument("config", type=Path, help="YAML run configuration")
    ap.add_argument("--out", type=Path, default=None, help="override the output directory")
    ap.add_argument("--preview", action="store_true", help="also write preview.png (2-D datasets only)")
    ap.add_argument("--p-lo", type=float, default=0.0, help="noise threshold for the preview")
    ap.add_argument("--p-hi", type=float, default=float("inf"), help="variation threshold for the preview")
    ap.add_argument("--saturation", choices=["paper", "cancel"], default="paper",
                    help="which P* the preview uses (see docs/DEVIATIONS.md #8)")
    ap.add_argument("--regions", choices=sorted(REGION_METHODS), default=None,
                    help="region method, overriding the config")
    ap.add_argument("--saddles", choices=sorted(SADDLE_METHODS), default=None,
                    help="saddle method, overriding the config")
    ap.add_argument("--simplify", type=float, default=None, metavar="T",
                    help="simplify first: drop features below T x value range (needs TTK)")
    args = ap.parse_args(argv)

    cfg = with_methods(load_config(args.config), PRESET_METHODS, args.regions, args.saddles)
    cfg = with_simplify(cfg, args.simplify)
    result = run_pipeline(cfg, args.out)
    print(result.summary())

    if args.preview:
        from topospine.viz.preview2d import render_preview   # matplotlib only when asked

        png = render_preview(result.output, p_lo=args.p_lo, p_hi=args.p_hi, saturation=args.saturation)
        print(f"preview   {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

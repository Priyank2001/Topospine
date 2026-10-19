"""Render preview.png for a 2-D export directory.

    python scripts/preview_2d.py out/ring2d --p-lo 0.05 --p-hi 0.9 [--saturation cancel] [--out fig.png]
"""

import argparse
from pathlib import Path

from topospine.viz.preview2d import render_preview

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir", type=Path)
    ap.add_argument("--p-lo", type=float, default=0.0)
    ap.add_argument("--p-hi", type=float, default=float("inf"))
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--saturation", choices=["paper", "cancel"], default="paper")
    a = ap.parse_args()
    print(render_preview(a.export_dir, a.p_lo, a.p_hi, a.out, a.saturation))

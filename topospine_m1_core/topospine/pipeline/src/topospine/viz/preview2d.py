"""2-D preview of an export directory: regions, extremum graph, persistence curves.

Reads only what the web app will read (graph.json + binaries), so a correct preview
also validates the file contract. Left panel: regions at p_lo (coloured), contour
lines, and G_R for R = [p_lo, p_hi] drawn straight saddle-to-extremum, in the style
of the paper's Fig. 2b. Right panel: the persistence (blue) and variation (red)
curves of Fig. 8b with the chosen thresholds marked.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from topospine.core.extremum_graph import arc_curve, extrema_curve, filter_graph, representatives
from topospine.core.graph import NodeKind
from topospine.core.persistence import Persistence
from topospine.io.exporter import read_export


def _region_colors(rep_labels: np.ndarray):
    import matplotlib.pyplot as plt

    palette = plt.get_cmap("tab20").colors
    ids, compact = np.unique(rep_labels, return_inverse=True)
    return np.array(palette)[compact % len(palette)]


def render_preview(export_dir: str | Path, p_lo: float = 0.0, p_hi: float = np.inf,
                   out_png: str | Path | None = None, saturation: str = "paper") -> Path:
    """saturation: "paper" uses Algorithm 1's P*, "cancel" the cancellation-only variant."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    b = read_export(export_dir)
    meta = b.meta
    is_grid = meta["kind"] == "grid"
    if (is_grid and len(meta["grid"]["dimsXYZ"]) != 2) or (not is_grid and meta["points"]["dim"] != 2):
        raise ValueError("preview supports 2-D grids and 2-D point sets only")

    if saturation not in ("paper", "cancel"):
        raise ValueError("saturation must be 'paper' or 'cancel'")
    pers = b.persistence
    if saturation == "cancel":
        pers = Persistence(pers.persistence, pers.saturated_cancel, pers.merged_into, pers.saturated_cancel)
    rep = representatives(pers, p_lo)[b.labels]
    colors = _region_colors(rep)
    tg = filter_graph(b.graph, pers, p_lo, p_hi)
    pos = b.positions[:, :2]

    fig, (ax, axc) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1.3, 1]})
    if is_grid:
        nx, ny = meta["grid"]["dimsXYZ"]
        (ox, oy), (sx, sy) = meta["grid"]["originXYZ"], meta["grid"]["spacingXYZ"]
        extent = [ox, ox + (nx - 1) * sx, oy, oy + (ny - 1) * sy]
        ax.imshow(colors.reshape(ny, nx, 3), origin="lower", extent=extent, alpha=0.55, interpolation="nearest")
        ax.contour(np.linspace(extent[0], extent[1], nx), np.linspace(extent[2], extent[3], ny),
                   b.field, levels=15, colors="k", linewidths=0.4, alpha=0.6)
    else:
        ax.scatter(b.points[:, 0], b.points[:, 1], c=colors, s=4, linewidths=0)

    for (s, m), keep in zip(b.graph.arcs, tg.arc_mask):
        if keep:
            ax.plot(*pos[[s, m]].T, color="k", lw=1.2, zorder=3)
    is_max = b.graph.kinds == NodeKind.MAXIMUM
    label = "minima" if meta["extremum"] == "minima" else "maxima"
    ax.scatter(*pos[is_max & tg.node_mask].T, s=40, c="crimson", edgecolors="k", zorder=4, label=label)
    ax.scatter(*pos[~is_max & tg.node_mask].T, s=22, c="white", edgecolors="k", zorder=4, label="saddles")
    ax.set_aspect("equal")
    ax.set_title(f"{meta['name']}: R = [{p_lo:g}, {p_hi:g}], P* = {saturation}")
    ax.legend(loc="upper right", fontsize=8)

    P = b.persistence.persistence
    pmax = float(np.nanmax(np.where(np.isfinite(P), P, np.nan))) if np.isfinite(P).any() else 1.0
    t = np.linspace(0, pmax * 1.05, 400)
    axc.step(t, extrema_curve(b.graph, b.persistence, t), where="post", color="tab:blue", label="extrema vs p_lo")
    axc.set_xlabel("persistence threshold")
    axc.set_ylabel("number of extrema", color="tab:blue")
    ax2 = axc.twinx()
    ax2.step(t, arc_curve(b.graph, b.persistence, t), where="post", color="tab:red", label="arcs vs p_hi")
    ax2.set_ylabel("number of arcs", color="tab:red")
    axc.axvline(p_lo, color="tab:blue", ls="--", lw=0.8)
    if np.isfinite(p_hi):
        ax2.axvline(p_hi, color="tab:red", ls="--", lw=0.8)
    axc.set_title("persistence (blue) and variation (red) plots")

    fig.tight_layout()
    out = Path(out_png) if out_png else Path(export_dir) / "preview.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out

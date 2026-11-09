#!/usr/bin/env python3
"""
hd_extremum_graph.py  (v1)

Extremum graph, persistence and merge tree of a scalar field sampled on a
high-dimensional point cloud (for example 300 dimensions).

Idea (same family as Topospine / HDViz style methods)
    1. Build a symmetrised k-nearest-neighbour graph in the FULL space
       (approximate search, because exact KD-trees degrade at high dimension).
    2. Steepest ascent on that graph: every point links to its highest neighbour.
       Points that end at the same local maximum form one region.
    3. For every pair of touching regions the saddle is the highest boundary
       edge, taken as the lower endpoint of the edge that maximises min(f(u), f(v)).
    4. Persistence of each maximum comes from a union-find sweep over the saddles
       (elder rule). This is exact for the superlevel-set components of the graph,
       and it also yields the merge (split) tree on the extremum graph.
    5. Simplify by a persistence threshold and export.

Input
    .npy   array of shape (n, d+1), scalar value in the LAST column
    .csv   header row; scalar in --value-column (default: last column)
    .npz   arrays "X" (n, d) and "f" (n,)

Output (in --out)
    result.npz     labels, simplified_labels, maxima table, graph arrays
    graph.json     simplified extremum graph + merge tree (original row indices)
    maxima.csv     one row per surviving extremum

Dependencies
    required: numpy
    optional: pynndescent (fast approximate kNN, recommended for n > 50k),
              scikit-learn (exact kNN fallback). A chunked NumPy brute force is
              the last fallback and is only sensible for a few tens of thousands
              of points.

Usage
    python hd_extremum_graph.py data.npy --k 20 --persistence 0.05 --out out/run1
    python hd_extremum_graph.py data.csv --value-column loss --mode min
    python hd_extremum_graph.py data.npy --stability 10,20,30
    python hd_extremum_graph.py --selftest

Notes
    * Values are made distinct by breaking ties with the row index, so plateaus
      and repeated values are safe.
    * Nothing here claims the graph topology equals the topology of the
      underlying continuous field. In high dimensions it is an approximation
      that depends on k, the sampling density and the scaling of the features.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------------- #
# Input and preprocessing
# --------------------------------------------------------------------------- #

def load_points(path, value_column=None, delimiter=","):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".npy":
        table = np.load(path).astype(np.float64)
        if table.ndim != 2 or table.shape[1] < 2:
            raise ValueError("expected an (n, d+1) array with the value in the last column")
        return table[:, :-1], table[:, -1]
    if suffix == ".npz":
        z = np.load(path)
        return np.asarray(z["X"], dtype=np.float64), np.asarray(z["f"], dtype=np.float64)
    if suffix == ".csv":
        with path.open() as fh:
            header = [h.strip() for h in fh.readline().split(delimiter)]
        table = np.loadtxt(path, delimiter=delimiter, skiprows=1, ndmin=2)
        col = value_column or header[-1]
        if col not in header:
            raise ValueError(f"value column {col!r} not in header {header}")
        j = header.index(col)
        keep = [i for i in range(len(header)) if i != j]
        return table[:, keep], table[:, j]
    raise ValueError(f"unsupported input type {suffix!r}")


def prepare(X, f, standardize=True, pca_dims=None, dedupe=True):
    """Drop non-finite rows, constant columns and duplicates; optionally scale and
    run PCA. Returns (X2, f2, kept) where kept maps rows of X2 to rows of the input."""
    X = np.asarray(X, dtype=np.float64)
    f = np.asarray(f, dtype=np.float64)
    kept = np.arange(len(X))

    good = np.isfinite(X).all(axis=1) & np.isfinite(f)
    if not good.all():
        print(f"[prepare] dropping {int((~good).sum())} rows with non-finite values")
        X, f, kept = X[good], f[good], kept[good]

    std = X.std(axis=0)
    live = std > 0
    if not live.all():
        print(f"[prepare] dropping {int((~live).sum())} constant columns")
        X = X[:, live]
        std = std[live]

    if standardize:
        X = (X - X.mean(axis=0)) / std

    if pca_dims is not None and pca_dims < X.shape[1]:
        Xc = X - X.mean(axis=0)
        cov = (Xc.T @ Xc) / max(len(Xc) - 1, 1)
        w, V = np.linalg.eigh(cov)
        V = V[:, np.argsort(w)[::-1][:pca_dims]]
        X = Xc @ V
        print(f"[prepare] PCA to {pca_dims} dimensions")

    if dedupe:
        _, first = np.unique(X, axis=0, return_index=True)
        if len(first) < len(X):
            first = np.sort(first)
            print(f"[prepare] dropping {len(X) - len(first)} duplicate rows (keeping first)")
            X, f, kept = X[first], f[first], kept[first]

    return X, f, kept


# --------------------------------------------------------------------------- #
# k-nearest-neighbour graph
# --------------------------------------------------------------------------- #

def _drop_self(idx, k):
    n = idx.shape[0]
    if idx.min() < 0:
        raise RuntimeError("neighbour search returned missing neighbours; increase k or sample size")
    mask = idx != np.arange(n)[:, None]
    full = mask.sum(axis=1) == k + 1            # self absent from its own list
    mask[full, -1] = False
    if (mask.sum(axis=1) != k).any():
        raise RuntimeError("neighbour list inconsistent (repeated self index)")
    return idx[mask].reshape(n, k).astype(np.int64)


def _knn_brute(X, k, chunk=2048):
    n = len(X)
    sq = (X * X).sum(axis=1)
    out = np.empty((n, k + 1), dtype=np.int64)
    for s in range(0, n, chunk):
        e = min(s + chunk, n)
        d2 = sq[s:e, None] - 2.0 * (X[s:e] @ X.T) + sq[None, :]
        part = np.argpartition(d2, k, axis=1)[:, : k + 1]
        out[s:e] = part
    return _drop_self(out, k)


def knn_graph(X, k, backend="auto", seed=0):
    """Return an (n, k) array of neighbour indices (self excluded)."""
    n = len(X)
    if not 1 <= k < n:
        raise ValueError(f"need 1 <= k < n, got k={k}, n={n}")
    if backend in ("auto", "pynndescent"):
        try:
            from pynndescent import NNDescent
            index = NNDescent(X.astype(np.float32), n_neighbors=k + 1,
                              metric="euclidean", random_state=seed)
            print("[knn] pynndescent (approximate)")
            return _drop_self(index.neighbor_graph[0], k)
        except ImportError:
            if backend == "pynndescent":
                raise
    if backend in ("auto", "sklearn"):
        try:
            from sklearn.neighbors import NearestNeighbors
            print("[knn] scikit-learn (exact)")
            idx = NearestNeighbors(n_neighbors=k + 1).fit(X).kneighbors(X, return_distance=False)
            return _drop_self(idx, k)
        except ImportError:
            if backend == "sklearn":
                raise
    print("[knn] NumPy brute force (exact, O(n^2 d))")
    return _knn_brute(X, k)


# --------------------------------------------------------------------------- #
# Core algorithm
# --------------------------------------------------------------------------- #

def _scatter_max(n, keys, vals, init):
    """out[i] = max(init[i], max of vals[keys == i])  (vectorised, no ufunc.at)."""
    out = init.copy()
    o = np.argsort(keys, kind="stable")
    kk, vv = keys[o], vals[o]
    starts = np.flatnonzero(np.r_[True, kk[1:] != kk[:-1]])
    m = np.maximum.reduceat(vv, starts)
    uk = kk[starts]
    out[uk] = np.maximum(out[uk], m)
    return out


def _best_per_pair(a, b, lr, M):
    """For each unordered label pair (a, b) keep the entry with the largest lr."""
    key = a.astype(np.int64) * M + b
    o = np.lexsort((lr, key))
    ko = key[o]
    last = np.flatnonzero(np.r_[ko[1:] != ko[:-1], True])
    return o[last]


def extremum_graph(X, f, k=20, mode="max", persistence_frac=0.05,
                   backend="auto", knn_idx=None, seed=0):
    """
    Compute the extremum graph of f on the kNN graph of X.

    mode = "max" uses maxima and superlevel sets, mode = "min" negates f.
    persistence_frac is the simplification threshold as a fraction of the range of f.
    """
    n = len(X)
    f = np.asarray(f, dtype=np.float64)
    sign = 1.0 if mode == "max" else -1.0
    g = sign * f

    t0 = time.time()
    idx = knn_idx if knn_idx is not None else knn_graph(X, k, backend, seed)
    k = idx.shape[1]
    print(f"[graph] n={n}, k={k}, kNN in {time.time() - t0:.1f}s")

    # Total order on vertices: by value, ties broken by index (so all values are distinct).
    order = np.lexsort((np.arange(n), g))          # ascending
    rank = np.empty(n, dtype=np.int64)
    rank[order] = np.arange(n)

    src = np.repeat(np.arange(n, dtype=np.int64), k)
    dst = idx.ravel()

    # Steepest ascent on the symmetrised graph.
    top = np.maximum(rank, rank[idx].max(axis=1))
    top = _scatter_max(n, dst, rank[src], top)
    up = order[top]
    root = up.copy()
    while True:
        nxt = root[root]
        if np.array_equal(nxt, root):
            break
        root = nxt

    maxima = np.flatnonzero(up == np.arange(n))
    M = len(maxima)
    cid = np.full(n, -1, dtype=np.int64)
    cid[maxima] = np.arange(M)
    labels = cid[root]
    mrank = rank[maxima]

    # Region boundaries -> one saddle per pair of touching regions.
    ls, ld = labels[src], labels[dst]
    cross = ls != ld
    s, d = src[cross], dst[cross]
    lr = np.minimum(rank[s], rank[d])               # rank of the saddle vertex
    a = np.minimum(ls[cross], ld[cross])
    b = np.maximum(ls[cross], ld[cross])
    if len(a):
        sel = _best_per_pair(a, b, lr, M)
        pa, pb, plr = a[sel], b[sel], lr[sel]
    else:
        pa = pb = plr = np.empty(0, dtype=np.int64)

    # Persistence by union-find over saddles in decreasing order (elder rule).
    uf = np.arange(M)
    comp_top = np.arange(M)
    pers = np.full(M, np.nan)
    parent = np.full(M, -1, dtype=np.int64)
    death_saddle = np.full(M, -1, dtype=np.int64)

    def find(x):
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    for e in np.argsort(-plr, kind="stable"):
        ra, rb = find(pa[e]), find(pb[e])
        if ra == rb:
            continue
        ta, tb = comp_top[ra], comp_top[rb]
        die, surv = (ta, tb) if mrank[ta] < mrank[tb] else (tb, ta)
        sv = order[plr[e]]
        pers[die] = g[maxima[die]] - g[sv]
        parent[die] = surv
        death_saddle[die] = sv
        uf[ra] = rb
        comp_top[rb] = surv

    grange = float(g.max() - g.min())
    essential = np.isnan(pers)
    pers[essential] = g[maxima[essential]] - g.min()   # one per connected component
    n_components = int(essential.sum())
    if n_components > 1:
        print(f"[graph] WARNING: kNN graph has {n_components} connected components; "
              f"increase k")

    # Simplification: dropped maxima fold into the maximum they merge with.
    thr = persistence_frac * grange
    keep = pers >= thr
    rep = np.where(keep, np.arange(M), parent)
    for m in range(M):
        while rep[m] >= 0 and not keep[rep[m]]:
            rep[m] = parent[rep[m]]
    rep = np.where(rep < 0, np.arange(M), rep)
    simplified_labels = rep[labels]

    # Simplified extremum graph: pair graph with endpoints mapped to survivors.
    if len(pa):
        ra_, rb_ = rep[pa], rep[pb]
        ok = ra_ != rb_
        A = np.minimum(ra_[ok], rb_[ok])
        B = np.maximum(ra_[ok], rb_[ok])
        if len(A):
            sel2 = _best_per_pair(A, B, plr[ok], M)
            ga, gb, glr = A[sel2], B[sel2], plr[ok][sel2]
        else:
            ga = gb = glr = np.empty(0, dtype=np.int64)
    else:
        ga = gb = glr = np.empty(0, dtype=np.int64)

    print(f"[graph] {M} raw extrema, {int(keep.sum())} kept at persistence >= {thr:.4g} "
          f"({persistence_frac:.1%} of range)")

    return {
        "mode": mode, "k": int(k), "n": int(n), "threshold": float(thr),
        "labels": labels, "simplified_labels": simplified_labels,
        "maxima_vertex": maxima, "maxima_value": f[maxima],
        "persistence": pers, "parent": parent, "death_saddle": death_saddle,
        "keep": keep, "representative": rep,
        "region_size": np.bincount(labels, minlength=M),
        "pair_a": pa, "pair_b": pb, "pair_saddle": order[plr] if len(plr) else plr,
        "graph_a": ga, "graph_b": gb, "graph_saddle": order[glr] if len(glr) else glr,
        "n_components": n_components, "_order": order, "_idx": idx,
        "_g": g,
    }


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #

def export(res, f, kept, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    keep = res["keep"]
    ids = np.flatnonzero(keep)
    mv = res["maxima_vertex"]

    def row(v):                       # original row index in the input file
        return int(kept[v])

    nodes = [{
        "id": int(i), "row": row(mv[i]), "value": float(f[mv[i]]),
        "persistence": float(res["persistence"][i]),
        "region_size": int(np.sum(res["simplified_labels"] == i)),
    } for i in ids]

    arcs = [{
        "a": int(a), "b": int(b), "saddle_row": row(s), "saddle_value": float(f[s]),
    } for a, b, s in zip(res["graph_a"], res["graph_b"], res["graph_saddle"])]

    merge_tree = [{
        "child": int(m), "parent": int(res["parent"][m]),
        "saddle_row": row(res["death_saddle"][m]),
        "saddle_value": float(f[res["death_saddle"][m]]),
        "persistence": float(res["persistence"][m]),
    } for m in range(len(mv)) if res["parent"][m] >= 0]

    with (out / "graph.json").open("w") as fh:
        json.dump({
            "mode": res["mode"], "k": res["k"], "n_points": res["n"],
            "persistence_threshold": res["threshold"],
            "n_connected_components": res["n_components"],
            "nodes": nodes, "arcs": arcs, "merge_tree": merge_tree,
            "notes": "persistence of a component's global extremum is its value minus the "
                     "global minimum (essential class)",
        }, fh, indent=1)

    with (out / "maxima.csv").open("w") as fh:
        fh.write("id,row,value,persistence,region_size\n")
        for nd in sorted(nodes, key=lambda z: -z["persistence"]):
            fh.write(f"{nd['id']},{nd['row']},{nd['value']},{nd['persistence']},{nd['region_size']}\n")

    np.savez_compressed(
        out / "result.npz",
        kept_rows=kept, labels=res["labels"], simplified_labels=res["simplified_labels"],
        maxima_vertex=mv, persistence=res["persistence"], parent=res["parent"],
        death_saddle=res["death_saddle"], keep=keep,
        graph_a=res["graph_a"], graph_b=res["graph_b"], graph_saddle=res["graph_saddle"],
    )
    print(f"[export] wrote {out}/graph.json, maxima.csv, result.npz")


# --------------------------------------------------------------------------- #
# Stability check across k
# --------------------------------------------------------------------------- #

def stability(X, f, ks, **kw):
    """Run for several k and report how much the kept maxima agree."""
    sets = {}
    for k in ks:
        r = extremum_graph(X, f, k=k, **kw)
        sets[k] = set(r["maxima_vertex"][r["keep"]].tolist())
    base = ks[0]
    print("\n[stability] kept maxima per k, and overlap (Jaccard) with k =", base)
    for k in ks:
        inter, union = len(sets[base] & sets[k]), len(sets[base] | sets[k])
        print(f"  k={k:<4d} kept={len(sets[k]):<5d} jaccard={inter / union if union else 1.0:.2f}")
    return sets


# --------------------------------------------------------------------------- #
# Self test: synthetic 300-D data + comparison with a direct union-find sweep
# --------------------------------------------------------------------------- #

def make_synthetic(n=4000, latent_dim=3, dim=300, peaks=5, noise=0.02, seed=0):
    rng = np.random.default_rng(seed)
    z = rng.uniform(-1, 1, size=(n, latent_dim))
    centres = rng.uniform(-0.7, 0.7, size=(peaks, latent_dim))
    heights = rng.uniform(0.6, 1.0, size=peaks)
    f = np.zeros(n)
    for c, h in zip(centres, heights):
        f += h * np.exp(-((z - c) ** 2).sum(axis=1) / (2 * 0.2 ** 2))
    A = np.linalg.qr(rng.normal(size=(dim, latent_dim)))[0].T * 3.0
    X = z @ A + noise * rng.normal(size=(n, dim))
    return X, f, centres


def reference_persistence(idx, g):
    """Direct sweep over vertices (decreasing value) on the symmetrised kNN graph."""
    n, k = idx.shape
    order = np.lexsort((np.arange(n), g))
    rank = np.empty(n, dtype=np.int64)
    rank[order] = np.arange(n)
    nbrs = [set() for _ in range(n)]
    for i in range(n):
        for j in idx[i]:
            nbrs[i].add(int(j))
            nbrs[int(j)].add(i)
    uf = {}
    top = {}

    def find(x):
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    pers = {}
    for v in order[::-1]:
        v = int(v)
        uf[v] = v
        roots = {find(u) for u in nbrs[v] if u in uf}
        roots.discard(v)
        if not roots:                       # a new local maximum is born
            top[v] = v
            continue
        # v joins every neighbouring component; the component with the highest
        # top survives, the others die at height g[v].
        best = max(roots, key=lambda r: rank[top[r]])
        for r in roots:
            if r != best:
                pers[top[r]] = g[top[r]] - g[v]
                uf[r] = best
        uf[v] = best
    return pers


def selftest():
    X, f, centres = make_synthetic()
    X, f, kept = prepare(X, f)
    res = extremum_graph(X, f, k=15, persistence_frac=0.1, backend="sklearn"
                         if _has("sklearn") else "auto")
    ref = reference_persistence(res["_idx"], res["_g"])

    mv = res["maxima_vertex"]
    bad = 0
    for i, v in enumerate(mv):
        if int(v) in ref and not np.isclose(ref[int(v)], res["persistence"][i], atol=1e-9):
            bad += 1
    missing = sum(1 for v in ref if v not in set(mv.tolist()))
    print(f"\n[selftest] maxima: {len(mv)}, reference deaths: {len(ref)}, "
          f"persistence mismatches: {bad}, reference maxima not found: {missing}")
    print(f"[selftest] kept maxima at 10% persistence: {int(res['keep'].sum())} "
          f"(synthetic data has {len(centres)} planted peaks in a 3-D latent space)")
    assert bad == 0 and missing == 0, "persistence does not match the direct sweep"
    print("[selftest] OK")


def _has(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", help=".npy / .csv / .npz point table")
    p.add_argument("--value-column", help="csv column holding the scalar (default: last)")
    p.add_argument("--k", type=int, default=20, help="neighbours per point (default 20)")
    p.add_argument("--mode", choices=["max", "min"], default="max")
    p.add_argument("--persistence", type=float, default=0.05,
                   help="simplification threshold as a fraction of the value range (default 0.05)")
    p.add_argument("--pca-dims", type=int, default=None,
                   help="optional PCA before the kNN graph (default: none, full space)")
    p.add_argument("--no-standardize", action="store_true", help="skip z-scoring of features")
    p.add_argument("--backend", choices=["auto", "pynndescent", "sklearn", "numpy"], default="auto")
    p.add_argument("--out", default="out/hd_run", help="output directory")
    p.add_argument("--stability", help="comma separated k values, e.g. 10,20,30")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        selftest()
        return 0
    if not args.input:
        p.error("an input file is required (or use --selftest)")

    X, f = load_points(args.input, args.value_column)
    print(f"[load] {X.shape[0]} points, {X.shape[1]} dimensions")
    X, f, kept = prepare(X, f, standardize=not args.no_standardize, pca_dims=args.pca_dims)

    kw = dict(mode=args.mode, persistence_frac=args.persistence, backend=args.backend)
    if args.stability:
        stability(X, f, [int(s) for s in args.stability.split(",")], **kw)
        return 0

    res = extremum_graph(X, f, k=args.k, **kw)
    export(res, f, kept, args.out)
    top = np.argsort(-res["persistence"])[:10]
    print("\ntop extrema by persistence:")
    for i in top:
        print(f"  id={i:<6d} row={int(kept[res['maxima_vertex'][i]]):<8d} "
              f"value={f[res['maxima_vertex'][i]]:<12.5g} persistence={res['persistence'][i]:.5g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

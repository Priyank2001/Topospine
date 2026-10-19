/**
 * PCA to 2-D: the initial layout (proposal feature 2) and a stable frame for warm starts.
 *
 * Positions are centred and projected on the two leading eigenvectors of their d x d
 * covariance, found by power iteration with deflation (d is small: 2, 3 or a handful of
 * features). PCA is a rotation (plus dropping axes), so distances in the plane are on the
 * same scale as distances in the domain - which the stress layout then refines.
 * Eigenvector signs are fixed (largest component positive) so layouts don't flip between runs.
 * 2-D positions are only centred, keeping the spine aligned with the data view.
 */

export function pca2(position: Float64Array, n: number, dim: number, iterations = 200): Float64Array {
  const out = new Float64Array(n * 2);
  if (n === 0) return out;
  if (dim === 2) {
    // Already planar: keep the domain's own axes. For near-isotropic data (a square
    // domain) the principal axes are ill-defined and PCA would rotate arbitrarily.
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { mx += position[2 * i] / n; my += position[2 * i + 1] / n; }
    for (let i = 0; i < n; i++) { out[2 * i] = position[2 * i] - mx; out[2 * i + 1] = position[2 * i + 1] - my; }
    return out;
  }
  const mean = new Float64Array(dim);
  for (let i = 0; i < n; i++) for (let k = 0; k < dim; k++) mean[k] += position[i * dim + k] / n;
  const cov = new Float64Array(dim * dim);
  for (let i = 0; i < n; i++) {
    for (let a = 0; a < dim; a++) {
      const da = position[i * dim + a] - mean[a];
      for (let b = 0; b < dim; b++) cov[a * dim + b] += (da * (position[i * dim + b] - mean[b])) / n;
    }
  }
  const axes: Float64Array[] = [];
  for (let c = 0; c < Math.min(2, dim); c++) {
    let v = new Float64Array(dim).map((_, k) => 1 + k * 0.1); // deterministic, non-degenerate start
    for (const u of axes) orthogonalise(v, u);
    for (let it = 0; it < iterations; it++) {
      const w = new Float64Array(dim);
      for (let a = 0; a < dim; a++) for (let b = 0; b < dim; b++) w[a] += cov[a * dim + b] * v[b];
      for (const u of axes) orthogonalise(w, u); // deflation: stay orthogonal to found axes
      const norm = Math.hypot(...w);
      if (norm < 1e-300) break; // no variance left in this direction
      v = w.map((x) => x / norm);
    }
    const norm = Math.hypot(...v);
    if (norm > 0) v = v.map((x) => x / norm);
    let big = 0;
    for (let k = 0; k < dim; k++) if (Math.abs(v[k]) > Math.abs(v[big])) big = k;
    if (v[big] < 0) v = v.map((x) => -x);
    axes.push(v);
  }
  for (let i = 0; i < n; i++) {
    for (let c = 0; c < axes.length; c++) {
      let s = 0;
      for (let k = 0; k < dim; k++) s += (position[i * dim + k] - mean[k]) * axes[c][k];
      out[i * 2 + c] = s;
    }
  }
  return out;
}

function orthogonalise(v: Float64Array, u: Float64Array): void {
  let dot = 0;
  for (let k = 0; k < v.length; k++) dot += v[k] * u[k];
  for (let k = 0; k < v.length; k++) v[k] -= dot * u[k];
}

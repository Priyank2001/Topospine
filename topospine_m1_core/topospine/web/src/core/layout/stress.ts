/**
 * Distance-preserving 2-D layout by stress majorization (SMACOF; Gansner, Koren & North 2004).
 *
 * The paper models the spine as springs whose rest lengths are the Euclidean distances
 * between critical points (Sec. 4.4). Stress majorization minimises exactly that energy,
 *     stress(X) = sum_{i<j} w_ij (||x_i - x_j|| - d_ij)^2,
 * but, unlike a force simulation, every iteration provably does not increase it, needs no
 * step size or cooling schedule, and is deterministic. The localized update is
 *     x_i <- sum_j w_ij (x_j + d_ij (x_i - x_j) / ||x_i - x_j||) / sum_j w_ij.
 *
 * Weights: w_ij = d_ij^-2 for every pair (keeps the global shape) times `edgeWeight` for
 * pairs joined by a spine link (keeps links at their rest length). Cost O(n^2) per sweep,
 * fine for the few hundred nodes a readable spine has (600 nodes ~ 0.5 s). Larger graphs
 * keep the PCA layout until level-of-detail and a worker arrive in M4.
 */

export interface StressInput {
  n: number;
  /** n*n target distances (symmetric, zero diagonal). */
  target: Float64Array;
  /** Index pairs with extra weight (the spine's links). */
  edges: [number, number][];
  /** n*2 starting positions (warm start or PCA). */
  init: Float64Array;
}

export interface StressOptions {
  edgeWeight: number;
  maxIterations: number;
  tolerance: number; // relative stress change that counts as converged
  maxNodes: number; // above this, return init unchanged
}

export const DEFAULT_STRESS: StressOptions = { edgeWeight: 8, maxIterations: 300, tolerance: 1e-5, maxNodes: 600 };

export function weights(inp: StressInput, edgeWeight: number): Float64Array {
  const { n, target } = inp;
  const w = new Float64Array(n * n);
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) if (i !== j) w[i * n + j] = 1 / Math.max(target[i * n + j], 1e-9) ** 2;
  }
  for (const [i, j] of inp.edges) {
    w[i * n + j] *= edgeWeight;
    w[j * n + i] *= edgeWeight;
  }
  return w;
}

export function stress(pos: Float64Array, target: Float64Array, w: Float64Array, n: number): number {
  let s = 0;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const dist = Math.hypot(pos[2 * i] - pos[2 * j], pos[2 * i + 1] - pos[2 * j + 1]);
      s += w[i * n + j] * (dist - target[i * n + j]) ** 2;
    }
  }
  return s;
}

export interface StressResult {
  position: Float64Array;
  iterations: number;
  stress: number;
}

export function stressLayout(inp: StressInput, opts: StressOptions = DEFAULT_STRESS): StressResult {
  const { n, target } = inp;
  const pos = Float64Array.from(inp.init);
  if (n < 2 || n > opts.maxNodes) return { position: pos, iterations: 0, stress: 0 };
  const w = weights(inp, opts.edgeWeight);
  separateCoincident(pos, n, target);
  let prev = stress(pos, target, w, n);
  let it = 0;
  for (; it < opts.maxIterations; it++) {
    for (let i = 0; i < n; i++) {
      let sx = 0, sy = 0, sw = 0;
      const xi = pos[2 * i], yi = pos[2 * i + 1];
      for (let j = 0; j < n; j++) {
        if (j === i) continue;
        const wij = w[i * n + j];
        const dx = xi - pos[2 * j], dy = yi - pos[2 * j + 1];
        const dist = Math.hypot(dx, dy) || 1e-12;
        const k = target[i * n + j] / dist;
        sx += wij * (pos[2 * j] + k * dx);
        sy += wij * (pos[2 * j + 1] + k * dy);
        sw += wij;
      }
      pos[2 * i] = sx / sw;
      pos[2 * i + 1] = sy / sw;
    }
    const cur = stress(pos, target, w, n);
    if (prev - cur <= opts.tolerance * prev) {
      prev = cur;
      it++;
      break;
    }
    prev = cur;
  }
  return { position: pos, iterations: it, stress: prev };
}

/** Nodes at the same start point would never separate (zero direction); nudge them apart. */
function separateCoincident(pos: Float64Array, n: number, target: Float64Array): void {
  let scale = 0;
  for (let k = 0; k < target.length; k++) scale = Math.max(scale, target[k]);
  const eps = (scale || 1) * 1e-3;
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < i; j++) {
      if (pos[2 * i] === pos[2 * j] && pos[2 * i + 1] === pos[2 * j + 1]) {
        pos[2 * i] += eps * Math.cos(i);
        pos[2 * i + 1] += eps * Math.sin(i);
      }
    }
  }
}

/** Euclidean distances between rows of an (n x dim) position array. */
export function pairwiseDistances(position: Float64Array, ids: ArrayLike<number>, dim: number): Float64Array {
  const n = ids.length;
  const out = new Float64Array(n * n);
  for (let a = 0; a < n; a++) {
    for (let b = a + 1; b < n; b++) {
      let s = 0;
      for (let k = 0; k < dim; k++) {
        const diff = position[ids[a] * dim + k] - position[ids[b] * dim + k];
        s += diff * diff;
      }
      out[a * n + b] = out[b * n + a] = Math.sqrt(s);
    }
  }
  return out;
}

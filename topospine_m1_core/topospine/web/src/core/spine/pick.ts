/** Nearest-node picking in world space. Linear scan: drawn graphs have at most a few thousand nodes. */

/**
 * Index (into the centres array) of the node nearest to (x, y) within `maxDist`, or -1.
 * centers: [x0, y0, x1, y1, ...] in the same units as x, y and maxDist.
 */
export function nearestNode(centers: ArrayLike<number>, x: number, y: number, maxDist: number): number {
  let best = -1;
  let bestD2 = maxDist * maxDist;
  for (let i = 0; i < centers.length / 2; i++) {
    const dx = centers[2 * i] - x, dy = centers[2 * i + 1] - y;
    const d2 = dx * dx + dy * dy;
    if (d2 <= bestD2) {
      bestD2 = d2;
      best = i;
    }
  }
  return best;
}

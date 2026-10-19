/**
 * Signed distance to a tapered capsule ("uneven capsule"): the convex hull of a circle of
 * radius ra at a and a circle of radius rb at b. CPU reference for the GLSL function in
 * render/shaders/capsule.frag.glsl, so the shader's math is unit-tested.
 *
 * Derivation (after Inigo Quilez): work in a frame with a at the origin and b on the +y
 * axis at height h. The hull's straight sides are tangent to both circles; with
 * b' = (ra - rb)/h and a' = sqrt(1 - b'^2), the side's normal is (a', b'). Project p on the
 * side direction (-b', a'): below 0 the closest feature is circle a, above a'h it is
 * circle b, otherwise the straight side. If one circle contains the other (|ra-rb| >= h)
 * the hull is just the larger circle.
 */

export function sdTaperedCapsule(
  px: number, py: number,
  ax: number, ay: number, ra: number,
  bx: number, by: number, rb: number,
): number {
  const dx = bx - ax, dy = by - ay;
  const h = Math.hypot(dx, dy);
  const qx0 = px - ax, qy0 = py - ay;
  if (h < 1e-12 || Math.abs(ra - rb) >= h) {
    return Math.min(Math.hypot(qx0, qy0) - ra, Math.hypot(px - bx, py - by) - rb);
  }
  // rotate into the frame where b is on +y
  const uy = dy / h, ux = dx / h;
  const lx = Math.abs(qx0 * uy - qy0 * ux); // distance across the axis (mirror symmetric)
  const ly = qx0 * ux + qy0 * uy; // distance along the axis
  const b = (ra - rb) / h;
  const a = Math.sqrt(1 - b * b);
  const k = -b * lx + a * ly;
  if (k < 0) return Math.hypot(lx, ly) - ra;
  if (k > a * h) return Math.hypot(lx, ly - h) - rb;
  return a * lx + b * ly - ra;
}

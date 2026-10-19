// Writes the signed distance to this piece, encoded as 0.5 + d / (2 * band), into an
// 8-bit target. Blending uses MIN, so after all pieces of one level are drawn every pixel
// holds the distance to the UNION of the level's shapes: outlines appear only on the
// union's boundary, never where pieces overlap. Mirrors core/spine/sdf.ts (unit-tested).
uniform float uBand;
varying vec2 vWorld;
varying vec4 vAB;
varying vec2 vR;

float sdTaperedCapsule(vec2 p, vec2 a, float ra, vec2 b, float rb) {
  vec2 d = b - a;
  float h = length(d);
  vec2 q = p - a;
  if (h < 1e-9 || abs(ra - rb) >= h) {
    return min(length(q) - ra, length(p - b) - rb);
  }
  vec2 u = d / h;
  float lx = abs(q.x * u.y - q.y * u.x);
  float ly = dot(q, u);
  float bb = (ra - rb) / h;
  float aa = sqrt(1.0 - bb * bb);
  float k = -bb * lx + aa * ly;
  if (k < 0.0) return length(vec2(lx, ly)) - ra;
  if (k > aa * h) return length(vec2(lx, ly - h)) - rb;
  return aa * lx + bb * ly - ra;
}

void main() {
  float d = sdTaperedCapsule(vWorld, vAB.xy, vR.x, vAB.zw, vR.y);
  float e = clamp(0.5 + d / (2.0 * uBand), 0.0, 1.0);
  gl_FragColor = vec4(e, e, e, 1.0);
}

// One instanced quad per tapered-capsule piece, sized to the capsule plus a band of
// uBand world units so the distance field is defined just outside the shape too.
uniform float uBand;
attribute vec4 aAB;   // a.xy, b.xy (world)
attribute vec2 aR;    // ra, rb (world)
varying vec2 vWorld;
varying vec4 vAB;
varying vec2 vR;

void main() {
  vec2 a = aAB.xy;
  vec2 b = aAB.zw;
  vec2 d = b - a;
  float h = length(d);
  vec2 u = h > 1e-9 ? d / h : vec2(1.0, 0.0);
  vec2 v = vec2(-u.y, u.x);
  // extent along the axis also covers the case where one circle swallows the other
  float lo = min(-aR.x, h - aR.y) - uBand;
  float hi = max(aR.x, h + aR.y) + uBand;
  float across = max(aR.x, aR.y) + uBand;
  vec2 p = a + u * mix(lo, hi, position.x) + v * (position.y * across);
  vWorld = p;
  vAB = aAB;
  vR = aR;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 0.0, 1.0);
}

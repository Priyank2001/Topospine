// Screen-size-constant node markers: one instanced quad per node.
uniform float uPxWorld;     // world units per drawing-buffer pixel
uniform float uSizePx;      // marker radius in drawing-buffer pixels (extrema)
attribute vec2 aCenter;
attribute float aKind;      // 0 extremum, 1 saddle
varying vec2 vLocal;
varying float vKind;

void main() {
  float r = (aKind < 0.5 ? uSizePx : 0.8 * uSizePx) + 1.5;
  vLocal = position.xy * r;                                  // pixels from the centre
  vKind = aKind;
  vec2 p = aCenter + position.xy * r * uPxWorld;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 0.0, 1.0);
}

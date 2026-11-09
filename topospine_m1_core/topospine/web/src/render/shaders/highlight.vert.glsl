// Screen-size-constant rings around highlighted nodes: one instanced quad per ring.
uniform float uPxWorld;     // world units per drawing-buffer pixel
uniform float uSizePx;      // node marker radius in drawing-buffer pixels
attribute vec2 aCenter;
attribute float aStyle;     // 0 hovered, 1 selected, 2 stand-in for a merged selection
varying vec2 vLocal;
varying float vStyle;

void main() {
  float r = 3.0 * uSizePx;                                   // ring radius + stroke + AA margin
  vLocal = position.xy * r;                                  // pixels from the centre
  vStyle = aStyle;
  vec2 p = aCenter + position.xy * r * uPxWorld;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 0.0, 1.0);
}

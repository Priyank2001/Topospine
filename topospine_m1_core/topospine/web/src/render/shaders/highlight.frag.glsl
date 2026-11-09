// Ink ring with a thin paper outline so it reads on any level colour.
//   selected: solid, thick;  hovered: thinner, translucent;  stand-in: dashed.
uniform float uSizePx;
uniform vec3 uInk;
uniform vec3 uPaper;
varying vec2 vLocal;
varying float vStyle;

const float PI = 3.14159265;

void main() {
  float radius = 2.0 * uSizePx;
  float halfWidth = (vStyle > 0.5 && vStyle < 1.5 ? 0.32 : 0.22) * uSizePx;
  float d = abs(length(vLocal) - radius);                    // pixels from the ring's centre line
  float ink = 1.0 - smoothstep(halfWidth - 0.75, halfWidth + 0.75, d);
  float outline = 1.0 - smoothstep(halfWidth + 0.25, halfWidth + 1.75, d);
  float alpha = outline * (vStyle < 0.5 ? 0.75 : 1.0);
  if (vStyle > 1.5) {                                        // 12 dashes around the ring
    float a = atan(vLocal.y, vLocal.x) / (2.0 * PI) + 0.5;
    alpha *= step(0.45, fract(a * 12.0));
  }
  if (alpha < 0.003) discard;
  gl_FragColor = vec4(mix(uPaper, uInk, ink / max(outline, 1e-3)), alpha);
}

uniform float uSizePx;
uniform vec3 uInk;
uniform vec3 uPaper;
varying vec2 vLocal;
varying float vKind;

void main() {
  float r = vKind < 0.5 ? uSizePx : 0.8 * uSizePx;
  float d = length(vLocal) - r;                              // pixels
  float inside = 1.0 - smoothstep(-0.75, 0.75, d);
  if (inside < 0.003) discard;
  // extrema: solid ink; saddles: paper-coloured with an ink ring
  float ring = 1.0 - smoothstep(0.75, 2.25, -d);
  vec3 col = vKind < 0.5 ? uInk : mix(uPaper, uInk, ring);
  gl_FragColor = vec4(col, inside);
}

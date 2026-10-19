// Turns one level's union distance field into a filled, outlined pseudo-contour and
// blends it over what is already on screen (lower levels = larger shapes, drawn first).
uniform sampler2D tSdf;
uniform vec2 uResolution;   // drawing-buffer pixels
uniform float uBandPx;      // band width the encoding used, in drawing-buffer pixels
uniform float uLineWidth;   // outline width in drawing-buffer pixels
uniform vec3 uFill;
uniform vec3 uLine;
uniform float uOpacity;

void main() {
  float e = texture2D(tSdf, gl_FragCoord.xy / uResolution).r;
  float d = (e - 0.5) * 2.0 * uBandPx;                       // signed distance in pixels
  float fill = 1.0 - smoothstep(-0.75, 0.75, d);             // ~1.5 px anti-aliased edge
  float line = 1.0 - smoothstep(0.5 * uLineWidth - 0.75, 0.5 * uLineWidth + 0.75, abs(d));
  float alpha = max(fill * uOpacity, line);
  if (alpha < 0.003) discard;
  gl_FragColor = vec4(mix(uFill, uLine, line), alpha);
}

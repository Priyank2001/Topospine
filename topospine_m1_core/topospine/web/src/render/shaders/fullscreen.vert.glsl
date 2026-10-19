// A single triangle covering the screen (no projection needed).
void main() {
  gl_Position = vec4(position.xy, 0.0, 1.0);
}

/**
 * Draws the spine's nested pseudo-contours with two passes per level:
 *
 *   1. distance pass: every tapered-capsule piece of the level is an instanced quad whose
 *      fragment shader writes its signed distance; MIN blending into an 8-bit target leaves
 *      the distance to the union of all pieces in each pixel;
 *   2. composite pass: one full-screen triangle turns that union distance into a filled,
 *      anti-aliased, outlined shape and blends it over the screen.
 *
 * Levels go from the lowest isovalue (largest shapes) to the highest, so higher contours sit
 * on top, giving the paper's nesting look. Cost per frame: 2 passes x levels; with <= 24
 * levels this stays well within an integrated GPU's budget, and the view renders on demand.
 *
 * Why 8-bit: float render targets with blending need extensions an integrated GPU may lack.
 * A narrow band (a few pixels) around each edge is all the composite needs, so 256 steps
 * over 2 x band pixels is plenty (~0.05 px resolution at a 6 px band).
 */

import * as THREE from "three";
import capsuleFrag from "./shaders/capsule.frag.glsl?raw";
import capsuleVert from "./shaders/capsule.vert.glsl?raw";
import compositeFrag from "./shaders/composite.frag.glsl?raw";
import fullscreenVert from "./shaders/fullscreen.vert.glsl?raw";
import { SpineGeometry } from "../core/spine/links";

export interface LevelStyle {
  fill: [number, number, number];
  line: [number, number, number];
}

const BAND_PX = 6;

export class SpineSdfRenderer {
  private readonly target: THREE.WebGLRenderTarget;
  private readonly capsuleMaterial: THREE.ShaderMaterial;
  private readonly compositeMaterial: THREE.ShaderMaterial;
  private readonly quad: THREE.BufferGeometry;
  private readonly composite: THREE.Mesh;
  private readonly compositeScene = new THREE.Scene();
  private readonly screenCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private levels: { scene: THREE.Scene; geometry: THREE.InstancedBufferGeometry; style: LevelStyle }[] = [];
  private readonly clearWhite = new THREE.Color(1, 1, 1);

  constructor() {
    this.target = new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.UnsignedByteType,
      format: THREE.RGBAFormat,
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      depthBuffer: false,
      generateMipmaps: false,
    });

    // unit quad: x in [0, 1] along the piece, y in [-1, 1] across it
    this.quad = new THREE.BufferGeometry();
    this.quad.setAttribute("position", new THREE.Float32BufferAttribute([0, -1, 0, 1, -1, 0, 1, 1, 0, 0, 1, 0], 3));
    this.quad.setIndex([0, 1, 2, 0, 2, 3]);

    this.capsuleMaterial = new THREE.ShaderMaterial({
      vertexShader: capsuleVert,
      fragmentShader: capsuleFrag,
      uniforms: { uBand: { value: 1 } },
      blending: THREE.CustomBlending,
      blendEquation: THREE.MinEquation,
      blendEquationAlpha: THREE.MinEquation,
      depthTest: false,
      depthWrite: false,
      transparent: true, // keeps three from sorting these into the opaque list with blending off
    });

    const tri = new THREE.BufferGeometry();
    tri.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
    this.compositeMaterial = new THREE.ShaderMaterial({
      vertexShader: fullscreenVert,
      fragmentShader: compositeFrag,
      uniforms: {
        tSdf: { value: this.target.texture },
        uResolution: { value: new THREE.Vector2(1, 1) },
        uBandPx: { value: BAND_PX },
        uLineWidth: { value: 1.25 },
        uFill: { value: new THREE.Color() },
        uLine: { value: new THREE.Color() },
        uOpacity: { value: 0.95 },
      },
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
    this.composite = new THREE.Mesh(tri, this.compositeMaterial);
    this.composite.frustumCulled = false;
    this.compositeScene.add(this.composite);
  }

  /** Replace all levels. Called when the derived spine geometry changes. */
  setGeometry(geo: SpineGeometry, styles: LevelStyle[]): void {
    this.disposeLevels();
    geo.pieces.forEach((pieces, i) => {
      const count = pieces.length / 6;
      if (count === 0) return;
      const ab = new Float32Array(count * 4);
      const r = new Float32Array(count * 2);
      for (let k = 0; k < count; k++) {
        ab[4 * k] = pieces[6 * k];
        ab[4 * k + 1] = pieces[6 * k + 1];
        ab[4 * k + 2] = pieces[6 * k + 3];
        ab[4 * k + 3] = pieces[6 * k + 4];
        r[2 * k] = pieces[6 * k + 2];
        r[2 * k + 1] = pieces[6 * k + 5];
      }
      const g = new THREE.InstancedBufferGeometry();
      g.index = this.quad.index;
      g.setAttribute("position", this.quad.getAttribute("position"));
      g.setAttribute("aAB", new THREE.InstancedBufferAttribute(ab, 4));
      g.setAttribute("aR", new THREE.InstancedBufferAttribute(r, 2));
      g.instanceCount = count;
      const mesh = new THREE.Mesh(g, this.capsuleMaterial);
      mesh.frustumCulled = false; // instances move vertices far from the base quad's bounds
      const scene = new THREE.Scene();
      scene.add(mesh);
      this.levels.push({ scene, geometry: g, style: styles[i] });
    });
  }

  /** Draw all levels onto the current (screen) framebuffer. The caller clears it first. */
  render(renderer: THREE.WebGLRenderer, camera: THREE.OrthographicCamera, worldPerPixel: number): void {
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    if (this.target.width !== size.x || this.target.height !== size.y) this.target.setSize(size.x, size.y);
    this.capsuleMaterial.uniforms.uBand.value = BAND_PX * worldPerPixel;
    this.compositeMaterial.uniforms.uResolution.value.copy(size);

    const prevClear = renderer.getClearColor(new THREE.Color());
    const prevAlpha = renderer.getClearAlpha();
    const prevAutoClear = renderer.autoClear;
    renderer.autoClear = false;
    for (const level of this.levels) {
      renderer.setRenderTarget(this.target);
      renderer.setClearColor(this.clearWhite, 1); // 1.0 = far outside every shape
      renderer.clear(true, false, false);
      renderer.render(level.scene, camera);

      renderer.setRenderTarget(null);
      this.compositeMaterial.uniforms.uFill.value.setRGB(...level.style.fill);
      this.compositeMaterial.uniforms.uLine.value.setRGB(...level.style.line);
      renderer.render(this.compositeScene, this.screenCamera);
    }
    renderer.setClearColor(prevClear, prevAlpha);
    renderer.autoClear = prevAutoClear;
  }

  get levelCount(): number {
    return this.levels.length;
  }

  private disposeLevels(): void {
    // dispose() frees every attribute buffer of the geometry, including the shared quad's;
    // three re-uploads those on next use, so sharing stays safe.
    for (const l of this.levels) l.geometry.dispose();
    this.levels = [];
  }

  dispose(): void {
    this.disposeLevels();
    this.quad.dispose();
    this.capsuleMaterial.dispose();
    this.compositeMaterial.dispose();
    this.composite.geometry.dispose();
    this.target.dispose();
  }
}

/**
 * Rings around hovered and selected nodes, drawn after the overlay. Kept apart from Overlay
 * so a hover rebuilds only this handful of instances, never the spine or the markers.
 */

import * as THREE from "three";
import highlightFrag from "./shaders/highlight.frag.glsl?raw";
import highlightVert from "./shaders/highlight.vert.glsl?raw";

export class HighlightLayer {
  readonly scene = new THREE.Scene();
  private readonly material: THREE.ShaderMaterial;
  private readonly quad: THREE.BufferGeometry;
  private rings?: THREE.Mesh<THREE.InstancedBufferGeometry, THREE.ShaderMaterial>;

  constructor() {
    this.quad = new THREE.BufferGeometry();
    this.quad.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0], 3));
    this.quad.setIndex([0, 1, 2, 0, 2, 3]);
    this.material = new THREE.ShaderMaterial({
      vertexShader: highlightVert,
      fragmentShader: highlightFrag,
      uniforms: {
        uPxWorld: { value: 1 },
        uSizePx: { value: 4 },
        uInk: { value: new THREE.Color() },
        uPaper: { value: new THREE.Color() },
      },
      transparent: true,
      depthTest: false,
      depthWrite: false,
    });
  }

  /** centers: [x, y] per ring in world units; styles: 0 hovered, 1 selected, 2 stand-in. */
  set(centers: Float32Array, styles: Float32Array): void {
    this.clear();
    if (!styles.length) return;
    const g = new THREE.InstancedBufferGeometry();
    g.index = this.quad.index;
    g.setAttribute("position", this.quad.getAttribute("position"));
    g.setAttribute("aCenter", new THREE.InstancedBufferAttribute(centers, 2));
    g.setAttribute("aStyle", new THREE.InstancedBufferAttribute(styles, 1));
    g.instanceCount = styles.length;
    this.rings = new THREE.Mesh(g, this.material);
    this.rings.frustumCulled = false;
    this.scene.add(this.rings);
  }

  setStyle(ink: [number, number, number], paper: [number, number, number], pxWorld: number, sizePx: number): void {
    this.material.uniforms.uInk.value.setRGB(...ink);
    this.material.uniforms.uPaper.value.setRGB(...paper);
    this.material.uniforms.uPxWorld.value = pxWorld;
    this.material.uniforms.uSizePx.value = sizePx;
  }

  private clear(): void {
    if (!this.rings) return;
    this.scene.remove(this.rings);
    // also frees the shared quad's GPU buffers; three re-uploads them on next use (as in Overlay)
    this.rings.geometry.dispose();
    this.rings = undefined;
  }

  dispose(): void {
    this.clear();
    this.quad.dispose();
    this.material.dispose();
  }
}

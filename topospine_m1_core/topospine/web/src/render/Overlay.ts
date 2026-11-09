/**
 * Thin skeleton lines (extremum -> saddle) and screen-size node markers drawn on top of the
 * contours. Markers keep a constant pixel size at any zoom, so their quads are rebuilt from
 * the world-per-pixel scale each frame (a uniform, not new geometry).
 */

import * as THREE from "three";
import markerFrag from "./shaders/marker.frag.glsl?raw";
import markerVert from "./shaders/marker.vert.glsl?raw";
import { OverlayData } from "../core/spine/overlay";

export class Overlay {
  readonly scene = new THREE.Scene();
  private readonly lineMaterial = new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.55 });
  private readonly markerMaterial: THREE.ShaderMaterial;
  private readonly quad: THREE.BufferGeometry;
  private lines?: THREE.LineSegments;
  private markers?: THREE.Mesh<THREE.InstancedBufferGeometry, THREE.ShaderMaterial>;

  constructor() {
    this.quad = new THREE.BufferGeometry();
    this.quad.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0], 3));
    this.quad.setIndex([0, 1, 2, 0, 2, 3]);
    this.markerMaterial = new THREE.ShaderMaterial({
      vertexShader: markerVert,
      fragmentShader: markerFrag,
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

  set(data: OverlayData, showSkeleton: boolean, showNodes: boolean): void {
    this.clear();
    if (showSkeleton && data.segments.length) {
      const g = new THREE.BufferGeometry();
      const pts = new Float32Array((data.segments.length / 2) * 3);
      for (let i = 0; i < data.segments.length / 2; i++) {
        pts[3 * i] = data.segments[2 * i];
        pts[3 * i + 1] = data.segments[2 * i + 1];
      }
      g.setAttribute("position", new THREE.BufferAttribute(pts, 3));
      this.lines = new THREE.LineSegments(g, this.lineMaterial);
      this.lines.frustumCulled = false;
      this.scene.add(this.lines);
    }
    if (showNodes && data.kinds.length) {
      const g = new THREE.InstancedBufferGeometry();
      g.index = this.quad.index;
      g.setAttribute("position", this.quad.getAttribute("position"));
      g.setAttribute("aCenter", new THREE.InstancedBufferAttribute(data.centers, 2));
      g.setAttribute("aKind", new THREE.InstancedBufferAttribute(data.kinds, 1));
      g.instanceCount = data.kinds.length;
      this.markers = new THREE.Mesh(g, this.markerMaterial);
      this.markers.frustumCulled = false;
      this.markers.renderOrder = 1;
      this.scene.add(this.markers);
    }
  }

  setStyle(ink: [number, number, number], paper: [number, number, number], pxWorld: number, sizePx: number): void {
    this.lineMaterial.color.setRGB(...ink);
    this.markerMaterial.uniforms.uInk.value.setRGB(...ink);
    this.markerMaterial.uniforms.uPaper.value.setRGB(...paper);
    this.markerMaterial.uniforms.uPxWorld.value = pxWorld;
    this.markerMaterial.uniforms.uSizePx.value = sizePx;
  }

  private clear(): void {
    if (this.lines) {
      this.scene.remove(this.lines);
      this.lines.geometry.dispose();
      this.lines = undefined;
    }
    if (this.markers) {
      this.scene.remove(this.markers);
      this.markers.geometry.dispose();
      this.markers = undefined;
    }
  }

  dispose(): void {
    this.clear();
    this.quad.dispose();
    this.lineMaterial.dispose();
    this.markerMaterial.dispose();
  }
}

/**
 * The spine canvas: owns the WebGLRenderer, an orthographic camera, pan/zoom input,
 * resizing, theme colours, and render-on-demand (no continuous loop: on an integrated GPU
 * an idle view should cost nothing).
 *
 * The view transform is (centre, worldPerCssPixel); the camera frustum is rebuilt from it
 * on every render, so resizing keeps the scale and zooming keeps the point under the cursor.
 */

import * as THREE from "three";
import { Overlay, OverlayData } from "../render/Overlay";
import { LevelStyle, SpineSdfRenderer } from "../render/SpineSdfRenderer";
import { SpineGeometry } from "../core/spine/links";

export interface Theme {
  background: [number, number, number];
  ink: [number, number, number];
  paper: [number, number, number];
}

function cssColor(name: string, fallback: string): [number, number, number] {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  const c = new THREE.Color(raw);
  return [c.r, c.g, c.b];
}

export function readTheme(): Theme {
  return {
    background: cssColor("--canvas", "#f3f5f7"),
    ink: cssColor("--ink", "#1f2a36"),
    paper: cssColor("--paper", "#ffffff"),
  };
}

export class SpineView {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -1, 1);
  private readonly sdf = new SpineSdfRenderer();
  private readonly overlay = new Overlay();
  private readonly resizeObserver: ResizeObserver;
  private readonly darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  private center = { x: 0, y: 0 };
  private worldPerCss = 1;
  private bounds: { minX: number; minY: number; maxX: number; maxY: number } | null = null;
  private pending = 0;
  private theme: Theme = readTheme();
  private drag: { id: number; x: number; y: number } | null = null;
  private readonly onThemeChange = () => {
    this.theme = readTheme();
    this.requestRender();
  };

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "default" });
    if (!this.renderer.capabilities.isWebGL2) throw new Error("WebGL2 is required (3D textures, MIN blending)");
    this.renderer.outputColorSpace = THREE.LinearSRGBColorSpace; // colours are written as given
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); // cap: fill-rate on integrated GPUs
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement ?? canvas);
    this.darkQuery.addEventListener("change", this.onThemeChange);
    canvas.addEventListener("wheel", this.onWheel, { passive: false });
    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointermove", this.onPointerMove);
    canvas.addEventListener("pointerup", this.onPointerUp);
    canvas.addEventListener("pointercancel", this.onPointerUp);
    canvas.addEventListener("dblclick", () => this.fit());
    this.resize();
  }

  setContent(geo: SpineGeometry, styles: LevelStyle[], overlay: OverlayData, showSkeleton: boolean, showNodes: boolean): void {
    this.sdf.setGeometry(geo, styles);
    this.overlay.set(overlay, showSkeleton, showNodes);
    this.bounds = contentBounds(geo, overlay);
    this.requestRender();
  }

  /** Frame the current content with a margin. */
  fit(): void {
    if (!this.bounds) return;
    const { minX, minY, maxX, maxY } = this.bounds;
    const w = this.canvas.clientWidth || 1, h = this.canvas.clientHeight || 1;
    this.center = { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
    this.worldPerCss = Math.max((maxX - minX) / w, (maxY - minY) / h, 1e-9) * 1.12;
    this.requestRender();
  }

  requestRender(): void {
    if (this.pending) return;
    this.pending = requestAnimationFrame(() => {
      this.pending = 0;
      this.draw();
    });
  }

  private draw(): void {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) return;
    const halfW = (w * this.worldPerCss) / 2, halfH = (h * this.worldPerCss) / 2;
    const cam = this.camera;
    cam.left = this.center.x - halfW;
    cam.right = this.center.x + halfW;
    cam.top = this.center.y + halfH;
    cam.bottom = this.center.y - halfH;
    cam.updateProjectionMatrix();

    const worldPerPixel = this.worldPerCss / this.renderer.getPixelRatio();
    const r = this.renderer;
    r.setRenderTarget(null);
    r.setClearColor(new THREE.Color(...this.theme.background), 1);
    r.clear();
    this.sdf.render(r, cam, worldPerPixel);
    this.overlay.setStyle(this.theme.ink, this.theme.paper, worldPerPixel, 4 * r.getPixelRatio());
    const auto = r.autoClear;
    r.autoClear = false;
    r.render(this.overlay.scene, cam);
    r.autoClear = auto;
  }

  private resize(): void {
    const parent = this.canvas.parentElement ?? this.canvas;
    const w = parent.clientWidth, h = parent.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, true);
    this.requestRender();
  }

  // --- input ---------------------------------------------------------------------------
  private toWorld(clientX: number, clientY: number): { x: number; y: number } {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: this.center.x + (clientX - rect.left - rect.width / 2) * this.worldPerCss,
      y: this.center.y - (clientY - rect.top - rect.height / 2) * this.worldPerCss,
    };
  }

  private readonly onWheel = (e: WheelEvent) => {
    e.preventDefault();
    const before = this.toWorld(e.clientX, e.clientY);
    this.worldPerCss *= Math.exp(e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015));
    const after = this.toWorld(e.clientX, e.clientY);
    this.center.x += before.x - after.x; // keep the point under the cursor fixed
    this.center.y += before.y - after.y;
    this.requestRender();
  };

  private readonly onPointerDown = (e: PointerEvent) => {
    this.drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
    this.canvas.setPointerCapture(e.pointerId);
  };

  private readonly onPointerMove = (e: PointerEvent) => {
    if (!this.drag || this.drag.id !== e.pointerId) return;
    this.center.x -= (e.clientX - this.drag.x) * this.worldPerCss;
    this.center.y += (e.clientY - this.drag.y) * this.worldPerCss;
    this.drag.x = e.clientX;
    this.drag.y = e.clientY;
    this.requestRender();
  };

  private readonly onPointerUp = (e: PointerEvent) => {
    if (this.drag?.id === e.pointerId) this.drag = null;
  };

  dispose(): void {
    if (this.pending) cancelAnimationFrame(this.pending);
    this.resizeObserver.disconnect();
    this.darkQuery.removeEventListener("change", this.onThemeChange);
    this.canvas.removeEventListener("wheel", this.onWheel);
    this.canvas.removeEventListener("pointerdown", this.onPointerDown);
    this.canvas.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("pointerup", this.onPointerUp);
    this.canvas.removeEventListener("pointercancel", this.onPointerUp);
    this.sdf.dispose();
    this.overlay.dispose();
    this.renderer.dispose();
  }
}

function contentBounds(geo: SpineGeometry, overlay: OverlayData) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const add = (x: number, y: number, r: number) => {
    minX = Math.min(minX, x - r); maxX = Math.max(maxX, x + r);
    minY = Math.min(minY, y - r); maxY = Math.max(maxY, y + r);
  };
  for (const p of geo.pieces) for (let k = 0; k < p.length; k += 6) { add(p[k], p[k + 1], p[k + 2]); add(p[k + 3], p[k + 4], p[k + 5]); }
  for (let k = 0; k < overlay.centers.length; k += 2) add(overlay.centers[k], overlay.centers[k + 1], 0);
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null;
}

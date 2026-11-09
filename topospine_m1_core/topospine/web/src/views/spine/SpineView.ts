/**
 * The spine canvas: owns the WebGLRenderer, an orthographic camera, pan/zoom input, node
 * picking, resizing, theme colours, and render-on-demand (no continuous loop: on an integrated
 * GPU an idle view should cost nothing).
 *
 * Passive (MVP): it draws the SpineViewModel and highlight rings it is given and reports
 * hover/click intents. The only things it decides are visual: camera (Viewport), theme,
 * outline colours (fill mixed with the theme ink), and which drawn node is under the pointer.
 * Raw input -> gestures is PointerGestures' job.
 */

import * as THREE from "three";
import { HighlightItem, HighlightStyle } from "../../core/selection";
import { SpineGeometry } from "../../core/spine/links";
import { OverlayData } from "../../core/spine/overlay";
import { nearestNode } from "../../core/spine/pick";
import { HighlightLayer } from "../../render/HighlightLayer";
import { Overlay } from "../../render/Overlay";
import { LevelStyle, SpineSdfRenderer } from "../../render/SpineSdfRenderer";
import { ISpineView, SpineViewEvents, SpineViewModel } from "./contract";
import { PointerGestures } from "./PointerGestures";
import { Theme, readTheme } from "./theme";
import { Bounds, Viewport } from "./Viewport";

/** Node marker radius in CSS pixels (markers and rings scale with the device pixel ratio). */
const MARKER_PX = 4;
/** A node is picked if the pointer is within this many CSS pixels of its centre. */
const PICK_PX = 10;

const STYLE_CODE: Record<HighlightStyle, number> = { hovered: 0, selected: 1, standIn: 2 };

export class SpineView implements ISpineView {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -1, 1);
  private readonly sdf = new SpineSdfRenderer();
  private readonly overlay = new Overlay();
  private readonly rings = new HighlightLayer();
  private readonly viewport = new Viewport();
  private readonly gestures: PointerGestures;
  private readonly resizeObserver: ResizeObserver;
  private readonly darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  private events?: SpineViewEvents;
  private bounds: Bounds | null = null;
  private pending = 0;
  private theme: Theme = readTheme();
  private content: SpineViewModel | null = null;
  private indexOf = new Map<number, number>(); // node id -> overlay centre index
  private highlights: readonly HighlightItem[] = [];
  private hoveredId: number | null = null;
  private readonly onThemeChange = () => {
    this.theme = readTheme();
    if (this.content) this.render(this.content); // outlines are mixed with the theme ink
    else this.requestRender();
  };

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "default" });
    if (!this.renderer.capabilities.isWebGL2) throw new Error("WebGL2 is required (3D textures, MIN blending)");
    this.renderer.outputColorSpace = THREE.LinearSRGBColorSpace; // colours are written as given
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); // cap: fill-rate on integrated GPUs
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement ?? canvas);
    this.darkQuery.addEventListener("change", this.onThemeChange);
    this.gestures = new PointerGestures(canvas, {
      pan: (dx, dy) => {
        this.viewport.panByCss(dx, dy);
        this.requestRender();
      },
      zoom: (px, py, factor) => {
        this.viewport.zoomAt(px, py, canvas.clientWidth, canvas.clientHeight, factor);
        this.requestRender();
      },
      hover: (px, py) => this.setHovered(this.pick(px, py)),
      leave: () => this.setHovered(null),
      click: (px, py, shift) => {
        const id = this.pick(px, py);
        if (id === null) this.events?.cleared();
        else this.events?.nodeClicked(id, shift);
      },
      doubleClick: () => this.fit(),
      escape: () => this.events?.cleared(),
    });
    this.resize();
  }

  bind(events: SpineViewEvents): void {
    this.events = events;
  }

  render(vm: SpineViewModel): void {
    this.content = vm;
    this.indexOf = new Map(Array.from(vm.nodeIds, (id, i) => [id, i]));
    this.sdf.setGeometry(vm.geometry, this.levelStyles(vm));
    this.overlay.set(vm.overlay, vm.showSkeleton, vm.showNodes);
    this.bounds = contentBounds(vm.geometry, vm.overlay);
    this.applyHighlights(); // node positions may have moved
  }

  highlight(items: readonly HighlightItem[]): void {
    this.highlights = items;
    this.applyHighlights();
  }

  /** Frame the current content with a margin. */
  fit(): void {
    if (!this.bounds) return;
    this.viewport.fit(this.bounds, this.canvas.clientWidth || 1, this.canvas.clientHeight || 1);
    this.requestRender();
  }

  private levelStyles(vm: SpineViewModel): LevelStyle[] {
    const ink = this.theme.ink;
    return vm.levelFills.map((fill) => ({ fill, line: [0, 1, 2].map((i) => 0.5 * fill[i] + 0.5 * ink[i]) as Theme["ink"] }));
  }

  private applyHighlights(): void {
    const centers = this.content?.overlay.centers ?? new Float32Array(0);
    const drawable: [number, HighlightStyle][] = [];
    for (const h of this.highlights) {
      const i = this.indexOf.get(h.node);
      if (i !== undefined) drawable.push([i, h.style]);
    }
    const xy = new Float32Array(drawable.length * 2);
    const styles = new Float32Array(drawable.length);
    drawable.forEach(([i, style], k) => {
      xy[2 * k] = centers[2 * i];
      xy[2 * k + 1] = centers[2 * i + 1];
      styles[k] = STYLE_CODE[style];
    });
    this.rings.set(xy, styles);
    this.requestRender();
  }

  private requestRender(): void {
    if (this.pending) return;
    this.pending = requestAnimationFrame(() => {
      this.pending = 0;
      this.draw();
    });
  }

  private draw(): void {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) return;
    Object.assign(this.camera, this.viewport.frustum(w, h));
    this.camera.updateProjectionMatrix();

    const r = this.renderer;
    const worldPerPixel = this.viewport.worldPerCss / r.getPixelRatio();
    const markerPx = MARKER_PX * r.getPixelRatio();
    r.setRenderTarget(null);
    r.setClearColor(new THREE.Color(...this.theme.background), 1);
    r.clear();
    this.sdf.render(r, this.camera, worldPerPixel);
    this.overlay.setStyle(this.theme.ink, this.theme.paper, worldPerPixel, markerPx);
    this.rings.setStyle(this.theme.ink, this.theme.paper, worldPerPixel, markerPx);
    const auto = r.autoClear;
    r.autoClear = false;
    r.render(this.overlay.scene, this.camera);
    r.render(this.rings.scene, this.camera);
    r.autoClear = auto;
  }

  private resize(): void {
    const parent = this.canvas.parentElement ?? this.canvas;
    const w = parent.clientWidth, h = parent.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, true);
    this.requestRender();
  }

  // --- picking -------------------------------------------------------------------------
  /** Node id under (px, py) CSS pixels, or null. */
  private pick(px: number, py: number): number | null {
    if (!this.content) return null;
    const p = this.viewport.toWorld(px, py, this.canvas.clientWidth, this.canvas.clientHeight);
    const i = nearestNode(this.content.overlay.centers, p.x, p.y, PICK_PX * this.viewport.worldPerCss);
    return i < 0 ? null : this.content.nodeIds[i];
  }

  private setHovered(id: number | null): void {
    if (id === this.hoveredId) return;
    this.hoveredId = id;
    this.canvas.style.cursor = id === null ? "" : "pointer";
    this.events?.nodeHovered(id);
  }

  dispose(): void {
    if (this.pending) cancelAnimationFrame(this.pending);
    this.resizeObserver.disconnect();
    this.darkQuery.removeEventListener("change", this.onThemeChange);
    this.gestures.dispose();
    this.sdf.dispose();
    this.overlay.dispose();
    this.rings.dispose();
    this.renderer.dispose();
  }
}

function contentBounds(geo: SpineGeometry, overlay: OverlayData): Bounds | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const add = (x: number, y: number, r: number) => {
    minX = Math.min(minX, x - r); maxX = Math.max(maxX, x + r);
    minY = Math.min(minY, y - r); maxY = Math.max(maxY, y + r);
  };
  for (const p of geo.pieces) for (let k = 0; k < p.length; k += 6) { add(p[k], p[k + 1], p[k + 2]); add(p[k + 3], p[k + 4], p[k + 5]); }
  for (let k = 0; k < overlay.centers.length; k += 2) add(overlay.centers[k], overlay.centers[k + 1], 0);
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null;
}

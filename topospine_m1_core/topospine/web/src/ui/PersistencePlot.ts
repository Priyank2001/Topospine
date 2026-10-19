/**
 * The paper's two-curve plot (Fig. 8b), made interactive: the blue curve counts extrema kept
 * for a noise threshold pLo, the red one counts arcs kept for a variation threshold pHi.
 * Plateaus mark stable structure. Drag the blue line to set pLo, the red one to set pHi;
 * dragging the red line to the right edge removes the variation limit (pHi = infinity).
 * Arrow keys nudge the focused threshold for keyboard users.
 */

import { arcCurve, extremaCurve, maxFinitePersistence } from "../core/thresholds";
import { SpineData } from "../core/types";

type Which = "lo" | "hi";

const PAD = { left: 8, right: 8, top: 10, bottom: 22 };

export class PersistencePlot {
  private t = new Float64Array(0);
  private blue = new Int32Array(0);
  private red = new Int32Array(0);
  private xMax = 1;
  private pLo = 0;
  private pHi = Infinity;
  private dragging: Which | null = null;
  private focus: Which = "lo";
  private readonly resizeObserver: ResizeObserver;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly onChange: (pLo: number, pHi: number) => void,
  ) {
    canvas.tabIndex = 0;
    canvas.addEventListener("pointerdown", this.onDown);
    canvas.addEventListener("pointermove", this.onMove);
    canvas.addEventListener("pointerup", this.onUp);
    canvas.addEventListener("keydown", this.onKey);
    this.resizeObserver = new ResizeObserver(() => this.draw());
    this.resizeObserver.observe(canvas);
  }

  setData(d: SpineData): void {
    this.xMax = (maxFinitePersistence(d) || 1) * 1.05;
    this.t = Float64Array.from({ length: 400 }, (_, i) => (i / 399) * this.xMax);
    this.blue = extremaCurve(d, this.t);
    this.red = arcCurve(d, this.t);
    this.draw();
  }

  setThresholds(pLo: number, pHi: number): void {
    this.pLo = pLo;
    this.pHi = pHi;
    this.draw();
  }

  private plotWidth(): number {
    return this.canvas.clientWidth - PAD.left - PAD.right;
  }

  private xOf(p: number): number {
    return PAD.left + (Math.min(p, this.xMax) / this.xMax) * this.plotWidth();
  }

  private pOf(clientX: number): number {
    const rect = this.canvas.getBoundingClientRect();
    const frac = (clientX - rect.left - PAD.left) / this.plotWidth();
    return Math.max(0, Math.min(1, frac)) * this.xMax;
  }

  private emit(which: Which, p: number, atRightEdge: boolean): void {
    if (which === "lo") this.pLo = Math.min(p, Number.isFinite(this.pHi) ? this.pHi : p);
    else this.pHi = atRightEdge ? Infinity : Math.max(p, this.pLo);
    this.draw();
    this.onChange(this.pLo, this.pHi);
  }

  private readonly onDown = (e: PointerEvent) => {
    const x = e.clientX - this.canvas.getBoundingClientRect().left;
    const dLo = Math.abs(x - this.xOf(this.pLo));
    const dHi = Math.abs(x - this.xOf(this.pHi));
    this.dragging = dHi < dLo ? "hi" : "lo";
    this.focus = this.dragging;
    this.canvas.setPointerCapture(e.pointerId);
    this.onMove(e);
  };

  private readonly onMove = (e: PointerEvent) => {
    if (!this.dragging) return;
    const rect = this.canvas.getBoundingClientRect();
    const atEdge = e.clientX > rect.right - PAD.right - 3;
    this.emit(this.dragging, this.pOf(e.clientX), atEdge);
  };

  private readonly onUp = () => {
    this.dragging = null;
  };

  private readonly onKey = (e: KeyboardEvent) => {
    if (e.key === "Tab") return;
    if (e.key === "l") this.focus = "lo";
    else if (e.key === "h") this.focus = "hi";
    else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      const step = (e.shiftKey ? 0.05 : 0.01) * this.xMax * (e.key === "ArrowLeft" ? -1 : 1);
      const cur = this.focus === "lo" ? this.pLo : Number.isFinite(this.pHi) ? this.pHi : this.xMax;
      const next = Math.max(0, cur + step);
      this.emit(this.focus, next, this.focus === "hi" && next >= this.xMax);
    } else return;
    e.preventDefault();
  };

  draw(): void {
    const c = this.canvas;
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = c.clientHeight;
    if (!w || !h) return;
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
    const g = c.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const css = getComputedStyle(document.documentElement);
    const blue = css.getPropertyValue("--persistence").trim() || "#2f6db5";
    const red = css.getPropertyValue("--variation").trim() || "#c23b3b";
    const ink = css.getPropertyValue("--ink-soft").trim() || "#5b6774";
    const plotH = h - PAD.top - PAD.bottom;

    const curve = (ys: Int32Array, color: string) => {
      const yMax = Math.max(1, ...ys);
      g.beginPath();
      g.moveTo(PAD.left, PAD.top + plotH);
      for (let i = 0; i < ys.length; i++) {
        const x = this.xOf(this.t[i]);
        const y = PAD.top + plotH * (1 - ys[i] / yMax);
        if (i === 0) g.lineTo(x, y);
        else {
          g.lineTo(x, PAD.top + plotH * (1 - ys[i - 1] / yMax));
          g.lineTo(x, y);
        }
      }
      g.lineTo(this.xOf(this.xMax), PAD.top + plotH);
      g.closePath();
      g.globalAlpha = 0.16;
      g.fillStyle = color;
      g.fill();
      g.globalAlpha = 1;
      g.strokeStyle = color;
      g.lineWidth = 1.5;
      g.stroke();
    };
    curve(this.blue, blue);
    curve(this.red, red);

    // axis
    g.strokeStyle = ink;
    g.lineWidth = 1;
    g.beginPath();
    g.moveTo(PAD.left, PAD.top + plotH + 0.5);
    g.lineTo(w - PAD.right, PAD.top + plotH + 0.5);
    g.stroke();

    const handle = (p: number, color: string, label: string, focused: boolean) => {
      const x = Math.round(this.xOf(p)) + 0.5;
      g.strokeStyle = color;
      g.lineWidth = focused ? 2.5 : 1.5;
      g.beginPath();
      g.moveTo(x, PAD.top);
      g.lineTo(x, PAD.top + plotH);
      g.stroke();
      g.fillStyle = color;
      g.font = "12px system-ui, sans-serif";
      g.textAlign = x > w / 2 ? "right" : "left";
      g.fillText(label, x + (x > w / 2 ? -5 : 5), PAD.top + plotH + 16);
    };
    handle(this.pLo, blue, `noise ${fmt(this.pLo)}`, this.focus === "lo");
    handle(this.pHi, red, `variation ${Number.isFinite(this.pHi) ? fmt(this.pHi) : "∞"}`, this.focus === "hi");
  }

  dispose(): void {
    this.resizeObserver.disconnect();
    this.canvas.removeEventListener("pointerdown", this.onDown);
    this.canvas.removeEventListener("pointermove", this.onMove);
    this.canvas.removeEventListener("pointerup", this.onUp);
    this.canvas.removeEventListener("keydown", this.onKey);
  }
}

export function fmt(p: number): string {
  if (p === 0) return "0";
  return Math.abs(p) >= 100 || Math.abs(p) < 0.01 ? p.toExponential(1) : p.toPrecision(2);
}

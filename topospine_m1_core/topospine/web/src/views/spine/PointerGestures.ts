/**
 * Turns raw canvas input into gestures: pan (drag), zoom (wheel), hover, click, leave,
 * double-click, Esc. Owns the listeners and the in-progress drag; knows nothing about what is
 * drawn. A press that moves less than CLICK_SLOP_PX before release is a click, not a pan.
 * Positions are CSS pixels from the canvas's top-left corner.
 */

/** A press that moves less than this (CSS pixels) is a click, not a pan. */
const CLICK_SLOP_PX = 4;

export interface GestureHandlers {
  pan(dx: number, dy: number): void;
  /** factor > 1 zooms out. */
  zoom(px: number, py: number, factor: number): void;
  hover(px: number, py: number): void;
  click(px: number, py: number, shift: boolean): void;
  leave(): void;
  doubleClick(): void;
  escape(): void;
}

export class PointerGestures {
  private drag: { id: number; x: number; y: number; startX: number; startY: number; moved: boolean } | null = null;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly on: GestureHandlers,
  ) {
    canvas.tabIndex = 0; // focusable, for Esc
    canvas.addEventListener("wheel", this.onWheel, { passive: false });
    canvas.addEventListener("pointerdown", this.onDown);
    canvas.addEventListener("pointermove", this.onMove);
    canvas.addEventListener("pointerup", this.onUp);
    canvas.addEventListener("pointercancel", this.onCancel);
    canvas.addEventListener("pointerleave", this.onLeave);
    canvas.addEventListener("dblclick", this.onDoubleClick);
    canvas.addEventListener("keydown", this.onKey);
  }

  private local(e: { clientX: number; clientY: number }): [number, number] {
    const rect = this.canvas.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  private readonly onWheel = (e: WheelEvent) => {
    e.preventDefault();
    this.on.zoom(...this.local(e), Math.exp(e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)));
  };

  private readonly onDown = (e: PointerEvent) => {
    this.canvas.focus({ preventScroll: true });
    this.drag = { id: e.pointerId, x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY, moved: false };
    this.canvas.setPointerCapture(e.pointerId);
  };

  private readonly onMove = (e: PointerEvent) => {
    const d = this.drag;
    if (!d || d.id !== e.pointerId) {
      this.on.hover(...this.local(e));
      return;
    }
    if (Math.hypot(e.clientX - d.startX, e.clientY - d.startY) > CLICK_SLOP_PX) d.moved = true;
    this.on.pan(e.clientX - d.x, e.clientY - d.y);
    d.x = e.clientX;
    d.y = e.clientY;
  };

  private readonly onUp = (e: PointerEvent) => {
    const d = this.drag;
    if (!d || d.id !== e.pointerId) return;
    this.drag = null;
    if (!d.moved) this.on.click(...this.local(e), e.shiftKey);
  };

  private readonly onCancel = (e: PointerEvent) => {
    if (this.drag?.id === e.pointerId) this.drag = null;
  };

  private readonly onLeave = () => {
    if (!this.drag) this.on.leave();
  };

  private readonly onDoubleClick = () => this.on.doubleClick();

  private readonly onKey = (e: KeyboardEvent) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    this.on.escape();
  };

  dispose(): void {
    this.canvas.removeEventListener("wheel", this.onWheel);
    this.canvas.removeEventListener("pointerdown", this.onDown);
    this.canvas.removeEventListener("pointermove", this.onMove);
    this.canvas.removeEventListener("pointerup", this.onUp);
    this.canvas.removeEventListener("pointercancel", this.onCancel);
    this.canvas.removeEventListener("pointerleave", this.onLeave);
    this.canvas.removeEventListener("dblclick", this.onDoubleClick);
    this.canvas.removeEventListener("keydown", this.onKey);
  }
}

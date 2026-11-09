/**
 * Pan/zoom state of the 2-D spine view: a centre and a scale (world units per CSS pixel).
 * No DOM: the view passes canvas sizes and pointer offsets in, so this math is unit-tested.
 * Resizing keeps the scale; zooming keeps the point under the cursor fixed.
 */

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Fraction of empty margin around fitted content. */
const FIT_MARGIN = 1.12;

export class Viewport {
  center = { x: 0, y: 0 };
  worldPerCss = 1;

  /** (px, py): CSS pixels from the canvas's top-left corner. */
  toWorld(px: number, py: number, width: number, height: number): { x: number; y: number } {
    return {
      x: this.center.x + (px - width / 2) * this.worldPerCss,
      y: this.center.y - (py - height / 2) * this.worldPerCss,
    };
  }

  /** Drag by (dx, dy) CSS pixels: the content follows the pointer. */
  panByCss(dx: number, dy: number): void {
    this.center.x -= dx * this.worldPerCss;
    this.center.y += dy * this.worldPerCss;
  }

  /** Scale by `factor` (> 1 zooms out) around the pointer. */
  zoomAt(px: number, py: number, width: number, height: number, factor: number): void {
    const before = this.toWorld(px, py, width, height);
    this.worldPerCss *= factor;
    const after = this.toWorld(px, py, width, height);
    this.center.x += before.x - after.x;
    this.center.y += before.y - after.y;
  }

  fit(b: Bounds, width: number, height: number): void {
    this.center = { x: (b.minX + b.maxX) / 2, y: (b.minY + b.maxY) / 2 };
    this.worldPerCss = Math.max((b.maxX - b.minX) / width, (b.maxY - b.minY) / height, 1e-9) * FIT_MARGIN;
  }

  frustum(width: number, height: number): { left: number; right: number; top: number; bottom: number } {
    const halfW = (width * this.worldPerCss) / 2, halfH = (height * this.worldPerCss) / 2;
    return { left: this.center.x - halfW, right: this.center.x + halfW, top: this.center.y + halfH, bottom: this.center.y - halfH };
  }
}

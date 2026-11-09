import { describe, expect, it } from "vitest";
import { Viewport } from "../../src/views/spine/Viewport";

describe("Viewport", () => {
  it("maps the canvas centre to the view centre and y up", () => {
    const v = new Viewport();
    v.center = { x: 5, y: 7 };
    v.worldPerCss = 2;
    expect(v.toWorld(50, 50, 100, 100)).toEqual({ x: 5, y: 7 });
    expect(v.toWorld(60, 40, 100, 100)).toEqual({ x: 25, y: 27 });
  });

  it("zooming keeps the point under the cursor fixed", () => {
    const v = new Viewport();
    const before = v.toWorld(80, 20, 200, 100);
    v.zoomAt(80, 20, 200, 100, 0.5);
    const after = v.toWorld(80, 20, 200, 100);
    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
    expect(v.worldPerCss).toBe(0.5);
  });

  it("panning moves content with the pointer", () => {
    const v = new Viewport();
    const p = v.toWorld(10, 10, 100, 100);
    v.panByCss(5, -3);
    const q = v.toWorld(15, 7, 100, 100);
    expect(q.x).toBeCloseTo(p.x);
    expect(q.y).toBeCloseTo(p.y);
  });

  it("fit centres the bounds with a margin on the tighter axis", () => {
    const v = new Viewport();
    v.fit({ minX: 0, minY: 0, maxX: 100, maxY: 10 }, 200, 100);
    expect(v.center).toEqual({ x: 50, y: 5 });
    expect(v.worldPerCss).toBeCloseTo(0.5 * 1.12);
    const f = v.frustum(200, 100);
    expect(f.right - f.left).toBeCloseTo(112);
  });
});

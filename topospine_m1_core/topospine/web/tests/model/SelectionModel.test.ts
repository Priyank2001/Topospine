import { describe, expect, it } from "vitest";
import { SelectionModel } from "../../src/model/SelectionModel";

describe("SelectionModel", () => {
  it("selectOnly replaces, toggle adds and removes, in click order", () => {
    const s = new SelectionModel();
    s.selectOnly(4);
    s.toggle(2);
    s.toggle(7);
    expect([...s.state.selected]).toEqual([4, 2, 7]);
    s.toggle(2);
    expect([...s.state.selected]).toEqual([4, 7]);
    s.selectOnly(9);
    expect([...s.state.selected]).toEqual([9]);
  });

  it("clear drops the selection but keeps the hover; reset drops both", () => {
    const s = new SelectionModel();
    s.selectOnly(1);
    s.hover(3);
    s.clear();
    expect(s.state.selected.size).toBe(0);
    expect(s.state.hovered).toBe(3);
    s.reset();
    expect(s.state.hovered).toBeNull();
  });

  it("does not notify when nothing changes", () => {
    const s = new SelectionModel();
    let n = 0;
    s.subscribe(() => n++);
    s.clear(); // already empty
    s.selectOnly(2);
    s.selectOnly(2); // same single selection
    s.hover(null); // already null
    s.hover(5);
    s.hover(5);
    expect(n).toBe(2);
  });

  it("never mutates a snapshot it handed out", () => {
    const s = new SelectionModel();
    s.selectOnly(1);
    const before = s.state.selected;
    s.toggle(2);
    expect([...before]).toEqual([1]);
  });
});

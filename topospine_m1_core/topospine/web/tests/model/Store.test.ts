import { describe, expect, it } from "vitest";
import { Store } from "../../src/model/Store";

describe("Store", () => {
  it("notifies on change only", () => {
    const s = new Store({ x: 1, y: 2 });
    let n = 0;
    s.subscribe(() => n++);
    s.set({ x: 1 });
    s.set({ x: 3 });
    expect(n).toBe(1);
    expect(s.get().x).toBe(3);
  });

  it("replaces the snapshot instead of mutating it", () => {
    const s = new Store({ x: 1 });
    const before = s.get();
    s.set({ x: 2 });
    expect(before.x).toBe(1);
  });

  it("stops notifying after unsubscribe", () => {
    const s = new Store({ x: 1 });
    let n = 0;
    const off = s.subscribe(() => n++);
    off();
    s.set({ x: 2 });
    expect(n).toBe(0);
  });
});

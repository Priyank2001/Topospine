/**
 * What the user is pointing at, shared by every view so they all highlight the same nodes.
 *
 *   hovered:  the node under the pointer (transient), or null
 *   selected: the nodes the user clicked, in click order (sticky)
 *
 * Ids are the nodes the user actually picked. What stands in for them under the current
 * thresholds (a merged extremum's representative) is derived (core/selection.ts), never
 * written back here, so lowering pLo again shows the original pick.
 */

import { Listener, Store } from "./Store";

export interface SelectionState {
  hovered: number | null;
  selected: ReadonlySet<number>;
}

const NOTHING: ReadonlySet<number> = new Set();

export class SelectionModel {
  private readonly store = new Store<SelectionState>({ hovered: null, selected: NOTHING });

  get state(): Readonly<SelectionState> {
    return this.store.get();
  }

  subscribe(fn: Listener<SelectionState>): () => void {
    return this.store.subscribe(fn);
  }

  isSelected(id: number): boolean {
    return this.state.selected.has(id);
  }

  hover(id: number | null): void {
    this.store.set({ hovered: id });
  }

  /** Plain click: this node only. */
  selectOnly(id: number): void {
    const s = this.state.selected;
    if (s.size === 1 && s.has(id)) return;
    this.store.set({ selected: new Set([id]) });
  }

  /** Shift-click: add or remove one node. */
  toggle(id: number): void {
    const next = new Set(this.state.selected);
    if (!next.delete(id)) next.add(id);
    this.store.set({ selected: next });
  }

  /** Esc / click on empty space: drop the selection, keep the hover. */
  clear(): void {
    if (this.state.selected.size) this.store.set({ selected: NOTHING });
  }

  /** New dataset: node ids mean something else now. */
  reset(): void {
    this.store.set({ hovered: null, selected: NOTHING });
  }
}

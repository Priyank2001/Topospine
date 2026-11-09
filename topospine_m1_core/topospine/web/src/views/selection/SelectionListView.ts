/** Renders the selection details: a hint line, the pointer row, then one row per selected node. */

import { ISelectionView, NodeRow, SelectionViewModel } from "./contract";

export class SelectionListView implements ISelectionView {
  constructor(private readonly root: HTMLElement) {}

  render(vm: SelectionViewModel): void {
    const heading = el("h2", "Selection");
    const hint = el("p", vm.hint, "selection-hint");
    const list = document.createElement("ul");
    if (vm.hovered) list.append(row(vm.hovered, "Pointer"));
    for (const r of vm.selected) list.append(row(r));
    this.root.replaceChildren(heading, hint, ...(list.children.length ? [list] : []));
  }

  dispose(): void {
    this.root.replaceChildren();
  }
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text: string, className?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  e.textContent = text;
  if (className) e.className = className;
  return e;
}

function row(r: NodeRow, badge?: string): HTMLLIElement {
  const li = document.createElement("li");
  if (badge) li.className = "is-pointer";
  const title = el("span", r.title, "selection-title");
  if (badge) title.append(" ", el("small", badge));
  li.append(title, el("span", r.detail, "selection-detail"));
  if (r.note) li.append(el("span", r.note, "selection-note"));
  return li;
}

/** The selection details list: the node under the pointer and every selected node. */

export interface NodeRow {
  /** e.g. "max #3" */
  readonly title: string;
  /** e.g. "f 0.83 · P 0.41 · 1,204 samples" */
  readonly detail: string;
  /** Empty when the node is drawn; otherwise why not ("merged into max #1", "hidden …"). */
  readonly note: string;
}

export interface SelectionViewModel {
  readonly hovered: NodeRow | null;
  readonly selected: readonly NodeRow[];
  /** One line of help or a count. */
  readonly hint: string;
}

export interface ISelectionView {
  render(vm: SelectionViewModel): void;
  dispose(): void;
}

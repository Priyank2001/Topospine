/** Renders label/value rows into a <dl>. */

import { IStatsView, StatRow } from "./contract";

export class StatsListView implements IStatsView {
  constructor(private readonly list: HTMLElement) {}

  render(rows: readonly StatRow[]): void {
    this.list.replaceChildren(
      ...rows.flatMap(([label, value]) => {
        const dt = document.createElement("dt");
        dt.textContent = label;
        const dd = document.createElement("dd");
        dd.textContent = value;
        return [dt, dd];
      }),
    );
  }

  dispose(): void {
    this.list.replaceChildren();
  }
}

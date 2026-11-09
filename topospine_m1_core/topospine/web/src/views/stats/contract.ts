/** A list of already formatted label/value rows. */

export type StatRow = readonly [label: string, value: string];

export interface IStatsView {
  render(rows: readonly StatRow[]): void;
  dispose(): void;
}

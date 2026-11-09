/**
 * Use cases that span more than one model, so models never subscribe to each other.
 *
 *   start(wanted): fetch the index -> session.setIndex -> open the first dataset
 *   open(name):    session.beginLoad -> fetch -> params.resetForDataset + selection.reset
 *                  -> session.finishLoad
 *
 * Order matters in `open`: thresholds and selection are reset BEFORE the session publishes
 * "ready", in the same tick, so presenters (which render once per tick) never see the new
 * dataset with the previous dataset's thresholds or node ids.
 */

import { DatasetSource } from "../services/DatasetSource";
import { SelectionModel } from "./SelectionModel";
import { SessionModel } from "./SessionModel";
import { SpineParamsModel } from "./SpineParamsModel";

export class Workspace {
  constructor(
    private readonly source: DatasetSource,
    readonly session: SessionModel,
    readonly params: SpineParamsModel,
    readonly selection: SelectionModel,
  ) {}

  async start(wanted?: string | null): Promise<void> {
    try {
      this.session.setIndex(await this.source.index());
    } catch (err) {
      this.session.failIndex(message(err));
      return;
    }
    const first = this.session.initialDataset(wanted);
    if (first) await this.open(first);
  }

  async open(name: string): Promise<void> {
    const requestId = this.session.beginLoad(name);
    try {
      const data = await this.source.load(name);
      if (!this.session.isCurrent(requestId)) return; // superseded: leave the newer load alone
      this.params.resetForDataset(data);
      this.selection.reset();
      this.session.finishLoad(requestId, data);
    } catch (err) {
      this.session.failLoad(requestId, message(err));
    }
  }
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

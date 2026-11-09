/** Real models around a controllable source, opened on a fixture. */

import { SelectionModel } from "../../src/model/SelectionModel";
import { SessionModel } from "../../src/model/SessionModel";
import { SpineFrames } from "../../src/model/SpineFrames";
import { SpineParamsModel } from "../../src/model/SpineParamsModel";
import { Workspace } from "../../src/model/Workspace";
import { ControlledSource, entry, flush } from "../fakes";
import { loadFixture } from "../helpers";

export function models() {
  const source = new ControlledSource([entry("ring", 12), entry("line")]);
  const session = new SessionModel();
  const params = new SpineParamsModel();
  const selection = new SelectionModel();
  const workspace = new Workspace(source, session, params, selection);
  const frames = new SpineFrames(session, params);
  const fixtures = { ring: loadFixture("ring"), line: loadFixture("line") };
  /** Run start() and let `name` finish loading. */
  const open = async (name: "ring" | "line" = "ring") => {
    if (session.state.index.status !== "ready") void workspace.start(name);
    else void workspace.open(name);
    await flush();
    source.resolve(name, fixtures[name]);
    await flush();
  };
  return { source, session, params, selection, workspace, frames, fixtures, open };
}

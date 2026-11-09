/** What the spine canvas draws and what it reports. Fill colours come in; outline colours are the view's (theme). */

import { HighlightItem } from "../../core/selection";
import { RGB } from "../../core/spine/levelColors";
import { SpineGeometry } from "../../core/spine/links";
import { OverlayData } from "../../core/spine/overlay";

export interface SpineViewModel {
  readonly geometry: SpineGeometry;
  /** One fill colour per entry of geometry.levels. */
  readonly levelFills: readonly RGB[];
  readonly overlay: OverlayData;
  /** Node id of each overlay centre, same order (used for picking and highlights). */
  readonly nodeIds: Int32Array;
  readonly showSkeleton: boolean;
  readonly showNodes: boolean;
}

export interface SpineViewEvents {
  /** Pointer moved onto a node (id) or off all nodes (null). */
  nodeHovered(id: number | null): void;
  /** Click (not a drag) on a node; additive = shift held. */
  nodeClicked(id: number, additive: boolean): void;
  /** Click on empty space, or Esc. */
  cleared(): void;
}

export interface ISpineView {
  bind(events: SpineViewEvents): void;
  /** New content: expensive (rebuilds the spine), so presenters call it only when content changes. */
  render(vm: SpineViewModel): void;
  /** Rings around drawn nodes: cheap, called on every selection change. */
  highlight(items: readonly HighlightItem[]): void;
  /** Frame the current content. */
  fit(): void;
  dispose(): void;
}

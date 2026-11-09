/**
 * What a picked node means under the current thresholds, and what to highlight for it.
 *
 * A selected node can be:
 *   visible  - drawn as itself;
 *   merged   - an extremum simplified away at pLo; its representative (the extremum it merged
 *              into) is drawn and stands in for it;
 *   hidden   - not drawn and nothing stands in (a saddle outside [pLo, pHi], or an extremum
 *              whose representative isn't drawn either).
 * Selection keeps the original ids (SelectionModel); everything here is derived per frame.
 */

import { DisplayGraph } from "./displayGraph";
import { MergedRegions } from "./regionStats";
import { EXTREMUM, SpineData } from "./types";

export type NodeStatus =
  | { readonly kind: "visible" }
  | { readonly kind: "merged"; readonly into: number }
  | { readonly kind: "hidden" };

export interface NodeInfo {
  readonly id: number;
  readonly isExtremum: boolean;
  /** f in the dataset's own units (not the height g). */
  readonly value: number;
  /** +Infinity = never cancelled. */
  readonly persistence: number;
  /** Samples in the region drawn for this node at pLo; null for saddles. */
  readonly samples: number | null;
  readonly status: NodeStatus;
  /** The drawn node that represents it, or null when hidden. */
  readonly shownAs: number | null;
}

/** The per-frame facts every lookup needs. */
export interface SelectionContext {
  readonly data: SpineData;
  readonly rep: Int32Array;
  readonly regions: MergedRegions;
  readonly drawn: ReadonlySet<number>;
}

export function drawnNodes(g: DisplayGraph): ReadonlySet<number> {
  return new Set(g.nodes);
}

export function describeNode(ctx: SelectionContext, id: number): NodeInfo {
  const { data: d, rep, regions, drawn } = ctx;
  const isExtremum = d.kind[id] === EXTREMUM;
  let status: NodeStatus;
  let shownAs: number | null;
  if (drawn.has(id)) {
    status = { kind: "visible" };
    shownAs = id;
  } else if (isExtremum && rep[id] !== id && drawn.has(rep[id])) {
    status = { kind: "merged", into: rep[id] };
    shownAs = rep[id];
  } else {
    status = { kind: "hidden" };
    shownAs = null;
  }
  return {
    id,
    isExtremum,
    value: d.value[id],
    persistence: d.persistence[id],
    samples: isExtremum ? regions.sizes[rep[id]] : null,
    status,
    shownAs,
  };
}

export type HighlightStyle = "hovered" | "selected" | "standIn";

export interface HighlightItem {
  readonly node: number;
  readonly style: HighlightStyle;
}

/**
 * Rings to draw: the hovered node (if still drawn), each visible selected node, and the
 * representative of each merged selected node (once, and not if it is itself selected).
 */
export function highlightFor(ctx: SelectionContext, hovered: number | null, selected: Iterable<number>): HighlightItem[] {
  const items: HighlightItem[] = [];
  const ringed = new Set<number>();
  const picks = [...selected];
  for (const id of picks) {
    if (ctx.drawn.has(id)) {
      items.push({ node: id, style: "selected" });
      ringed.add(id);
    }
  }
  for (const id of picks) {
    const shownAs = describeNode(ctx, id).shownAs;
    if (shownAs !== null && !ringed.has(shownAs)) {
      items.push({ node: shownAs, style: "standIn" });
      ringed.add(shownAs);
    }
  }
  if (hovered !== null && ctx.drawn.has(hovered)) items.push({ node: hovered, style: "hovered" });
  return items;
}

/** Short name of a node for labels: "max #3", "min #3", "saddle #12". */
export function nodeLabel(d: SpineData, id: number): string {
  if (d.kind[id] !== EXTREMUM) return `saddle #${id}`;
  return `${d.meta.extremum === "minima" ? "min" : "max"} #${id}`;
}

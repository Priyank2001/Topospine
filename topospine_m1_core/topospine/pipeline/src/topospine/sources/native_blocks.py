"""Our own two blocks of graph extraction (DECISIONS.md D-004).

    AscentRegions    "ascent"    block 1: follow steepest ascent on the run's neighbourhood
                                 to a maximum (Sec. 3.4). Grids and points.
    BoundarySaddles  "boundary"  block 2: one saddle per pair of touching regions, at the
                                 lower end of their highest boundary edge (DEVIATIONS.md #2).
                                 Works on ANY labelling, so it pairs with every region method.

Both are thin adapters: the maths lives in core.gradient_flow, these classes only read
what they need from the ExtractionContext. Neither builds the graph; ComposedSource
hands their outputs to core.assemble_flow.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from topospine.core.gradient_flow import SaddleSet, boundary_saddles, regions_by_ascent
from topospine.sources.base import ExtractionContext


class AscentRegions:
    name = "ascent"

    def labels(self, ctx: ExtractionContext) -> NDArray[np.int64]:
        return regions_by_ascent(ctx.ranks, ctx.neighborhood)

    def report(self) -> dict[str, Any]:
        return {}


class BoundarySaddles:
    name = "boundary"
    requires_regions: str | None = None

    def saddles(self, ctx: ExtractionContext, labels: NDArray[np.int64]) -> SaddleSet:
        return boundary_saddles(ctx.ranks, labels, ctx.neighborhood)

    def report(self) -> dict[str, Any]:
        return {}

"""TTK backend as it was in M1: the `ttk+boundary` preset of ComposedSource (D-001, D-005).

Regions come from TTK's exact discrete gradient, saddles from the same boundary rule the
native source uses, so any difference between the two backends is a difference in
regions only. For TTK's own saddles too, compose TtkRegions + TtkSaddles (ttk_blocks.py).

Kept as a named class so `TtkSource(...)` and `source: {type: ttk}` configs keep working.
Its name stays "ttk" until run.py records the two methods separately (D-006).
"""

from __future__ import annotations

from collections.abc import Sequence

from topospine.sources.composed_source import ComposedSource
from topospine.sources.native_blocks import BoundarySaddles
from topospine.sources.ttk_backend import TtkBackend
from topospine.sources.ttk_blocks import DEFAULT_CANDIDATES, DEFAULT_MIN_SCORE, TtkRegions


class TtkSource(ComposedSource):
    METHODS = ("ttk", "boundary")         # the pair this preset fixes (read by PRESET_METHODS)

    def __init__(self, connectivity: int | None = None, candidates: Sequence[str] = DEFAULT_CANDIDATES,
                 min_score: float = DEFAULT_MIN_SCORE, backend: TtkBackend | None = None) -> None:
        self._ttk_regions = TtkRegions(backend, candidates, min_score)
        super().__init__(self._ttk_regions, BoundarySaddles(), connectivity=connectivity)
        self.name = "ttk"

    @property
    def last_choice(self) -> tuple[str, dict[str, float]] | None:
        """Which segmentation array was used and every candidate's score (for the report)."""
        return self._ttk_regions.last_choice

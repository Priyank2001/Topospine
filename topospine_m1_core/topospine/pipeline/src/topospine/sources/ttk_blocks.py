"""TTK's two blocks of graph extraction (DECISIONS.md D-004).

    TtkRegions  "ttk"  block 1: TTK's maximum regions (a per-sample segmentation array).
    TtkSaddles  "ttk"  block 2: TTK's own saddles (read by ttk_output.ttk_saddles), plus
                       our boundary saddles only where needed to join pieces (D-011).
                       Only valid with TtkRegions (D-007): it looks up each separatrix's
                       peak in the labels, so the labels must be TTK's.

Both read one shared TtkBackend, so a `ttk+ttk` run calls TTK once.

Which array holds the maxima's regions? (D-012)
    The name depends on TTK's ascending/descending convention, so we don't trust a name:
    each candidate is scored by the fraction of its regions that hold exactly one of TTK's
    OWN maxima, and the best wins. (M1 counted maxima of our stencil instead; on noisy 3-D
    data our stencil and TTK's mesh disagree enough that no array passed.)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from topospine.core.gradient_flow import SaddleSet, boundary_saddles
from topospine.core.reconnect import connect_pieces, count_pieces
from topospine.sources.base import ExtractionContext
from topospine.sources.ttk_backend import TtkBackend
from topospine.sources.ttk_output import TtkArrayNames, ttk_maxima, ttk_saddles

DEFAULT_CANDIDATES = ("DescendingManifold", "AscendingManifold")
DEFAULT_MIN_SCORE = 0.5


def compact_labels(raw: NDArray) -> NDArray[np.int64]:
    """Map arbitrary region ids (TTK uses critical-point ids) to 0..M-1."""
    _, inverse = np.unique(np.asarray(raw).ravel(), return_inverse=True)
    return inverse.astype(np.int64)


def maximum_score(labels: NDArray[np.int64], maxima: NDArray[np.int64]) -> float:
    """Fraction of regions that contain exactly one of the given maxima (1.0 = perfect).

    Regions of minima hold zero or several maxima (maxima sit on their borders), so this
    tells the two segmentations apart; "is the region's top a maximum" would not.
    """
    maxima_per_region = np.bincount(labels[maxima], minlength=int(labels.max()) + 1)
    return float((maxima_per_region == 1).mean())


def pick_maximum_regions(
    arrays: Mapping[str, NDArray], maxima: NDArray[np.int64]
) -> tuple[str, NDArray[np.int64], dict[str, float]]:
    scores, labelled = {}, {}
    for name, raw in arrays.items():
        labelled[name] = compact_labels(raw)
        scores[name] = maximum_score(labelled[name], maxima)
    best = max(scores, key=scores.get)
    return best, labelled[best], scores


class TtkRegions:
    name = "ttk"

    def __init__(self, backend: TtkBackend | None = None, candidates: Sequence[str] = DEFAULT_CANDIDATES,
                 min_score: float = DEFAULT_MIN_SCORE, arrays: TtkArrayNames = TtkArrayNames()) -> None:
        self.backend = backend or TtkBackend()
        self.candidates = tuple(candidates)
        self.min_score = float(min_score)
        self.arrays = arrays
        self.last_choice: tuple[str, dict[str, float]] | None = None   # for logging / the report

    def labels(self, ctx: ExtractionContext) -> NDArray[np.int64]:
        out = self.backend.morse_smale(ctx.dataset)
        per_sample = out.per_sample_arrays(ctx.dataset.num_samples)
        found = {name: per_sample[name] for name in self.candidates if name in per_sample}
        if not found:
            raise RuntimeError(f"TTK output has none of the arrays {self.candidates}; "
                               "check the names in your TTK version and pass `candidates`.")
        name, labels, scores = pick_maximum_regions(found, ttk_maxima(out, self.arrays))
        self.last_choice = (name, scores)
        if scores[name] < self.min_score:
            raise RuntimeError(f"no TTK array looks like maxima regions (scores {scores})")
        return labels

    def report(self) -> dict[str, Any]:
        if self.last_choice is None:
            return {}
        name, scores = self.last_choice
        return {"array": name, "score": round(scores[name], 4)}


@dataclass(frozen=True)
class SaddleReport:
    """What happened to TTK's saddles in one run (for the run summary)."""

    kept: int           # TTK saddles with two uphill separatrices
    dropped: int        # fewer than two (D-009)
    added: int          # our boundary saddles added to join pieces (D-011)


class TtkSaddles:
    name = "ttk"
    requires_regions: str | None = "ttk"

    def __init__(self, backend: TtkBackend | None = None, arrays: TtkArrayNames = TtkArrayNames()) -> None:
        self.backend = backend or TtkBackend()
        self.arrays = arrays
        self.last_report: SaddleReport | None = None

    def saddles(self, ctx: ExtractionContext, labels: NDArray[np.int64]) -> SaddleSet:
        result, dropped = ttk_saddles(self.backend.morse_smale(ctx.dataset), labels, self.arrays)
        kept, added, m = result.samples.size, 0, int(labels.max()) + 1
        if count_pieces(result.pairs, m) > 1:      # the boundary scan only runs when needed
            candidates = boundary_saddles(ctx.ranks, labels, ctx.neighborhood)
            result, added = connect_pieces(result, candidates, ctx.ranks, m)
        self.last_report = SaddleReport(kept=kept, dropped=dropped, added=added)
        return result

    def report(self) -> dict[str, Any]:
        return {} if self.last_report is None else asdict(self.last_report)

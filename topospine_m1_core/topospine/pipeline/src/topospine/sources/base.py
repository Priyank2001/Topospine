"""The interfaces of graph extraction: the whole job, and the two blocks it is made of.

    ExtremumGraphSource   Dataset -> FlowDecomposition. What run.py talks to.
    RegionMethod          block 1: which maximum each sample flows up to (labels).
    SaddleMethod          block 2: saddles between those regions (a SaddleSet).

ComposedSource joins one RegionMethod and one SaddleMethod into an ExtremumGraphSource
(DECISIONS.md D-004), so a new method is one class implementing one block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from topospine.core.datasets import Dataset
from topospine.core.gradient_flow import FlowDecomposition, SaddleSet
from topospine.core.neighborhoods import Neighborhood


class ExtremumGraphSource(Protocol):
    """Compute the gradient flow graph of the MAXIMA of dataset.values.

    The pipeline negates values beforehand for a minimum graph, so sources never
    need to know which extremum type the user asked for.
    """

    name: str

    def compute(self, dataset: Dataset) -> FlowDecomposition: ...


@dataclass(frozen=True, eq=False)
class ExtractionContext:
    """What both blocks of one run share, computed once.

    ranks        : sample_ranks(dataset.values), the (f, index) order every block uses.
    neighborhood : the run's single definition of "neighbour" (grid stencil or kNN).
    """

    dataset: Dataset
    ranks: NDArray[np.int64]
    neighborhood: Neighborhood


class RegionMethod(Protocol):
    """Block 1: the region (maximum) every sample belongs to.

    Returns labels 0..M-1, one per sample, every id used. Numbering is free;
    assemble_flow places each region's maximum at its highest sample.
    """

    name: str

    def labels(self, ctx: ExtractionContext) -> NDArray[np.int64]: ...


class SaddleMethod(Protocol):
    """Block 2: the saddles between the regions block 1 found.

    requires_regions: name of the only RegionMethod this works with, or None for any.
    Checked once, when the blocks are joined (D-007).
    """

    name: str
    requires_regions: str | None

    def saddles(self, ctx: ExtractionContext, labels: NDArray[np.int64]) -> SaddleSet: ...

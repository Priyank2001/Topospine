"""The one interface every extremum-graph backend implements."""

from __future__ import annotations

from typing import Protocol

from topospine.core.datasets import Dataset
from topospine.core.gradient_flow import FlowDecomposition


class ExtremumGraphSource(Protocol):
    """Compute the gradient flow graph of the MAXIMA of dataset.values.

    The pipeline negates values beforehand for a minimum graph, so sources never
    need to know which extremum type the user asked for.
    """

    name: str

    def compute(self, dataset: Dataset) -> FlowDecomposition: ...

"""Our own backend: steepest ascent on a grid stencil or a symmetrised kNN graph.

Works for every dataset kind, needs only NumPy/SciPy, and is the reference the
TTK/TACHYON adapters are compared against.
"""

from __future__ import annotations

from topospine.core.datasets import Dataset, GridDataset
from topospine.core.gradient_flow import FlowDecomposition, decompose
from topospine.core.neighborhoods import GridNeighborhood, KnnNeighborhood, Neighborhood


class NativeSource:
    name = "native"

    def __init__(self, connectivity: int | None = None, k: int = 15) -> None:
        """connectivity: grid stencil size (default: the full stencil, 8 in 2-D / 26 in 3-D,
        which gives far fewer spurious maxima on noisy data than the face stencil).
        k: neighbours per point for point data."""
        self.connectivity = connectivity
        self.k = int(k)

    def neighborhood(self, dataset: Dataset) -> Neighborhood:
        if isinstance(dataset, GridDataset):
            conn = self.connectivity or (3 ** len(dataset.shape) - 1)
            return GridNeighborhood(dataset.shape, conn)
        return KnnNeighborhood(dataset.points, self.k)

    def compute(self, dataset: Dataset) -> FlowDecomposition:
        return decompose(dataset.values, self.neighborhood(dataset))

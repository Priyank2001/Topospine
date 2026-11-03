"""One region method + one saddle method = an ExtremumGraphSource (DECISIONS.md D-004).

    dataset ─► ExtractionContext (ranks, neighbourhood: built once)
                 ├─► regions.labels(ctx)            ─► labels
                 └─► saddles.saddles(ctx, labels)   ─► SaddleSet
                                     assemble_flow  ─► FlowDecomposition

Owns the run's neighbourhood (stencil / k) so both blocks agree on what "neighbour"
means. Does not know any concrete method: those come from the registries.
"""

from __future__ import annotations

from topospine.core.datasets import Dataset, GridDataset
from topospine.core.gradient_flow import FlowDecomposition, assemble_flow, sample_ranks
from topospine.core.neighborhoods import GridNeighborhood, KnnNeighborhood, Neighborhood
from topospine.sources.base import ExtractionContext, RegionMethod, SaddleMethod

DEFAULT_K = 15


class ComposedSource:
    def __init__(self, regions: RegionMethod, saddles: SaddleMethod,
                 connectivity: int | None = None, k: int = DEFAULT_K) -> None:
        """connectivity: grid stencil size (default: the full stencil, 8 in 2-D / 26 in 3-D,
        which gives far fewer spurious maxima on noisy data than the face stencil).
        k: neighbours per point for point data."""
        need = saddles.requires_regions
        if need is not None and need != regions.name:
            # Fail before any data is loaded (D-007 explains why the mix is unsafe).
            raise ValueError(f"saddle method {saddles.name!r} works only with region method "
                             f"{need!r}, not {regions.name!r} (see docs/DECISIONS.md D-007)")
        self.regions = regions
        self.saddles = saddles
        self.connectivity = connectivity
        self.k = int(k)
        self.name = f"{regions.name}+{saddles.name}"

    def neighborhood(self, dataset: Dataset) -> Neighborhood:
        if isinstance(dataset, GridDataset):
            conn = self.connectivity or (3 ** len(dataset.shape) - 1)
            return GridNeighborhood(dataset.shape, conn)
        return KnnNeighborhood(dataset.points, self.k)

    def compute(self, dataset: Dataset) -> FlowDecomposition:
        ctx = ExtractionContext(dataset, sample_ranks(dataset.values), self.neighborhood(dataset))
        labels = self.regions.labels(ctx)
        return assemble_flow(dataset.values, labels, self.saddles.saddles(ctx, labels), ctx.ranks)

"""Our own backend: the `ascent+boundary` preset of ComposedSource.

Steepest ascent on a grid stencil or a symmetrised kNN graph, then our boundary
saddles. Works for every dataset kind, needs only NumPy/SciPy, and is the reference
the TTK adapters are compared against.

Kept as a named class (not just a registry entry) so `NativeSource(connectivity, k)`
and `source: {type: native}` configs keep working unchanged (D-005). It adds no
behaviour: the neighbourhood and the compute step are ComposedSource's.
Its name stays "native" so meta.json is unchanged until run.py records the two
methods separately (D-006, file 7 of M3).
"""

from __future__ import annotations

from topospine.sources.composed_source import DEFAULT_K, ComposedSource, Connectivity
from topospine.sources.native_blocks import AscentRegions, BoundarySaddles


class NativeSource(ComposedSource):
    METHODS = ("ascent", "boundary")      # the pair this preset fixes (read by PRESET_METHODS)

    def __init__(self, connectivity: Connectivity = None, k: int = DEFAULT_K) -> None:
        super().__init__(AscentRegions(), BoundarySaddles(), connectivity=connectivity, k=k)
        self.name = "native"

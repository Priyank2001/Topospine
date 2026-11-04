"""Pure NumPy core. Nothing in this package imports TTK, VTK, ParaView or file I/O.

Pipeline (Correa et al. 2011, Sec. 3.4 + Algorithm 1):

    values + Neighborhood --decompose()--> FlowDecomposition (GradientFlowGraph + labels)
                          --compute_persistence()--> Persistence (P, P*, merged_into)
                          --filter_graph()--> ThresholdedGraph for R = [p_lo, p_hi]
"""

from topospine.core.extremum_graph import (
    ThresholdedGraph,
    arc_curve,
    extrema_curve,
    filter_graph,
    representatives,
)
from topospine.core.gradient_flow import (
    FlowDecomposition,
    SaddleSet,
    assemble_flow,
    boundary_saddles,
    decompose,
    graph_from_regions,
    regions_by_ascent,
    sample_ranks,
    steepest_ascent,
)
from topospine.core.graph import GradientFlowGraph, NodeKind
from topospine.core.neighborhoods import FreudenthalNeighborhood, GridNeighborhood, KnnNeighborhood, Neighborhood
from topospine.core.persistence import Persistence, compute_persistence
from topospine.core.reconnect import connect_pieces, count_pieces
from topospine.core.region_stats import RegionHistograms, region_histograms

__all__ = [
    "FlowDecomposition",
    "GradientFlowGraph",
    "FreudenthalNeighborhood",
    "GridNeighborhood",
    "KnnNeighborhood",
    "Neighborhood",
    "NodeKind",
    "Persistence",
    "RegionHistograms",
    "SaddleSet",
    "ThresholdedGraph",
    "arc_curve",
    "assemble_flow",
    "boundary_saddles",
    "compute_persistence",
    "connect_pieces",
    "count_pieces",
    "decompose",
    "extrema_curve",
    "filter_graph",
    "graph_from_regions",
    "region_histograms",
    "regions_by_ascent",
    "representatives",
    "sample_ranks",
    "steepest_ascent",
]

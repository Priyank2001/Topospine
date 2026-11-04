import sys

import numpy as np
import pytest

from topospine.core.datasets import GridDataset
from topospine.io.synthetic import bumps_grid, sample_points
from topospine.sources.native_source import NativeSource
from topospine.sources.ttk_backend import (
    MorseSmaleOutput,
    PortArrays,
    TtkBackend,
    import_ttk,
    numpy_to_image,
    read_ports,
    run_morse_smale,
)
from topospine.sources.ttk_source import TtkSource


@pytest.fixture
def bumps2d():
    return bumps_grid((40, 30), centers=[[0.25, 0.3], [0.7, 0.7]], heights=[1.0, 0.8], width=0.12)


class CountingRunner:
    def __init__(self, output=MorseSmaleOutput(())):
        self.calls, self.output = [], output

    def __call__(self, dataset):
        self.calls.append(dataset)
        return self.output


def test_backend_runs_once_per_dataset(bumps2d):
    runner = CountingRunner()
    backend = TtkBackend(runner)
    first = backend.morse_smale(bumps2d)
    assert backend.morse_smale(bumps2d) is first                  # regions + saddles blocks: one TTK run
    assert len(runner.calls) == 1


def test_backend_reruns_for_a_new_dataset(bumps2d):
    runner = CountingRunner()
    backend = TtkBackend(runner)
    flipped = GridDataset(bumps2d.name, -bumps2d.values, bumps2d.spacing, bumps2d.origin)   # a minimum graph
    backend.morse_smale(bumps2d)
    backend.morse_smale(flipped)
    assert runner.calls == [bumps2d, flipped]


def test_backend_rejects_points_before_running():
    runner = CountingRunner()
    with pytest.raises(ValueError, match="grid"):
        TtkBackend(runner).morse_smale(sample_points("ackley", 2, 50, -1, 1))
    assert runner.calls == []


def test_per_sample_arrays_searches_every_port_by_length():
    n = 6
    out = MorseSmaleOutput((
        PortArrays({"CellDimension": np.zeros(3), "Same": np.full(n, 1)}, {}),        # critical points
        PortArrays({}, {"SourceId": np.arange(n)}),                                   # cell arrays never count
        PortArrays({"DescendingManifold": np.arange(n), "Same": np.full(n, 2)}, {}),  # segmentation
    ))
    found = out.per_sample_arrays(n)
    assert sorted(found) == ["DescendingManifold", "Same"]
    assert found["Same"].tolist() == [1] * n                       # first port wins on a name clash


def test_ttk_source_reads_through_its_backend(bumps2d):
    native = NativeSource().compute(bumps2d)
    peaks = native.graph.samples[native.graph.maxima]
    cp = PortArrays({"CellDimension": np.full(peaks.size, 2), "CellId": np.arange(peaks.size),
                     "ttkVertexScalarField": peaks}, {})
    seg = PortArrays({"DescendingManifold": native.labels * 3 + 7, "Other": np.zeros(5)}, {})
    runner = CountingRunner(MorseSmaleOutput((cp, seg)))
    src = TtkSource(backend=TtkBackend(runner))
    dec = src.compute(bumps2d)
    assert np.array_equal(dec.graph.values, native.graph.values)
    assert src.last_choice[0] == "DescendingManifold"
    assert len(runner.calls) == 1


def test_ttk_source_reports_missing_arrays(bumps2d):
    runner = CountingRunner(MorseSmaleOutput((PortArrays({"Nope": np.zeros(bumps2d.num_samples)}, {}),)))
    with pytest.raises(RuntimeError, match="none of the arrays"):
        TtkSource(backend=TtkBackend(runner)).compute(bumps2d)


def test_import_ttk_explains_how_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "topologytoolkit", None)      # makes the import fail
    with pytest.raises(RuntimeError, match="conda install"):
        import_ttk()


class FakeAlgorithm:
    def __init__(self, outputs):
        self.outputs = outputs

    def GetNumberOfOutputPorts(self):
        return len(self.outputs)

    def GetOutputDataObject(self, port):
        return self.outputs[port]


def test_read_ports_copies_vtk_arrays():
    pytest.importorskip("vtkmodules")
    from vtkmodules.util.numpy_support import numpy_to_vtk
    from vtkmodules.vtkCommonCore import vtkStringArray
    from vtkmodules.vtkCommonDataModel import vtkPolyData

    img = numpy_to_image(np.arange(6.0).reshape(2, 3), spacing=(1.0, 1.0), origin=(0.0, 0.0))
    poly = vtkPolyData()
    ids = numpy_to_vtk(np.array([4, 5], dtype=np.int64), deep=True)
    ids.SetName("SourceId")
    poly.GetCellData().AddArray(ids)
    text = vtkStringArray()
    text.SetName("Label")
    poly.GetCellData().AddArray(text)

    out = read_ports(FakeAlgorithm([img, poly, None]))
    assert out.ports[0].point["f"].tolist() == list(range(6))
    assert list(out.ports[1].cell) == ["SourceId"]                 # string array skipped
    assert out.ports[2] == PortArrays({}, {})                      # missing port keeps its slot
    assert not out.ports[0].point["f"].flags.writeable             # shared by two blocks: read-only


@pytest.mark.slow
def test_real_ttk_output_layout(bumps2d):
    pytest.importorskip("topologytoolkit")
    out = run_morse_smale(bumps2d)
    assert {"CellDimension", "CellId", "ttkVertexScalarField"} <= set(out.ports[0].point)
    assert {"SourceId", "DestinationId", "SeparatrixType"} <= set(out.ports[1].cell)
    assert {"AscendingManifold", "DescendingManifold"} <= set(out.per_sample_arrays(bumps2d.num_samples))

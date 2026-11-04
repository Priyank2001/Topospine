import numpy as np
import pytest

from topospine.io.readers import read_dataset, read_npy_grid, read_points_csv, read_points_npy, read_raw, read_vti


def test_raw_orientation_and_byte_order(tmp_path):
    data = np.arange(24, dtype=">u2")          # x fastest, big-endian on disk
    path = tmp_path / "v.raw"
    data.tofile(path)
    g = read_raw(path, dims_xyz=[4, 3, 2], dtype="uint16", byte_order="big", spacing_xyz=[1, 2, 3])
    assert g.shape == (2, 3, 4)                 # numpy (z, y, x)
    assert g.values[0, 0, 1] == 1               # one step in x = next value on disk
    assert g.values[1, 0, 0] == 12              # one step in z = one 4x3 slice
    assert g.spacing == (3.0, 2.0, 1.0)         # stored in array order


def test_raw_size_mismatch(tmp_path):
    path = tmp_path / "v.raw"
    np.zeros(10, dtype=np.uint8).tofile(path)
    with pytest.raises(ValueError, match="need 12"):
        read_raw(path, dims_xyz=[3, 4])


def test_npy_grid(tmp_path):
    np.save(tmp_path / "f.npy", np.ones((5, 6)))
    g = read_npy_grid(tmp_path / "f.npy", spacing_xyz=[0.5, 2.0])
    assert g.shape == (5, 6) and g.spacing == (2.0, 0.5) and g.name == "f"


def test_csv_points_with_feature_subset(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("a,b,c,y\n0,10,7,1\n2,10,8,2\n4,10,9,3\n")
    p = read_points_csv(path, value_column="y", feature_columns=["a", "b"], normalize="zscore")
    assert p.feature_names == ("a", "b") and p.dim == 2
    assert np.allclose(p.points[:, 0], [-1.2247449, 0, 1.2247449])
    assert np.allclose(p.points * p.scale + p.offset, [[0, 10], [2, 10], [4, 10]])
    assert p.values.tolist() == [1, 2, 3]


def test_csv_errors(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("a,y\n0,1\n1,2\n")
    with pytest.raises(ValueError, match="value column"):
        read_points_csv(path, value_column="z")
    with pytest.raises(ValueError, match="feature columns"):
        read_points_csv(path, value_column="y", feature_columns=["q"])


def test_points_npy(tmp_path):
    np.save(tmp_path / "p.npy", np.c_[np.random.default_rng(0).normal(size=(20, 3)), np.arange(20)])
    p = read_points_npy(tmp_path / "p.npy", normalize="none")
    assert p.dim == 3 and p.values[-1] == 19


def test_vti_roundtrip(tmp_path):
    pytest.importorskip("vtkmodules")
    from vtkmodules.vtkIOXML import vtkXMLImageDataWriter

    from topospine.sources.ttk_backend import numpy_to_image

    values = np.arange(24.0).reshape(2, 3, 4)
    w = vtkXMLImageDataWriter()
    w.SetFileName(str(tmp_path / "v.vti"))
    w.SetInputData(numpy_to_image(values, spacing=(3.0, 2.0, 1.0), origin=(0.0, 0.0, 0.0), name="rho"))
    w.Write()
    g = read_vti(tmp_path / "v.vti")
    assert np.array_equal(g.values, values) and g.spacing == (3.0, 2.0, 1.0) and g.value_name == "rho"


def test_unknown_reader(tmp_path):
    with pytest.raises(ValueError, match="unknown dataset type"):
        read_dataset("hdf5", tmp_path / "x")

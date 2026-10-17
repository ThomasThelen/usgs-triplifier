import gzip
import zipfile
from pathlib import Path

import numpy as np
import pyogrio.raw
import pytest
import shapely
from rdflib import Graph

from usgs_triplifier.config import config


def parse_nt_gz(path):
    """Parse a gzipped N-Triples output file into a Graph for assertions."""
    graph = Graph()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        graph.parse(f, format="nt")
    return graph


@pytest.fixture()
def data_dirs(tmp_path, monkeypatch):
    """Point the shared config singleton at per-test input/output directories."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(config, "input_directory", input_dir)
    monkeypatch.setattr(config, "output_directory", output_dir)
    # Isolate the archive too (not created: code that needs it mkdirs it)
    monkeypatch.setattr(config, "archive_output_directory", tmp_path / "archive")
    return input_dir, output_dir


def make_gpkg_zip(
    input_dir: Path, zip_name: str, geometries: dict[int, shapely.Geometry | None]
) -> Path:
    """
    Builds a zipped GeoPackage in input_dir shaped like the USGS FullModel.

    :param input_dir: Directory the triplifiers read zips from.
    :param zip_name: Name of the zip file (must match *_GPKG.zip).
    :param geometries: Mapping of feature id to shapely geometry, or None
        for a feature without one.
    :return: Path to the zip file.
    """
    gpkg_path = input_dir / "data.gpkg"
    feature_ids = np.array(list(geometries), dtype="int64")
    wkb = np.array(
        [None if g is None else shapely.to_wkb(g) for g in geometries.values()],
        dtype=object,
    )
    pyogrio.raw.write(
        gpkg_path,
        geometry=wkb,
        field_data=[feature_ids],
        fields=["feature_id"],
        layer="DomesticNames",
        driver="GPKG",
        geometry_type="MultiPoint Z",
        crs="EPSG:4326",
    )
    zip_path = input_dir / zip_name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(gpkg_path, "data.gpkg")
    gpkg_path.unlink()
    return zip_path


def make_text_zip(input_dir, zip_name, txt_name, lines):
    """
    Build a zip containing one pipe-delimited text file in ``input_dir``.

    :param input_dir: Directory the triplifiers read zips from.
    :param zip_name: Name of the zip file (must match the triplifier's glob).
    :param txt_name: Name of the text file inside the zip.
    :param lines: Text lines (header first) to join with newlines.
    """
    zip_path = input_dir / zip_name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(txt_name, "\n".join(lines) + "\n")
    return zip_path

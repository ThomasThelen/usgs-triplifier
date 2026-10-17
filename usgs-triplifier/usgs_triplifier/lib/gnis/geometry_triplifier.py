import gzip
import logging
import tempfile
import zipfile
from pathlib import Path

import pyogrio
import pyogrio.raw
import shapely
from rdflib import Literal
from tqdm import tqdm

from .triplifier import NTStreamSink, normalize_feature_id
from ...config import config

logger = logging.getLogger(__name__)

FEATURES_LAYER = "DomesticNames"

# Rows per GDAL read
BATCH_SIZE = 100_000

# Same CRS prefix the point geometries carry, so every WKT literal in the
# dataset is self-describing
CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"


def get_gpkg_zip_files(pattern: str = "*_GPKG.zip") -> list[Path]:
    """
    Get list of GPKG zip files from the input directory.

    :param pattern: Glob pattern to match zip files.
    :return: List of paths to zip files.
    """
    return sorted(config.input_directory.glob(pattern))


def triplify_geometries(output_basename: str = "geometries") -> NTStreamSink:
    """
    Stream a multipoint geometry for every feature in the staged GeoPackages.

    Each feature gets ``geosparql:hasGeometry`` to a ``usgeo-multipoint``
    node whose ``geosparql:asWKT`` is the 2D multipoint. The source declares
    Z coordinates, but they are always 0 (GNIS keeps elevation as an
    attribute), so they are dropped on read.

    :param output_basename: Basename for the output file.
    :return: The sink the triples were streamed through.
    :raises FileNotFoundError: If no GPKG zip is staged.
    """
    zip_files = get_gpkg_zip_files()

    if not zip_files:
        raise FileNotFoundError(f"No GPKG zip files found in {config.input_directory}")

    output_dir = config.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_basename}.nt.gz"

    with gzip.open(output_path, "wt", encoding="utf-8") as out:
        sink = NTStreamSink(out)
        for zip_path in zip_files:
            logger.info(f"Processing {zip_path.name}")
            with zipfile.ZipFile(zip_path, "r") as zf:
                gpkg_files = [f for f in zf.namelist() if f.endswith(".gpkg")]
                with tempfile.TemporaryDirectory() as tmpdir:
                    for gpkg_file in gpkg_files:
                        zf.extract(gpkg_file, tmpdir)
                        _triplify_layer(Path(tmpdir) / gpkg_file, sink)

    logger.info(f"Output written to {output_path}")
    return sink


def _triplify_layer(gpkg_path: Path, sink: NTStreamSink) -> None:
    """
    Reads the features layer in batches and emits one multipoint per row.

    Rows without a geometry are skipped; the rest are written at full
    coordinate precision.

    :param gpkg_path: Path to the extracted GeoPackage.
    :param sink: Streaming triple sink the geometry triples are written to.
    """
    total = pyogrio.read_info(gpkg_path, layer=FEATURES_LAYER)["features"]
    pbar = tqdm(
        total=total,
        unit="rows",
        desc=f"Geometries {gpkg_path.name}",
        bar_format="{l_bar}{bar:40}{r_bar}",
    )

    for offset in range(0, total, BATCH_SIZE):
        _, _, wkb, (feature_ids,) = pyogrio.raw.read(
            gpkg_path,
            layer=FEATURES_LAYER,
            columns=["feature_id"],
            force_2d=True,
            skip_features=offset,
            max_features=BATCH_SIZE,
        )
        geometries = shapely.from_wkb(wkb)
        for feature_id, geometry in zip(feature_ids.tolist(), geometries):
            if geometry is None or geometry.is_empty:
                continue
            # Full precision: the coordinates are published as given
            wkt = shapely.to_wkt(geometry, rounding_precision=-1)
            _add_geometry(sink, normalize_feature_id(feature_id), wkt)
        pbar.update(len(feature_ids))

    pbar.close()


def _add_geometry(sink: NTStreamSink, feature_id: str, wkt: str) -> None:
    """
    Links a feature to its multipoint node and attaches the WKT literal.

    :param sink: Streaming triple sink.
    :param feature_id: Canonical feature id, as used in gnisf: IRIs.
    :param wkt: 2D multipoint WKT, without a CRS prefix.
    """
    prefixes = config.prefix_list
    geosparql = prefixes["geosparql"]
    feature = prefixes["gnisf"][feature_id]
    geometry = prefixes["usgeo-multipoint"][f"gnisf.{feature_id}"]

    sink.add((feature, geosparql["hasGeometry"], geometry))
    sink.add(
        (
            geometry,
            geosparql["asWKT"],
            Literal(f"{CRS84}{wkt}", datatype=geosparql["wktLiteral"]),
        )
    )

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import ClassVar

import pyogrio
import pyogrio.raw
import shapely
from tqdm import tqdm

from ...config import config
from ...output_files import OutputFiles
from ...usgs_products import UsgsProducts
from .identifiers import FeatureIds
from .rdf import NTriplesWriter, Terms


class GeometryTriplifier:
    """
    Converts the multipoint geometries in the GeoPackage into geometries.nt.gz.
    """

    # Layer holding one row per feature
    LAYER: ClassVar[str] = "DomesticNames"

    # Rows read from the layer per call
    BATCH_SIZE: ClassVar[int] = 100_000

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def run(self) -> int:
        """
        Writes a geometry for every feature in the GeoPackage zips in the
        input directory.

        :return: Number of triples written.
        :raises FileNotFoundError: If the input directory has no GeoPackage zip.
        """
        pattern = UsgsProducts.GEOPACKAGE.pattern
        zip_paths = sorted(config.input_directory.glob(pattern))
        if not zip_paths:
            raise FileNotFoundError(
                f"No zip files matching {pattern} in {config.input_directory}"
            )

        path = config.output_directory / OutputFiles.GEOMETRIES
        with NTriplesWriter(path) as writer:
            for zip_path in zip_paths:
                self._log.info(f"Reading geometries from {zip_path.name}")
                with zipfile.ZipFile(zip_path, "r") as zf:
                    names = [n for n in zf.namelist() if n.endswith(".gpkg")]
                    # GDAL reads a GeoPackage from a file, so it is extracted
                    with tempfile.TemporaryDirectory() as tmpdir:
                        for name in names:
                            zf.extract(name, tmpdir)
                            self._read_layer(Path(tmpdir) / name, writer)
        self._log.info(f"Wrote {len(writer)} triples to {path}")
        return len(writer)

    def _read_layer(self, gpkg_path: Path, writer: NTriplesWriter) -> None:
        """
        Reads the features layer in batches and writes one multipoint per
        feature, at full coordinate precision. Features without a geometry
        are skipped.

        :param gpkg_path: Path of the extracted GeoPackage.
        :param writer: Writer the geometry triples are added to.
        """
        total = pyogrio.read_info(gpkg_path, layer=self.LAYER)["features"]
        progress = tqdm(
            total=total,
            unit="rows",
            desc=gpkg_path.name,
            bar_format="{l_bar}{bar:40}{r_bar}",
        )
        for offset in range(0, total, self.BATCH_SIZE):
            _, _, wkb, (feature_ids,) = pyogrio.raw.read(
                gpkg_path,
                layer=self.LAYER,
                columns=["feature_id"],
                force_2d=True,
                skip_features=offset,
                max_features=self.BATCH_SIZE,
            )
            for feature_id, geometry in zip(
                feature_ids.tolist(), shapely.from_wkb(wkb)
            ):
                if geometry is None or geometry.is_empty:
                    continue
                wkt = shapely.to_wkt(geometry, rounding_precision=-1)
                self._add_geometry(writer, FeatureIds.normalize(feature_id), wkt)
            progress.update(len(feature_ids))
        progress.close()

    @staticmethod
    def _add_geometry(writer: NTriplesWriter, feature_id: str, wkt: str) -> None:
        """
        Links a feature to its multipoint node and attaches the WKT literal.

        :param writer: Writer the triples are added to.
        :param feature_id: Canonical feature id, as used in gnisf: IRIs.
        :param wkt: 2D multipoint WKT, without a CRS prefix.
        """
        prefixes = config.prefix_list
        geosparql = prefixes["geosparql"]
        geometry = prefixes["usgeo-multipoint"][f"gnisf.{feature_id}"]
        writer.add((prefixes["gnisf"][feature_id], geosparql["hasGeometry"], geometry))
        writer.add((geometry, geosparql["asWKT"], Terms.wkt_literal(wkt)))

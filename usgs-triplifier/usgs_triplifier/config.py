from pathlib import Path
from typing import ClassVar

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings
from rdflib import Namespace


class Config(BaseSettings):
    """
    Settings for the triplifiers, crosswalks and release steps, read from
    environment variables (the field aliases) with the defaults below.
    """

    # Directory the default input, output and archive directories are in
    DATA_DIR: ClassVar[Path] = Path(__file__).parent.parent / "data"

    # Base IRI of the gnis:, gnisf:, gnisf-alias:, usgs: and nhd: namespaces
    lod_base: str = Field(default="http://gnis-ld.org/lod", alias="LOD_BASE")
    # Base IRI of the usgeo-* geometry namespaces
    geo_base: str = Field(default="http://gnis-ld.org/geometry", alias="GEO_BASE")

    # Input directory for downloaded GNIS data
    input_directory: Path = Field(
        default=DATA_DIR / "geographic_names", alias="GNIS_INPUT_DIRECTORY"
    )

    # Output directory for generated RDF files
    output_directory: Path = Field(
        default=DATA_DIR / "output" / "gnis", alias="RDF_OUTPUT_DIRECTORY"
    )

    # Directory the release dump (gnis-ld-<yymmdd>.nt.gz + .meta.json sidecar)
    # is exported to; the website serves this directory at /archive
    archive_output_directory: Path = Field(
        default=DATA_DIR / "archive", alias="ARCHIVE_OUTPUT_DIRECTORY"
    )

    # Public website base URL, used for release download links in metadata
    site_base: str = Field(default="https://gnis-ld.org", alias="SITE_BASE")

    # Date (YYYY-MM-DD) of the legacy dump in the input directory. A legacy
    # dump is a GNIS export in the file format USGS used until 2021. When set,
    # the triplifiers read that format and the release is dated with this
    # value. When unset, the current USGS products are read.
    legacy_dump_date: str | None = Field(default=None, alias="LEGACY_DUMP_DATE")

    # Date (YYYY-MM-DD) to put on the release instead of the time of the run.
    # Ignored when legacy_dump_date is set.
    release_date: str | None = Field(default=None, alias="RELEASE_DATE")

    # SPARQL endpoint the crosswalk links are harvested from (P590 backlinks)
    wikidata_endpoint: str = Field(
        default="https://query.wikidata.org/sparql", alias="WIKIDATA_ENDPOINT"
    )

    # GeoNames US dump for the name-and-distance alignment
    geonames_url: str = Field(
        default="https://download.geonames.org/export/dump/US.zip",
        alias="GEONAMES_URL",
    )

    # Furthest a same-named GeoNames candidate may sit from the GNIS
    # coordinates and still be accepted as the same feature
    geonames_max_distance_m: float = Field(
        default=10_000, alias="GEONAMES_MAX_DISTANCE_M"
    )

    # Tighter threshold for point-like classes (populated places, springs,
    # buildings), whose coordinates disagree far less between gazetteers
    # than extended features like streams and ridges
    geonames_point_max_distance_m: float = Field(
        default=5_000, alias="GEONAMES_POINT_MAX_DISTANCE_M"
    )

    # A winning candidate must be unambiguous: the runner-up must be this
    # many times farther away, or trail by the minimum gap below, or the
    # feature is left unlinked
    geonames_ambiguity_ratio: float = Field(
        default=2.0, alias="GEONAMES_AMBIGUITY_RATIO"
    )
    geonames_ambiguity_min_gap_m: float = Field(
        default=2_000, alias="GEONAMES_AMBIGUITY_MIN_GAP_M"
    )

    # Distinct subjects sampled per generated dump for the SHACL gate
    shacl_sample_subjects: int = Field(default=2_000, alias="SHACL_SAMPLE_SUBJECTS")

    # Census national gazetteer files (the ANSI code column is the GNIS id)
    census_gazetteer_base: str = Field(
        default="https://www2.census.gov/geo/docs/maps-data/data/gazetteer",
        alias="CENSUS_GAZETTEER_BASE",
    )
    census_gazetteer_year: int = Field(default=2025, alias="CENSUS_GAZETTEER_YEAR")

    # Static prefixes that don't depend on config values
    _static_prefixes: ClassVar[dict[str, Namespace]] = {
        "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
        "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),
        "owl": Namespace("http://www.w3.org/2002/07/owl#"),
        "xsd": Namespace("http://www.w3.org/2001/XMLSchema#"),
        "geosparql": Namespace("http://www.opengis.net/ont/geosparql#"),
        "qudt": Namespace("http://qudt.org/schema/qudt/"),
        "unit": Namespace("http://qudt.org/vocab/unit/"),
        "ago": Namespace("http://awesemantic-geo.link/ontology/"),
        "geonames": Namespace("http://sws.geonames.org/"),
    }

    @property
    def legacy_dump(self) -> bool:
        """
        Reports whether the input directory holds a legacy dump.

        :return: True when legacy_dump_date is set.
        """
        return self.legacy_dump_date is not None

    @computed_field
    @property
    def prefix_list(self) -> dict[str, Namespace]:
        return {
            **self._static_prefixes,
            "usgs": Namespace(f"{self.lod_base}/usgs/ontology/"),
            "gnis": Namespace(f"{self.lod_base}/gnis/ontology/"),
            "gnisf": Namespace(f"{self.lod_base}/gnis/feature/"),
            "gnisf-alias": Namespace(f"{self.lod_base}/gnis/feature-alias/"),
            "nhd": Namespace(f"{self.lod_base}/nhd/ontology/"),
            "nhdf": Namespace(f"{self.lod_base}/nhd/feature/"),
            "usgeo-point": Namespace(f"{self.geo_base}/point/"),
            "usgeo-multipoint": Namespace(f"{self.geo_base}/multipoint/"),
            "usgeo-linestring": Namespace(f"{self.geo_base}/linestring/"),
            "usgeo-multilinestring": Namespace(f"{self.geo_base}/multilinestring/"),
            "usgeo-polygon": Namespace(f"{self.geo_base}/polygon/"),
            "usgeo-multipolygon": Namespace(f"{self.geo_base}/multipolygon/"),
        }

    model_config = {"populate_by_name": True}

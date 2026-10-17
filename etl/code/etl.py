import logging
import sys
from datetime import datetime, timezone

import requests

from usgs_triplifier.lib.archive_exporter import export_historical, export_release
from usgs_triplifier.lib.census_crosswalk import build_census_crosswalk
from usgs_triplifier.lib.crosswalk import build_crosswalk
from usgs_triplifier.lib.dataset_downloader import DatasetDownloader
from usgs_triplifier.lib.dedup import remove_duplicate_triples
from usgs_triplifier.lib.geonames_crosswalk import build_geonames_crosswalk
from usgs_triplifier.lib.dataset_metadata import write_dataset_metadata
from usgs_triplifier.lib.retention import build_retained
from usgs_triplifier.lib.validation import validate_release
from usgs_triplifier.lib.gnis import (
    UnitsTriplifier,
    FeaturesTriplifier,
    NamesTriplifier,
    HistoryTriplifier,
)
from usgs_triplifier.lib.gnis.geometry_triplifier import triplify_geometries
from config import config
from graphdb_adapter import GraphDBAdapter

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("etl")


def main() -> None:
    if config.legacy_dump:
        logger.info(
            f"Reading the {config.legacy_dump_date} legacy dump from the input "
            "directory; skipping the download"
        )
    elif config.download_data:
        logger.info("Downloading...")
        DatasetDownloader.download()
    else:
        logger.info("DOWNLOAD_DATA is disabled, skipping download")

    logger.info("Transforming into RDF...")
    # Leftovers from a previous run would otherwise leak into the release
    # export, which sweeps every generated file in the output directory
    for pattern in ("*.ttl", "*.nt.gz"):
        for stale in config.output_directory.glob(pattern):
            stale.unlink()
    for triplifier in [
        FeaturesTriplifier,
        NamesTriplifier,
        HistoryTriplifier,
        UnitsTriplifier,
    ]:
        triplifier()

    if not config.legacy_dump:
        triplify_geometries()

    # The crosswalks also run for legacy dumps because the links are keyed on
    # GNIS feature ids, which do not change between dumps.
    logger.info("Harvesting crosswalk links from Wikidata")
    build_crosswalk()

    logger.info("Aligning against the GeoNames US gazetteer")
    build_geonames_crosswalk()

    logger.info("Joining Census GEOIDs from the national gazetteer")
    build_census_crosswalk()

    # The triplifiers stream instead of building graphs, so exact duplicates
    # survive to this point; drop them before anything is published or loaded
    logger.info("Removing duplicate triples")
    remove_duplicate_triples()

    release_date = config.legacy_dump_date or config.release_date
    build_time = (
        datetime.fromisoformat(release_date).replace(tzinfo=timezone.utc)
        if release_date
        else datetime.now(timezone.utc)
    )

    logger.info("Validating the release against the SHACL shapes")
    if not validate_release():
        logger.error("SHACL validation failed; not exporting this release")
        sys.exit(1)

    logger.info("Exporting release dump to the archive")
    archive_path = export_release(build_time)

    logger.info("Retaining records for features dropped upstream")
    historical_path = None
    if build_retained(build_time) is not None:
        historical_path = export_historical(build_time)
    else:
        logger.info("There is no previous release in the archive")

    logger.info("Writing dataset metadata")
    write_dataset_metadata(
        build_time, archive_path=archive_path, historical_path=historical_path
    )

    if config.legacy_dump:
        logger.info("Legacy dump: not reloading GraphDB")
        logger.info("ETL complete")
        return

    logger.info("Configuring GraphDB")
    graphdb_adapter = GraphDBAdapter()
    steps = [
        ("Enabling GraphDB security", graphdb_adapter.enable_security),
        ("Setting GraphDB password", graphdb_adapter.set_password),
        ("Creating repository", graphdb_adapter.create_repository_from_config),
        ("Clearing the previous release", graphdb_adapter.clear_repository),
        ("Copying triples to import directory", graphdb_adapter.copy_triples),
        ("Loading data into GraphDB", graphdb_adapter.upload),
        ("Setting GraphDB permissions", graphdb_adapter.enable_guest_access),
    ]
    for description, step in steps:
        logger.info(description)
        try:
            step()
        except requests.exceptions.RequestException as error:
            logger.error(f"{description} failed: {error}")
            if getattr(error, "response", None) is not None:
                logger.error(f"Response status code: {error.response.status_code}")
                logger.error(f"Response body: {error.response.text}")
            sys.exit(1)

    logger.info("ETL complete")


if __name__ == "__main__":
    main()

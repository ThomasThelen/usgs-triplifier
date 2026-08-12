import logging
import sys
from datetime import datetime, timezone

import requests

from usgs_triplifier.lib.archive_exporter import export_historical, export_release
from usgs_triplifier.lib.dataset_downloader import DatasetDownloader
from usgs_triplifier.lib.dataset_metadata import write_dataset_metadata
from usgs_triplifier.lib.retention import build_retained
from usgs_triplifier.lib.gnis import (
    UnitsTriplifier,
    FeaturesTriplifier,
    NamesTriplifier,
    HistoryTriplifier,
)
from config import config
from graphdb_adapter import GraphDBAdapter

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("etl")


def main() -> None:
    if config.download_data:
        logger.info("Downloading...")
        DatasetDownloader.download()
    else:
        logger.info("DOWNLOAD_DATA is disabled, skipping download")

    logger.info("Transforming into RDF...")
    for triplifier in [
        FeaturesTriplifier,
        NamesTriplifier,
        HistoryTriplifier,
        UnitsTriplifier,
    ]:
        triplifier()

    build_time = (
        datetime.fromisoformat(config.release_date).replace(tzinfo=timezone.utc)
        if config.release_date
        else datetime.now(timezone.utc)
    )

    logger.info("Exporting release dump to the archive")
    archive_path = export_release(build_time)

    logger.info("Retaining records for features dropped upstream")
    historical_path = None
    if build_retained(build_time) is not None:
        historical_path = export_historical(build_time)
    else:
        logger.info("No previous release in the archive; nothing to retain")

    logger.info("Writing dataset metadata")
    write_dataset_metadata(
        build_time, archive_path=archive_path, historical_path=historical_path
    )

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

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import requests

from usgs_triplifier.lib.archive_exporter import ReleaseExporter
from usgs_triplifier.lib.census_crosswalk import CensusCrosswalk
from usgs_triplifier.lib.dataset_downloader import DatasetDownloader
from usgs_triplifier.lib.dataset_metadata import DatasetMetadataWriter
from usgs_triplifier.lib.dedup import Deduplicator
from usgs_triplifier.lib.geonames_crosswalk import GeoNamesCrosswalk
from usgs_triplifier.lib.gnis import (
    FeaturesTriplifier,
    GeometryTriplifier,
    HistoryTriplifier,
    NamesTriplifier,
    UnitsTriplifier,
)
from usgs_triplifier.lib.retention import RetentionBuilder
from usgs_triplifier.lib.validation import ReleaseValidator
from usgs_triplifier.lib.wikidata_crosswalk import WikidataCrosswalk

from config import EtlConfig
from graphdb_adapter import GraphDBAdapter, GraphDBImportError


class PipelineError(Exception):
    """
    Raised when a release can't be published.
    """


class Pipeline:
    """
    Builds a GNIS-LD release and publishes it.
    """

    TRIPLIFIERS: ClassVar[tuple[type, ...]] = (
        FeaturesTriplifier,
        NamesTriplifier,
        HistoryTriplifier,
        UnitsTriplifier,
    )

    CROSSWALKS: ClassVar[tuple[type, ...]] = (
        WikidataCrosswalk,
        GeoNamesCrosswalk,
        CensusCrosswalk,
    )

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, config: EtlConfig) -> None:
        """
        Creates the pipeline.

        :param config: Settings for every step.
        """
        self.config = config

    def run(self) -> None:
        """
        Builds and publishes a release.

        :raises PipelineError: If the release fails validation or GraphDB
            rejects a request.
        """
        self.download()
        self.triplify()
        self.add_crosswalks()
        Deduplicator(self.config).run()

        build_time = self.build_time()
        self._log.info("Validating a sample of the release against the SHACL shapes")
        if not ReleaseValidator(self.config).validate():
            raise PipelineError("SHACL validation failed; the release was not exported")

        release_path, historical_path = self.export(build_time)
        self._log.info("Writing the dataset metadata")
        DatasetMetadataWriter(self.config).write(
            build_time, release_path, historical_path
        )

        if self.config.legacy_dump:
            # A release from a legacy dump is only written to the archive
            # output directory; GraphDB keeps serving the current release
            self._log.info("Legacy dump: not reloading GraphDB")
        else:
            self.load_graphdb()
        self._log.info("ETL complete")

    def download(self) -> None:
        """
        Downloads the current USGS products into the input directory, unless
        the input is a legacy dump, which is copied there by hand, or
        DOWNLOAD_DATA is false.
        """
        if self.config.legacy_dump:
            self._log.info(
                f"Reading the {self.config.legacy_dump_date} legacy dump from the "
                "input directory; skipping the download"
            )
        elif self.config.download_data:
            DatasetDownloader(self.config.input_directory).download()
        else:
            self._log.info(
                "DOWNLOAD_DATA is false; using the files in the input directory"
            )

    def triplify(self) -> None:
        """
        Deletes the .nt.gz and .ttl files of a previous run from the output
        directory, then converts the USGS products to RDF there. A leftover
        file would otherwise be included in this release. The multipoint
        geometries are only written for the current products, because legacy
        dumps have no GeoPackage.
        """
        for pattern in ("*.ttl", "*.nt.gz"):
            for stale in self.config.output_directory.glob(pattern):
                stale.unlink()
        for triplifier in self.TRIPLIFIERS:
            triplifier(self.config).run()
        if not self.config.legacy_dump:
            GeometryTriplifier(self.config).run()

    def add_crosswalks(self) -> None:
        """
        Writes the links of every crosswalk.
        """
        for crosswalk in self.CROSSWALKS:
            crosswalk(self.config).build()

    def build_time(self) -> datetime:
        """
        Picks the time the release is dated with. This is LEGACY_DUMP_DATE
        when set, otherwise RELEASE_DATE, otherwise the current time.

        :return: The time, in UTC.
        """
        release_date = self.config.legacy_dump_date or self.config.release_date
        if release_date:
            return datetime.fromisoformat(release_date).replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    def export(self, build_time: datetime) -> tuple[Path, Path | None]:
        """
        Writes the release file, then the retained records and, when there
        are any, the historical release file.

        :param build_time: Time the release is dated with.
        :return: (release file, historical release file or None).
        """
        exporter = ReleaseExporter(self.config)
        release_path = exporter.export_release(build_time)
        if RetentionBuilder(self.config).build(build_time) is None:
            self._log.info(
                "No records to retain: there is no earlier release in the "
                "archive, or no feature was dropped since it"
            )
            return release_path, None
        return release_path, exporter.export_historical(build_time)

    def load_graphdb(self) -> None:
        """
        Replaces the GraphDB repository's contents with the output directory's
        RDF files, setting up security and the repository first if needed.

        The files are copied to the import directory before the repository is
        cleared, so a copy failure leaves the previous release in place.

        :raises PipelineError: If the output directory has no RDF files,
            GraphDB rejects a request, or the import fails; the response is logged.
        """
        graphdb = GraphDBAdapter(self.config)

        def copy_triples() -> None:
            if not graphdb.copy_triples():
                raise PipelineError(
                    f"No RDF files in {self.config.output_directory} to load"
                )

        steps = [
            ("Enabling GraphDB security", graphdb.enable_security),
            ("Setting the GraphDB password", graphdb.set_password),
            ("Creating the repository", graphdb.create_repository_from_config),
            ("Copying the RDF files to the import directory", copy_triples),
            ("Clearing the previous release", graphdb.clear_repository),
            ("Importing the RDF files", graphdb.import_files),
            ("Granting anonymous read access", graphdb.enable_guest_access),
        ]
        for description, step in steps:
            self._log.info(description)
            try:
                step()
            except (requests.RequestException, GraphDBImportError) as error:
                response = getattr(error, "response", None)
                if response is not None:
                    self._log.error(
                        f"GraphDB responded {response.status_code}: {response.text}"
                    )
                raise PipelineError(f"{description} failed: {error}") from error

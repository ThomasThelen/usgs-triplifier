import gzip
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from ..config import Config
from ..output_files import OutputFiles


class RetentionBuilder:
    """
    Keeps the records of features that are no longer in the USGS products,
    so their URIs keep resolving.

    The release just exported is compared with every earlier release in the
    archive output directory, so a release built out of order (a legacy dump
    added after later releases) is covered too. Every IRI subject that is
    in an earlier release but not in the new one has its lines copied, with
    the blank nodes they reference, to retained-features.nt.gz. The file the
    lines are copied from depends on the subject.

        - Subjects already in the newest earlier historical release file are
          copied from it as they are, with their existing
          usgs:HistoricalFeature and gnis:lastAppearedIn triples.
        - Every other subject is copied from the newest earlier release that
          has it. Each GNIS feature among them gets rdf:type
          usgs:HistoricalFeature and gnis:lastAppearedIn with that release's IRI.
    """

    # Maximum passes over a file to collect the blank nodes that retained
    # lines reference. Retained blank nodes are one level deep (feature to
    # elevation), so the loop normally stops after two passes.
    MAX_CLOSURE_PASSES: ClassVar[int] = 5

    RDF_TYPE: ClassVar[str] = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"

    # Paths under lod_base whose subjects are ontology terms, which are not
    # records and are never retained
    ONTOLOGY_PATHS: ClassVar[tuple[str, ...]] = ("/gnis/ontology/", "/usgs/ontology/")

    def __init__(self, config: Config) -> None:
        """
        Creates the builder.

        :param config: Settings holding the output and archive output
            directories and lod_base.
        """
        self.config = config
        self._ontology_prefixes = tuple(
            f"<{config.lod_base}{path}" for path in self.ONTOLOGY_PATHS
        )

    def build(self, build_time: datetime) -> Path | None:
        """
        Writes retained-features.nt.gz to the output directory.

        :param build_time: Time the release just exported is dated with.
        :return: Path of the file, or None when nothing is retained. When the
            archive has no earlier release, no file is written; otherwise the
            file is written even when it is empty.
        :raises FileNotFoundError: If the release for build_time has not been exported.
        """
        release_id = OutputFiles.release_id(build_time)
        archive_dir = self.config.archive_output_directory
        earlier = self._earlier(archive_dir, OutputFiles.RELEASE, release_id)
        if not earlier:
            return None
        earlier_historical = self._earlier(
            archive_dir, OutputFiles.HISTORICAL_RELEASE, release_id
        )

        # Subjects not to copy again: those in the new release, and those
        # already copied from a newer file
        covered = self._iri_subjects(archive_dir / OutputFiles.release(release_id))

        lines: list[str] = []
        if earlier_historical:
            retained = self._dropped_records(earlier_historical[0], covered)
            lines.extend(retained)
            covered |= self._iri_subjects_of(retained)

        for path in earlier:
            dropped = self._dropped_records(path, covered)
            if not dropped:
                continue
            lines.extend(dropped)
            covered |= self._iri_subjects_of(dropped)
            path_id = OutputFiles.RELEASE.match(path.name)[1]
            lines.extend(
                self._historical_triples(
                    dropped, f"{self.config.lod_base}/gnis/release/{path_id}"
                )
            )

        path = self.config.output_directory / OutputFiles.RETAINED
        with gzip.open(path, "wt", encoding="utf-8") as out:
            for line in lines:
                out.write(line + "\n")
        return path if lines else None

    @staticmethod
    def _earlier(archive_dir: Path, pattern: re.Pattern, release_id: str) -> list[Path]:
        """
        Lists the files in the archive whose name matches a release file
        pattern and whose release id is earlier than release_id.

        :param archive_dir: Archive output directory.
        :param pattern: OutputFiles.RELEASE or OutputFiles.HISTORICAL_RELEASE.
        :param release_id: Id of the release just exported.
        :return: The files, newest release first.
        """
        candidates = [
            (m[1], path)
            for path in archive_dir.glob("*.nt.gz")
            if (m := pattern.match(path.name)) and m[1] < release_id
        ]
        return [path for _, path in sorted(candidates, reverse=True)]

    @staticmethod
    def _lines(path: Path) -> Iterator[str]:
        """
        Yields the triple lines of a gzipped N-Triples file.

        :param path: The file.
        :return: Iterator of lines without surrounding whitespace, skipping
            blank lines and comments.
        """
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    yield line

    @staticmethod
    def _subject(line: str) -> str:
        """
        Extracts the subject term of an N-Triples line.

        :param line: N-Triples line without surrounding whitespace.
        :return: The text before the first space.
        """
        return line[: line.index(" ")]

    @staticmethod
    def _object(line: str) -> str:
        """
        Extracts the object term of an N-Triples line.

        :param line: N-Triples line without surrounding whitespace.
        :return: The text between the predicate and the closing " .".
        """
        after_subject = line[line.index(" ") + 1 :]
        return after_subject[after_subject.index(" ") + 1 : -2].strip()

    def _iri_subjects(self, path: Path) -> set[str]:
        """
        Collects the IRI subjects of a file.

        :param path: Gzipped N-Triples file.
        :return: The subject terms that are IRIs, in angle brackets.
        """
        return {
            s
            for line in self._lines(path)
            if (s := self._subject(line)).startswith("<")
        }

    def _iri_subjects_of(self, lines: list[str]) -> set[str]:
        """
        Collects the IRI subjects of N-Triples lines.

        :param lines: N-Triples lines without surrounding whitespace.
        :return: The subject terms that are IRIs, in angle brackets.
        """
        return {s for line in lines if (s := self._subject(line)).startswith("<")}

    def _dropped_records(self, source: Path, covered: set[str]) -> list[str]:
        """
        Collects the lines of a file whose IRI subject is not covered, and the
        lines of the blank nodes they reference.

        A dropped feature's geometry and alias are IRI subjects of their own,
        so they are collected by the same comparison as the feature. Ontology
        terms are left out.

        :param source: Earlier release or historical release file.
        :param covered: IRI subjects to leave out, which are those in the new
            release and those already collected from newer files.
        :return: The collected lines, in file order.
        """
        keep = {
            s
            for line in self._lines(source)
            if (s := self._subject(line)).startswith("<")
            and s not in covered
            and not s.startswith(self._ontology_prefixes)
        }
        if not keep:
            return []
        kept: list[str] = []
        seen: set[str] = set()
        for _ in range(self.MAX_CLOSURE_PASSES):
            added_blank_node = False
            for line in self._lines(source):
                if self._subject(line) not in keep or line in seen:
                    continue
                seen.add(line)
                kept.append(line)
                obj = self._object(line)
                if obj.startswith("_:") and obj not in keep:
                    keep.add(obj)
                    added_blank_node = True
            if not added_blank_node:
                break
        return kept

    def _historical_triples(
        self, dropped_lines: list[str], release_iri: str
    ) -> list[str]:
        """
        Builds the rdf:type usgs:HistoricalFeature and gnis:lastAppearedIn
        triples of each GNIS feature among the dropped lines' subjects.

        :param dropped_lines: Lines collected from one earlier release.
        :param release_iri: IRI of that release, the last that had the features.
        :return: N-Triples lines, two per feature.
        """
        lod = self.config.lod_base
        feature_prefix = f"<{lod}/gnis/feature/"
        features = {
            s
            for line in dropped_lines
            if (s := self._subject(line)).startswith(feature_prefix)
        }
        historical_class = f"<{lod}/usgs/ontology/HistoricalFeature>"
        last_appeared = f"<{lod}/gnis/ontology/lastAppearedIn>"
        lines = []
        for feature in sorted(features):
            lines.append(f"{feature} {self.RDF_TYPE} {historical_class} .")
            lines.append(f"{feature} {last_appeared} <{release_iri}> .")
        return lines

import gzip
import logging
from pathlib import Path
from typing import ClassVar

import pyshacl
from rdflib import Graph

from ..config import Config


class ReleaseValidator:
    """
    Checks the generated N-Triples files against the SHACL shapes in
    shapes/release-shapes.ttl before a release is exported.

    A release has tens of millions of triples, too many for pyshacl, which
    holds the data in an rdflib Graph. So only the first
    shacl_sample_subjects IRI subjects of each file are validated. A mapping
    error in a triplifier or crosswalk affects every record of its file,
    including the validated ones. Violations fail the check. Warnings, used
    for known problems in the USGS data such as unparseable dates, are only
    logged.
    """

    SHAPES_PATH: ClassVar[Path] = (
        Path(__file__).parent.parent / "shapes" / "release-shapes.ttl"
    )

    # Base IRI written in the shapes file; replaced with lod_base when loaded
    SHAPES_LOD_BASE: ClassVar[str] = "http://gnis-ld.org/lod"

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, config: Config) -> None:
        """
        Creates the validator.

        :param config: Settings holding the output directory, lod_base and
            shacl_sample_subjects.
        """
        self.config = config

    def validate(self) -> bool:
        """
        Validates a sample of every .nt.gz in the output directory.

        :return: False when any violation is found; True otherwise, including
            when there are no files to validate.
        """
        sample = Graph()
        paths = sorted(self.config.output_directory.glob("*.nt.gz"))
        for path in paths:
            lines = self._sample_lines(path, self.config.shacl_sample_subjects)
            sample.parse(data="".join(lines), format="nt")
        if not paths:
            self._log.warning("No generated files to validate")
            return True

        shapes = Graph()
        shapes_text = self.SHAPES_PATH.read_text().replace(
            self.SHAPES_LOD_BASE, self.config.lod_base
        )
        shapes.parse(data=shapes_text, format="turtle")
        _, report, _ = pyshacl.validate(
            sample, shacl_graph=shapes, inference="none", advanced=False
        )

        violations, warnings = self._partition_results(report)
        self._log.info(
            f"SHACL: validated {len(sample)} sampled triples from {len(paths)} files: "
            f"{len(violations)} violations, {len(warnings)} warnings"
        )
        for message in warnings[:10]:
            self._log.warning(f"SHACL warning: {message}")
        for message in violations[:20]:
            self._log.error(f"SHACL violation: {message}")
        return not violations

    @staticmethod
    def _sample_lines(path: Path, max_subjects: int) -> list[str]:
        """
        Collects the lines of a file's first IRI subjects.

        Reads from the start of the file and keeps every line until a line
        introduces subject number max_subjects + 1. A line whose subject is a
        blank node is kept when an earlier kept line has that blank node as
        its object, which covers blank nodes one level deep, such as elevations.

        :param path: Gzipped N-Triples file.
        :param max_subjects: Number of distinct IRI subjects to collect.
        :return: The collected lines.
        """
        lines: list[str] = []
        subjects: set[str] = set()
        blank_nodes: set[str] = set()
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                subject = line[: line.index(" ")]
                if subject.startswith("_:"):
                    if subject in blank_nodes:
                        lines.append(line)
                    continue
                if subject not in subjects:
                    if len(subjects) >= max_subjects:
                        break
                    subjects.add(subject)
                lines.append(line)
                obj = line[:-2].strip()
                obj = obj[obj.rindex(" ") + 1 :] if " " in obj else obj
                if obj.startswith("_:"):
                    blank_nodes.add(obj)
        return lines

    @staticmethod
    def _partition_results(report: Graph) -> tuple[list[str], list[str]]:
        """
        Splits a SHACL validation report by severity.

        :param report: Report graph returned by pyshacl.validate.
        :return: (violations, results of any other severity), each a list of
            "focus node: message" strings.
        """
        query = """
            PREFIX sh: <http://www.w3.org/ns/shacl#>
            SELECT ?severity ?focus ?message WHERE {
                ?r a sh:ValidationResult ;
                   sh:resultSeverity ?severity ;
                   sh:focusNode ?focus ;
                   sh:resultMessage ?message .
            }
        """
        violations, others = [], []
        for severity, focus, message in report.query(query):
            text = f"{focus}: {message}"
            if str(severity).endswith("Violation"):
                violations.append(text)
            else:
                others.append(text)
        return violations, others

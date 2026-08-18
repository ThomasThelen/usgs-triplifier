"""
SHACL validation of the generated release data.

Full-graph validation is off the table — pySHACL holds the data as an
rdflib Graph, and a release is tens of millions of triples — so the gate
validates a deterministic sample instead: the leading records of every
generated dump, with their blank-node closure. A systematic pipeline bug
(wrong datatype, missing label, malformed URI, broken tombstone) corrupts
every record it touches, so a bounded sample catches the class of
regression a build gate exists to catch, in seconds.

The shapes (shapes/release-shapes.ttl) are derived from the gnis and usgs
ontologies. Violations fail the build; warnings (known upstream quirks,
like unparsable source dates passing through as plain literals) are
logged and tolerated.
"""

import gzip
import logging
from pathlib import Path

import pyshacl
from rdflib import Graph

from ..config import config

SHAPES_PATH = Path(__file__).parent.parent / "shapes" / "release-shapes.ttl"

logger = logging.getLogger(__name__)


def validate_release() -> bool:
    """
    Validate a sample of every generated dump against the release shapes.

    :return: True when the sample conforms (warnings allowed), False when
        any violation was found.
    """
    sample = Graph()
    n_files = 0
    for nt_path in sorted(config.output_directory.glob("*.nt.gz")):
        sample.parse(
            data="".join(_sample_lines(nt_path, config.shacl_sample_subjects)),
            format="nt",
        )
        n_files += 1
    if not n_files:
        logger.warning("No generated dumps to validate")
        return True

    shapes = Graph()
    # the shapes are written against the production base; rebase them to
    # whatever base this deployment mints
    shapes_text = SHAPES_PATH.read_text().replace(
        "http://gnis-ld.org/lod", config.lod_base
    )
    shapes.parse(data=shapes_text, format="turtle")

    conforms, report_graph, _ = pyshacl.validate(
        sample, shacl_graph=shapes, inference="none", advanced=False
    )

    violations, warnings = _partition_results(report_graph)
    logger.info(
        f"SHACL: validated {len(sample)} sampled triples from {n_files} files: "
        f"{len(violations)} violations, {len(warnings)} warnings"
    )
    for message in warnings[:10]:
        logger.warning(f"SHACL warning: {message}")
    for message in violations[:20]:
        logger.error(f"SHACL violation: {message}")
    return not violations


def _sample_lines(nt_path: Path, max_subjects: int) -> list[str]:
    """
    Sample a dump's leading records.

    The writers emit a record's blank-node lines immediately after the
    line that introduces the blank node, so a single pass that stops at
    the first subject past the sample sees every dependent line.

    :param nt_path: Gzipped N-Triples dump to sample.
    :param max_subjects: Number of distinct URI subjects to collect.
    :return: The lines of the first ``max_subjects`` subjects, plus their
        blank-node closure.
    """
    lines: list[str] = []
    subjects: set[str] = set()
    bnodes: set[str] = set()
    with gzip.open(nt_path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            subject = line[: line.index(" ")]
            if subject.startswith("_:"):
                if subject in bnodes:
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
                bnodes.add(obj)
    return lines


def _partition_results(report_graph: Graph) -> tuple[list[str], list[str]]:
    """
    Split a validation report into violations and everything milder.

    :param report_graph: The report graph returned by pyshacl.validate.
    :return: Two lists of "focus node: message" strings — violations
        first, then warnings and infos.
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
    violations, warnings = [], []
    for severity, focus, message in report_graph.query(query):
        text = f"{focus}: {message}"
        if str(severity).endswith("Violation"):
            violations.append(text)
        else:
            warnings.append(text)
    return violations, warnings

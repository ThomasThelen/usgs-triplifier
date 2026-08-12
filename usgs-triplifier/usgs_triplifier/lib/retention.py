"""
Carry forward records for features dropped from the upstream sources.

Feature URIs are permanent: when USGS stops shipping a record, its last-known
triples are retained — tombstoned as historical — so the URI keeps resolving.
Retained records are diffed from the release dumps in the archive, written to
the output directory for the GraphDB load, and published per release as the
gnis-ld-historical-<yymmdd>.nt.gz companion dump. Only vanished subjects are
carried: still-current features never receive stale property values.
"""

import gzip
import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import config
from .dataset_metadata import (
    R_HISTORICAL_DUMP,
    R_MAIN_DUMP,
    RETAINED_BASENAME,
    build_id_for,
)

# Blank-node closure is shallow (feature -> elevation node); passes are a
# safety bound, not an expected depth.
MAX_CLOSURE_PASSES = 5


def build_retained(build_time: datetime | None = None) -> Path | None:
    """
    Write retained-features.ttl for every record dropped from this release.

    Diffs the just-exported release dump against the newest previous release
    dump and the newest previous historical dump in the archive: any subject
    present before but absent now is carried forward verbatim (with its
    blank-node closure), and newly dropped GNIS features are tombstoned with
    rdf:type usgs:HistoricalFeature and gnis:lastAppearedIn pointing at the
    release they last appeared in. Records already retained stay retained
    until their subject reappears upstream.

    :param build_time: Timestamp identifying the build; defaults to now (UTC).
    :return: Path of the written file, or None when nothing was retained
        (first release, or no records dropped).
    """
    build_time = build_time or datetime.now(timezone.utc)
    build_id = build_id_for(build_time)

    archive_dir = config.archive_output_directory
    current_dump = archive_dir / f"gnis-ld-{build_id}.nt.gz"
    previous_main = _previous_dump(archive_dir, R_MAIN_DUMP, build_id)
    previous_historical = _previous_dump(archive_dir, R_HISTORICAL_DUMP, build_id)
    if previous_main is None:
        return None

    current_subjects = _uri_subjects(current_dump)

    lines: list[str] = []
    # Records already retained: kept until their subject reappears upstream.
    # These carry their original tombstones, so no new ones are added.
    if previous_historical is not None:
        lines.extend(_dropped_records(previous_historical, current_subjects))

    # Records newly dropped from the previous release, plus tombstones
    newly_dropped = _dropped_records(previous_main, current_subjects)
    lines.extend(newly_dropped)
    previous_release_uri = (
        f"{config.lod_base}/gnis/release/{R_MAIN_DUMP.match(previous_main.name)[1]}"
    )
    lines.extend(_tombstones(newly_dropped, previous_release_uri))

    # Always (re)write the file so a stale one from a previous run is never
    # loaded, but only report a path when there is something to publish.
    output_path = config.output_directory / RETAINED_BASENAME
    with open(output_path, "w", encoding="utf-8") as out:
        for line in lines:
            out.write(line + "\n")
    return output_path if lines else None


def _previous_dump(
    archive_dir: Path, pattern: re.Pattern, build_id: str
) -> Path | None:
    """Newest archived dump matching ``pattern`` from before this build."""
    candidates = [
        (m[1], path)
        for path in archive_dir.glob("*.nt.gz")
        if (m := pattern.match(path.name)) and m[1] < build_id
    ]
    return max(candidates)[1] if candidates else None


def _lines(dump_path: Path):
    """Yield each triple line of a gzipped N-Triples dump."""
    with gzip.open(dump_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line


def _subject(line: str) -> str:
    return line[: line.index(" ")]


def _object(line: str) -> str:
    """The object term: between the predicate and the closing ' .'."""
    after_subject = line[line.index(" ") + 1 :]
    return after_subject[after_subject.index(" ") + 1 : -2].strip()


def _uri_subjects(dump_path: Path) -> set[str]:
    """Every URI appearing in subject position in a dump."""
    return {s for line in _lines(dump_path) if (s := _subject(line)).startswith("<")}


def _dropped_records(source: Path, current_subjects: set[str]) -> list[str]:
    """
    Lines of ``source`` whose subject no longer appears in the current
    release, plus the blank-node closure of those records.

    A dropped feature's dependent records (geometry, aliases) are dropped
    subjects themselves, so the URI diff catches them directly; only blank
    nodes need chasing.
    """
    keep = {
        s
        for line in _lines(source)
        if (s := _subject(line)).startswith("<") and s not in current_subjects
    }

    kept_lines: list[str] = []
    seen: set[str] = set()
    for _ in range(MAX_CLOSURE_PASSES):
        grew = False
        for line in _lines(source):
            if _subject(line) not in keep or line in seen:
                continue
            seen.add(line)
            kept_lines.append(line)
            obj = _object(line)
            if obj.startswith("_:") and obj not in keep:
                keep.add(obj)
                grew = True
        if not grew:
            break
    return kept_lines


def _tombstones(dropped_lines: list[str], release_uri: str) -> list[str]:
    """Historical typing + provenance for each newly dropped GNIS feature."""
    feature_prefix = f"<{config.lod_base}/gnis/feature/"
    features = {
        s for line in dropped_lines if (s := _subject(line)).startswith(feature_prefix)
    }
    historical_class = f"<{config.lod_base}/usgs/ontology/HistoricalFeature>"
    last_appeared = f"<{config.lod_base}/gnis/ontology/lastAppearedIn>"
    rdf_type = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
    lines = []
    for feature in sorted(features):
        lines.append(f"{feature} {rdf_type} {historical_class} .")
        lines.append(f"{feature} {last_appeared} <{release_uri}> .")
    return lines

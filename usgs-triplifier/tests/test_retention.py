import gzip
from datetime import datetime, timezone

import pytest

from usgs_triplifier.config import config
from usgs_triplifier.lib.archive_exporter import export_historical
from usgs_triplifier.lib.dataset_metadata import RETAINED_BASENAME
from usgs_triplifier.lib.retention import build_retained

BUILD_TIME = datetime(2026, 7, 1, tzinfo=timezone.utc)

LOD = "http://gnis-ld.org/lod"
GEO = "http://gnis-ld.org/geometry"
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
HISTORICAL = f"<{LOD}/usgs/ontology/HistoricalFeature>"
LAST_APPEARED = f"<{LOD}/gnis/ontology/lastAppearedIn>"

# Feature 1 is dropped upstream: a full record with a geometry (a dependent
# URI subject) and an elevation blank node (needs closure chasing).
DROPPED_RECORD = [
    f'<{LOD}/gnis/feature/1> {LABEL} "Blue Lake" .',
    f"<{LOD}/gnis/feature/1> <http://www.opengis.net/ont/geosparql#hasGeometry> <{GEO}/point/gnisf.1> .",
    f"<{LOD}/gnis/feature/1> <{LOD}/gnis/ontology/elevation> _:b1 .",
    '_:b1 <http://qudt.org/schema/qudt/numericValue> "5280.0"^^<http://www.w3.org/2001/XMLSchema#double> .',
    f'<{GEO}/point/gnisf.1> <http://www.opengis.net/ont/geosparql#asWKT> "POINT(1 2)" .',
]

KEPT_LINE = f'<{LOD}/gnis/feature/2> {LABEL} "Kept Creek" .'

# Feature 3 was already retained in an earlier release, with its tombstone
PRIOR_HISTORICAL = [
    f'<{LOD}/gnis/feature/3> {LABEL} "Ghost Town" .',
    f"<{LOD}/gnis/feature/3> {RDF_TYPE} {HISTORICAL} .",
    f"<{LOD}/gnis/feature/3> {LAST_APPEARED} <{LOD}/gnis/release/260101> .",
]


@pytest.fixture()
def archive_dir(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.mkdir()
    monkeypatch.setattr(config, "archive_output_directory", archive)
    return archive


def _write_dump(archive_dir, name, lines):
    with gzip.open(archive_dir / name, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _retained_lines():
    text = (config.output_directory / RETAINED_BASENAME).read_text()
    return [line for line in text.splitlines() if line.strip()]


def test_dropped_record_is_carried_with_closure_and_tombstone(data_dirs, archive_dir):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", DROPPED_RECORD + [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])

    assert build_retained(BUILD_TIME) is not None
    lines = _retained_lines()

    # The whole record survives: feature, geometry subject, blank node
    for line in DROPPED_RECORD:
        assert line in lines
    # Still-current features are not carried
    assert KEPT_LINE not in lines
    # Tombstoned against the release it last appeared in
    assert f"<{LOD}/gnis/feature/1> {RDF_TYPE} {HISTORICAL} ." in lines
    assert (
        f"<{LOD}/gnis/feature/1> {LAST_APPEARED} <{LOD}/gnis/release/260401> ." in lines
    )


def test_previously_retained_records_stay_without_new_tombstones(
    data_dirs, archive_dir
):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-historical-260401.nt.gz", PRIOR_HISTORICAL)
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])

    build_retained(BUILD_TIME)
    lines = _retained_lines()

    for line in PRIOR_HISTORICAL:
        assert line in lines
    # The original lastAppearedIn is preserved, not re-stamped
    stamps = [line for line in lines if LAST_APPEARED in line]
    assert stamps == [
        f"<{LOD}/gnis/feature/3> {LAST_APPEARED} <{LOD}/gnis/release/260101> ."
    ]


def test_reappearing_feature_leaves_the_historical_set(data_dirs, archive_dir):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-historical-260401.nt.gz", PRIOR_HISTORICAL)
    # Feature 3 is shipped by USGS again
    _write_dump(
        archive_dir,
        "gnis-ld-260701.nt.gz",
        [KEPT_LINE, f'<{LOD}/gnis/feature/3> {LABEL} "Ghost Town" .'],
    )

    assert build_retained(BUILD_TIME) is None
    assert _retained_lines() == []


def test_first_release_has_nothing_to_retain(data_dirs, archive_dir):
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])
    assert build_retained(BUILD_TIME) is None


def test_export_historical_publishes_companion_dump(data_dirs, archive_dir):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", DROPPED_RECORD + [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])
    build_retained(BUILD_TIME)

    dump = export_historical(BUILD_TIME)

    assert dump == archive_dir / "gnis-ld-historical-260701.nt.gz"
    with gzip.open(dump, "rt", encoding="utf-8") as f:
        published = [line for line in f.read().splitlines() if line.strip()]
    assert published == _retained_lines()
    sidecar = (archive_dir / "gnis-ld-historical-260701.meta.json").read_text()
    assert '"id": "260701"' in sidecar
    assert f'"triples": "{len(published):,}"' in sidecar

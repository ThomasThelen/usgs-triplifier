import gzip
from datetime import datetime, timezone

import pytest

from usgs_triplifier.lib.archive_exporter import ReleaseExporter
from usgs_triplifier.output_files import OutputFiles
from usgs_triplifier.lib.retention import RetentionBuilder

BUILD_TIME = datetime(2026, 7, 1, tzinfo=timezone.utc)

LOD = "http://gnis-ld.org/lod"
GEO = "http://gnis-ld.org/geometry"
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
HISTORICAL = f"<{LOD}/usgs/ontology/HistoricalFeature>"
LAST_APPEARED = f"<{LOD}/gnis/ontology/lastAppearedIn>"

# Feature 1 is dropped upstream. Its record has a geometry, which is an IRI
# subject of its own, and an elevation blank node.
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
def archive_dir(tmp_path, monkeypatch, config):
    archive = tmp_path / "archive"
    archive.mkdir()
    config.archive_output_directory = archive
    return archive


def _write_dump(archive_dir, name, lines):
    with gzip.open(archive_dir / name, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _retained_lines(config):
    with gzip.open(config.output_directory / OutputFiles.RETAINED, "rt") as f:
        return [line for line in f.read().splitlines() if line.strip()]


def test_dropped_record_is_carried_with_closure_and_tombstone(
    data_dirs, archive_dir, config
):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", DROPPED_RECORD + [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])

    assert RetentionBuilder(config).build(BUILD_TIME) is not None
    lines = _retained_lines(config)

    # The feature, geometry and blank node lines are all retained
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
    data_dirs, archive_dir, config
):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-historical-260401.nt.gz", PRIOR_HISTORICAL)
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])

    RetentionBuilder(config).build(BUILD_TIME)
    lines = _retained_lines(config)

    for line in PRIOR_HISTORICAL:
        assert line in lines
    # The original lastAppearedIn is preserved, not re-stamped
    stamps = [line for line in lines if LAST_APPEARED in line]
    assert stamps == [
        f"<{LOD}/gnis/feature/3> {LAST_APPEARED} <{LOD}/gnis/release/260101> ."
    ]


def test_reappearing_feature_leaves_the_historical_set(data_dirs, archive_dir, config):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-historical-260401.nt.gz", PRIOR_HISTORICAL)
    _write_dump(
        archive_dir,
        "gnis-ld-260701.nt.gz",
        [KEPT_LINE, f'<{LOD}/gnis/feature/3> {LABEL} "Ghost Town" .'],
    )

    assert RetentionBuilder(config).build(BUILD_TIME) is None
    assert _retained_lines(config) == []


def test_first_release_has_nothing_to_retain(data_dirs, archive_dir, config):
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])
    assert RetentionBuilder(config).build(BUILD_TIME) is None


def test_feature_only_in_a_backfilled_legacy_dump_is_retained(
    data_dirs, archive_dir, config
):
    # The 2021 legacy dump is added to the archive after the 2026 releases
    # exist; feature 1 is only in it, feature 4 was dropped after 2026-04
    feature_4 = f'<{LOD}/gnis/feature/4> {LABEL} "Old Mill" .'
    _write_dump(archive_dir, "gnis-ld-210825.nt.gz", DROPPED_RECORD + [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", [KEPT_LINE, feature_4])
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])

    RetentionBuilder(config).build(BUILD_TIME)
    lines = _retained_lines(config)

    for line in DROPPED_RECORD + [feature_4]:
        assert line in lines
    assert (
        f"<{LOD}/gnis/feature/1> {LAST_APPEARED} <{LOD}/gnis/release/210825> ." in lines
    )
    assert (
        f"<{LOD}/gnis/feature/4> {LAST_APPEARED} <{LOD}/gnis/release/260401> ." in lines
    )
    assert KEPT_LINE not in lines


def test_feature_in_several_earlier_releases_is_taken_from_the_newest(
    data_dirs, archive_dir, config
):
    old_label = f'<{LOD}/gnis/feature/1> {LABEL} "Blue Pond" .'
    new_label = f'<{LOD}/gnis/feature/1> {LABEL} "Blue Lake" .'
    _write_dump(archive_dir, "gnis-ld-210825.nt.gz", [old_label, KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", [new_label, KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])

    RetentionBuilder(config).build(BUILD_TIME)
    lines = _retained_lines(config)

    assert new_label in lines
    assert old_label not in lines
    stamps = [line for line in lines if LAST_APPEARED in line]
    assert stamps == [
        f"<{LOD}/gnis/feature/1> {LAST_APPEARED} <{LOD}/gnis/release/260401> ."
    ]


def test_export_historical_publishes_companion_dump(data_dirs, archive_dir, config):
    _write_dump(archive_dir, "gnis-ld-260401.nt.gz", DROPPED_RECORD + [KEPT_LINE])
    _write_dump(archive_dir, "gnis-ld-260701.nt.gz", [KEPT_LINE])
    RetentionBuilder(config).build(BUILD_TIME)

    dump = ReleaseExporter(config).export_historical(BUILD_TIME)

    assert dump == archive_dir / "gnis-ld-historical-260701.nt.gz"
    with gzip.open(dump, "rt", encoding="utf-8") as f:
        published = [line for line in f.read().splitlines() if line.strip()]
    assert published == _retained_lines(config)
    sidecar = (archive_dir / "gnis-ld-historical-260701.meta.json").read_text()
    assert '"id": "260701"' in sidecar
    assert f'"triples": "{len(published):,}"' in sidecar

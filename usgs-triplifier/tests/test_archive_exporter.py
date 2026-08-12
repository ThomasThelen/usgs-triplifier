import gzip
import json
from datetime import datetime, timezone

import pytest
from rdflib import Graph

from usgs_triplifier.config import config
from usgs_triplifier.lib.archive_exporter import _format_size, export_release
from usgs_triplifier.lib.dataset_metadata import METADATA_BASENAME

BUILD_TIME = datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc)

FEATURES_TTL = """
@prefix gnis: <http://gnis-ld.org/lod/gnis/ontology/> .
<http://gnis-ld.org/lod/gnis/feature/1> gnis:featureId "1" ;
    gnis:county "Example" .
"""

NAMES_TTL = """
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://gnis-ld.org/lod/gnis/feature/1> rdfs:label "Example" .
"""


@pytest.fixture()
def archive_dir(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    monkeypatch.setattr(config, "archive_output_directory", archive)
    return archive


def test_export_concatenates_outputs_as_ntriples(data_dirs, archive_dir):
    _, output_dir = data_dirs
    (output_dir / "features.ttl").write_text(FEATURES_TTL)
    (output_dir / "names.ttl").write_text(NAMES_TTL)
    # The metadata description is not part of the data dump
    (output_dir / METADATA_BASENAME).write_text(NAMES_TTL)

    dump = export_release(BUILD_TIME)

    assert dump == archive_dir / "gnis-ld-260810.nt.gz"
    with gzip.open(dump, "rt", encoding="utf-8") as f:
        dumped = Graph()
        dumped.parse(f, format="nt")
    assert len(dumped) == 3


def test_export_writes_sidecar_for_website_scanner(data_dirs, archive_dir):
    _, output_dir = data_dirs
    (output_dir / "features.ttl").write_text(FEATURES_TTL)

    dump = export_release(BUILD_TIME)

    sidecar = json.loads((archive_dir / "gnis-ld-260810.meta.json").read_text())
    assert sidecar["id"] == "260810"
    assert sidecar["published"] == "2026-08-10"
    assert sidecar["triples"] == "2"
    assert sidecar["size"] == _format_size(dump.stat().st_size)


def test_format_size_matches_website_units():
    assert _format_size(500) == "1 KB"
    assert _format_size(2_048) == "2 KB"
    assert _format_size(3_500_000) == "3.5 MB"
    assert _format_size(1_200_000_000) == "1.2 GB"

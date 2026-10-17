import gzip
import json
from datetime import datetime, timezone

import pytest
from rdflib import Graph

from usgs_triplifier.lib.archive_exporter import ReleaseExporter
from usgs_triplifier.output_files import OutputFiles

BUILD_TIME = datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc)

FEATURES_NT = [
    '<http://gnis-ld.org/lod/gnis/feature/1> <http://gnis-ld.org/lod/gnis/ontology/featureId> "1" .',
    '<http://gnis-ld.org/lod/gnis/feature/1> <http://gnis-ld.org/lod/gnis/ontology/county> "Example" .',
]

NAMES_NT = [
    '<http://gnis-ld.org/lod/gnis/feature/1> <http://www.w3.org/2000/01/rdf-schema#label> "Example" .',
]


def _write_nt_gz(path, lines):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


@pytest.fixture()
def archive_dir(tmp_path, monkeypatch, config):
    archive = tmp_path / "archive"
    config.archive_output_directory = archive
    return archive


def test_export_concatenates_outputs_as_ntriples(data_dirs, archive_dir, config):
    _, output_dir = data_dirs
    _write_nt_gz(output_dir / "features.nt.gz", FEATURES_NT)
    _write_nt_gz(output_dir / "names.nt.gz", NAMES_NT)
    # Retained records are published separately, never in the main dump
    _write_nt_gz(output_dir / OutputFiles.RETAINED, NAMES_NT)

    dump = ReleaseExporter(config).export_release(BUILD_TIME)

    assert dump == archive_dir / "gnis-ld-260810.nt.gz"
    with gzip.open(dump, "rt", encoding="utf-8") as f:
        dumped = Graph()
        dumped.parse(f, format="nt")
    assert len(dumped) == 3


def test_export_writes_sidecar_for_website_scanner(data_dirs, archive_dir, config):
    _, output_dir = data_dirs
    _write_nt_gz(output_dir / "features.nt.gz", FEATURES_NT)

    dump = ReleaseExporter(config).export_release(BUILD_TIME)

    sidecar = json.loads((archive_dir / "gnis-ld-260810.meta.json").read_text())
    assert sidecar["id"] == "260810"
    assert sidecar["published"] == "2026-08-10"
    assert sidecar["triples"] == "2"
    assert sidecar["size"] == ReleaseExporter.format_size(dump.stat().st_size)


def test_format_size_matches_website_units():
    assert ReleaseExporter.format_size(500) == "1 KB"
    assert ReleaseExporter.format_size(2_048) == "2 KB"
    assert ReleaseExporter.format_size(3_500_000) == "3.5 MB"
    assert ReleaseExporter.format_size(1_200_000_000) == "1.2 GB"

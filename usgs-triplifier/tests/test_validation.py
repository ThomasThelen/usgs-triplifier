import gzip
import logging

from usgs_triplifier.lib.validation import ReleaseValidator

LOD = "http://gnis-ld.org/lod"
RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>"
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
LANG = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"

GOOD_FEATURE = [
    f'<{LOD}/gnis/feature/1> <{LOD}/gnis/ontology/featureId> "1" .',
    f"<{LOD}/gnis/feature/1> {RDF_TYPE} <{LOD}/usgs/ontology/Summit> .",
    f'<{LOD}/gnis/feature/1> <{LOD}/gnis/ontology/officialName> "Blue Peak"@en .',
    f"<{LOD}/gnis/feature/1> <{LOD}/gnis/ontology/elevation> _:e1 .",
    '_:e1 <http://qudt.org/schema/qudt/numericValue> "5280"^^<http://www.w3.org/2001/XMLSchema#double> .',
    "_:e1 <http://qudt.org/schema/qudt/unit> <http://qudt.org/vocab/unit/FT> .",
]


def _write(output_dir, name, lines):
    with gzip.open(output_dir / name, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def test_conforming_sample_passes(data_dirs, config):
    _, output_dir = data_dirs
    _write(output_dir, "features.nt.gz", GOOD_FEATURE)
    assert ReleaseValidator(config).validate() is True


def test_violation_fails_and_is_logged(data_dirs, caplog, config):
    _, output_dir = data_dirs
    # officialName without a language tag violates the rdf:langString shape
    _write(
        output_dir,
        "features.nt.gz",
        GOOD_FEATURE
        + [
            f'<{LOD}/gnis/feature/2> <{LOD}/gnis/ontology/featureId> "2" .',
            f'<{LOD}/gnis/feature/2> <{LOD}/gnis/ontology/officialName> "Bare Literal" .',
        ],
    )
    with caplog.at_level(logging.ERROR):
        assert ReleaseValidator(config).validate() is False
    assert "SHACL violation" in caplog.text
    assert "feature/2" in caplog.text


def test_incomplete_elevation_bnode_is_caught(data_dirs, config):
    _, output_dir = data_dirs
    lines = [
        f'<{LOD}/gnis/feature/3> <{LOD}/gnis/ontology/featureId> "3" .',
        f"<{LOD}/gnis/feature/3> <{LOD}/gnis/ontology/elevation> _:e3 .",
        '_:e3 <http://qudt.org/schema/qudt/numericValue> "12"^^<http://www.w3.org/2001/XMLSchema#double> .',
    ]
    _write(output_dir, "features.nt.gz", lines)
    assert ReleaseValidator(config).validate() is False


def test_upstream_date_quirk_is_only_a_warning(data_dirs, caplog, config):
    _, output_dir = data_dirs
    _write(
        output_dir,
        "features.nt.gz",
        GOOD_FEATURE
        + [
            f'<{LOD}/gnis/feature/1> <{LOD}/gnis/ontology/dateFeatureCreated> "bogus" .'
        ],
    )
    with caplog.at_level(logging.WARNING):
        assert ReleaseValidator(config).validate() is True
    assert "SHACL warning" in caplog.text


GEO = "http://gnis-ld.org/geometry"
GEOSPARQL = "http://www.opengis.net/ont/geosparql#"
CRS84 = "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"


def _wkt(node: str, wkt: str) -> str:
    """
    Builds the N-Triples line attaching a CRS84 WKT literal to a geometry node.

    :param node: IRI of the geometry node.
    :param wkt: WKT text, without the CRS prefix.
    :return: The N-Triples line.
    """
    return f'<{node}> <{GEOSPARQL}asWKT> "{CRS84}{wkt}"^^<{GEOSPARQL}wktLiteral> .'


def test_point_and_multipoint_geometries_conform(data_dirs, config):
    _, output_dir = data_dirs
    point = f"{GEO}/point/gnisf.1"
    multipoint = f"{GEO}/multipoint/gnisf.1"
    _write(
        output_dir,
        "features.nt.gz",
        GOOD_FEATURE
        + [
            f"<{LOD}/gnis/feature/1> <{GEOSPARQL}hasGeometry> <{point}> .",
            _wkt(point, "POINT(-117.2 34.5)"),
        ],
    )
    _write(
        output_dir,
        "geometries.nt.gz",
        [
            f"<{LOD}/gnis/feature/1> <{GEOSPARQL}hasGeometry> <{multipoint}> .",
            _wkt(multipoint, "MULTIPOINT ((-117.2 34.5), (-117.1 34.6))"),
        ],
    )
    assert ReleaseValidator(config).validate() is True


def test_three_dimensional_wkt_is_a_violation(data_dirs, config):
    _, output_dir = data_dirs
    multipoint = f"{GEO}/multipoint/gnisf.1"
    _write(
        output_dir,
        "geometries.nt.gz",
        [
            f"<{LOD}/gnis/feature/1> <{GEOSPARQL}hasGeometry> <{multipoint}> .",
            _wkt(multipoint, "MULTIPOINT Z ((-117.2 34.5 0))"),
        ],
    )
    assert ReleaseValidator(config).validate() is False


def test_sampling_respects_subject_budget(data_dirs, monkeypatch, config):
    _, output_dir = data_dirs
    config.shacl_sample_subjects = 1
    # the second subject is malformed but sits past the sample budget
    _write(
        output_dir,
        "features.nt.gz",
        GOOD_FEATURE
        + [f'<{LOD}/gnis/feature/9> <{LOD}/gnis/ontology/officialName> "Bad" .'],
    )
    assert ReleaseValidator(config).validate() is True

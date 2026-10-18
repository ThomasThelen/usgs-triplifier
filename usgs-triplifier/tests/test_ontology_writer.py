from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from conftest import parse_nt_gz
from usgs_triplifier.lib.ontology_writer import OntologyWriter
from usgs_triplifier.output_files import OutputFiles


def test_writes_both_ontologies_as_ntriples(config):
    paths = OntologyWriter(config).write()

    assert paths == [
        config.output_directory / OutputFiles.ONTOLOGY_GNIS,
        config.output_directory / OutputFiles.ONTOLOGY_USGS,
    ]
    assert all(p.is_file() for p in paths)
    gnis = parse_nt_gz(paths[0])
    usgs = parse_nt_gz(paths[1])
    for source, graph in (("gnis.ttl", gnis), ("usgs.ttl", usgs)):
        expected = Graph().parse(
            OntologyWriter.ONTOLOGIES_DIR / source, format="turtle"
        )
        assert len(graph) == len(expected) > 0
    assert (config.prefix_list["gnis"]["State"], RDF.type, OWL.Class) in gnis
    assert (config.prefix_list["usgs"]["Feature"], RDF.type, OWL.Class) in usgs


def test_base_iris_follow_lod_base_and_site_base(config):
    config.lod_base = "http://example.org/lod"
    config.site_base = "https://example.org"

    graph = parse_nt_gz(OntologyWriter(config).write()[0])

    assert (
        URIRef("http://example.org/lod/gnis/ontology/State"),
        RDF.type,
        OWL.Class,
    ) in graph
    assert not any("gnis-ld.org" in str(term) for triple in graph for term in triple)
    assert (
        URIRef("http://example.org/lod/gnis/ontology/"),
        RDFS.seeAlso,
        URIRef("https://example.org/vocabularies"),
    ) in graph


def test_output_is_identical_across_runs(config):
    writer = OntologyWriter(config)
    first = writer.write()[1].read_bytes()
    second = writer.write()[1].read_bytes()

    assert first == second

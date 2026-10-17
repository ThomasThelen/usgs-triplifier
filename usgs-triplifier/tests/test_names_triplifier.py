from rdflib import Literal
from rdflib.namespace import RDFS, XSD

from conftest import make_text_zip, parse_nt_gz
from usgs_triplifier.config import config
from usgs_triplifier.lib.gnis.names_triplifier import NamesTriplifier


HEADER = "feature_id|feature_name|feature_name_official|citation|date_created"


def test_names_end_to_end(data_dirs):
    input_dir, output_dir = data_dirs
    make_text_zip(
        input_dir,
        "AllNames_National_Text.zip",
        "Text/AllNames_National.txt",
        [
            HEADER,
            '1|Blue Lake|Official|"History of Alameda County" p. 12|01/02/1998',
            "1|Old Blue|Variant|ignored citation|03/04/1999",
            "2|Twin Peaks|Official|Citation Unknown|bogus-date",
        ],
    )

    NamesTriplifier().run()

    graph = parse_nt_gz(output_dir / "names.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]

    # Official name -> label + officialName
    assert (gnisf["1"], RDFS.label, Literal("Blue Lake", lang="en")) in graph
    assert list(graph.objects(gnisf["1"], gnis["officialName"])) == [
        Literal("Blue Lake", lang="en")
    ]
    # Variant name -> alternativeName only, and its citation/date are ignored
    assert list(graph.objects(gnisf["1"], gnis["alternativeName"])) == [
        Literal("Old Blue", lang="en")
    ]
    assert list(graph.objects(gnisf["1"], gnis["dateNameCreated"])) == [
        Literal("1998-01-02", datatype=XSD.date)
    ]

    # Embedded double quotes survive the pipe-delimited parsing intact
    citations = list(graph.objects(gnisf["1"], gnis["citation"]))
    assert citations == [Literal('"History of Alameda County" p. 12', lang="en")]

    # 'Citation Unknown' maps to the well-known IRI; bad date passes through
    assert list(graph.objects(gnisf["2"], gnis["citation"])) == [
        gnis["UnknownCitation"]
    ]
    assert list(graph.objects(gnisf["2"], gnis["dateNameCreated"])) == [
        Literal("bogus-date")
    ]


def test_is_official_accepts_current_and_legacy_flags():
    assert NamesTriplifier._is_official({"feature_name_official": "Official"})
    assert not NamesTriplifier._is_official({"feature_name_official": "Variant"})
    assert NamesTriplifier._is_official({"feature_name_official": "Y"})
    assert not NamesTriplifier._is_official({"feature_name_official": "N"})
    assert not NamesTriplifier._is_official({})

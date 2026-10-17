from rdflib import Literal
from rdflib.namespace import OWL, RDF

from conftest import make_text_zip, parse_nt_gz
from usgs_triplifier.config import config
from usgs_triplifier.lib.gnis.history_triplifier import HistoryTriplifier
from usgs_triplifier.lib.gnis.units_triplifier import UnitsTriplifier


def test_history_end_to_end(data_dirs):
    input_dir, output_dir = data_dirs
    make_text_zip(
        input_dir,
        "FeatureDescriptionHistory_National_Text.zip",
        "Text/FeatureDescriptionHistory_National.txt",
        [
            "feature_id|description|history",
            "1|  A lake.  |Named in 1901.",
            "2|   |",
        ],
    )

    HistoryTriplifier().run()

    graph = parse_nt_gz(output_dir / "history.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]

    assert list(graph.objects(gnisf["1"], gnis["description"])) == [
        Literal("A lake.", lang="en")
    ]
    assert list(graph.objects(gnisf["1"], gnis["history"])) == [
        Literal("Named in 1901.", lang="en")
    ]
    # Whitespace-only and missing values produce no triples
    assert list(graph.predicate_objects(gnisf["2"])) == []


def test_units_end_to_end(data_dirs):
    input_dir, output_dir = data_dirs
    make_text_zip(
        input_dir,
        "GovernmentUnits_National_Text.zip",
        "Text/GovernmentUnits_National.txt",
        [
            "feature_id|unit_type|county_numeric|county_name|state_numeric"
            "|state_alpha|state_name|country_alpha|country_name|feature_name",
            "10|STATE|||06|CA|California|US|United States|California",
            "20|COUNTY|1|Alameda|06|CA|California|US|United States|Alameda County",
            "30|COUNTRY||||||US|United States|United States",
        ],
    )

    UnitsTriplifier().run()

    graph = parse_nt_gz(output_dir / "units.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]
    gnisf_alias = config.prefix_list["gnisf-alias"]

    # STATE row
    assert (gnisf["10"], RDF.type, gnis["State"]) in graph
    assert list(graph.objects(gnisf["10"], gnis["stateId"])) == [Literal("06")]
    assert list(graph.objects(gnisf["10"], gnis["stateCode"])) == [Literal("CA")]
    assert list(graph.objects(gnisf["10"], gnis["stateName"])) == [
        Literal("California", lang="en")
    ]
    assert (gnisf_alias["California"], OWL.sameAs, gnisf["10"]) in graph

    # COUNTY row: zero-padded code, state alias link, no state code/id
    assert (gnisf["20"], RDF.type, gnis["County"]) in graph
    assert list(graph.objects(gnisf["20"], gnis["countyCode"])) == [Literal("001")]
    assert list(graph.objects(gnisf["20"], gnis["countyName"])) == [
        Literal("Alameda", lang="en")
    ]
    assert list(graph.objects(gnisf["20"], gnis["state"])) == [
        gnisf_alias["California"]
    ]
    assert list(graph.objects(gnisf["20"], gnis["stateCode"])) == []
    assert (gnisf_alias["California.Alameda"], OWL.sameAs, gnisf["20"]) in graph

    # COUNTRY row is skipped entirely
    assert list(graph.predicate_objects(gnisf["30"])) == []

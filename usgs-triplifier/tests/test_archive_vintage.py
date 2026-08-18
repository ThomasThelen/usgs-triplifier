"""
Backfilling from the USGS file archive: the pre-GPKG vintages (through 2021)
are pipe-delimited text with uppercase headers, two-letter state codes, and a
Y/N official-name flag. Headers and rows here mirror the real 2021-08-25
files under StagedProducts/GeographicNames/Archive/.
"""

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from conftest import make_text_zip, parse_nt_gz
from usgs_triplifier.config import config
from usgs_triplifier.lib import geonames_crosswalk
from usgs_triplifier.lib.gnis import features_triplifier
from usgs_triplifier.lib.gnis.features_triplifier import FeaturesTriplifier
from usgs_triplifier.lib.gnis.history_triplifier import HistoryTriplifier
from usgs_triplifier.lib.gnis.names_triplifier import NamesTriplifier
from usgs_triplifier.lib.gnis.units_triplifier import UnitsTriplifier

NATIONAL_FILE_HEADER = (
    "FEATURE_ID|FEATURE_NAME|FEATURE_CLASS|STATE_ALPHA|STATE_NUMERIC"
    "|COUNTY_NAME|COUNTY_NUMERIC|PRIMARY_LAT_DMS|PRIM_LONG_DMS|PRIM_LAT_DEC"
    "|PRIM_LONG_DEC|SOURCE_LAT_DMS|SOURCE_LONG_DMS|SOURCE_LAT_DEC"
    "|SOURCE_LONG_DEC|ELEV_IN_M|ELEV_IN_FT|MAP_NAME|DATE_CREATED|DATE_EDITED"
)


def _national_file_zip(input_dir):
    return make_text_zip(
        input_dir,
        "NationalFile.zip",
        "NationalFile_20210825.txt",
        [
            NATIONAL_FILE_HEADER,
            "1414314|Denali|Summit|AK|02|Denali|068|631712N|1510038W|63.0690949"
            "|-151.0063|||||6144|20157|Mount McKinley A-3|01/01/2000|",
            # Unknown coordinates ("0") -> no geometry; VI expands to the
            # modern GPKG state spelling
            "999|Salt Pond|Lake|VI|78|St. Thomas|030|||0|0|||||0|0|Map|02/02/2001|",
        ],
    )


def test_features_from_archived_national_file(data_dirs, monkeypatch):
    input_dir, output_dir = data_dirs
    monkeypatch.setattr(features_triplifier, "feature_aliases", {})
    monkeypatch.setattr(config, "archive_mode", True)
    _national_file_zip(input_dir)

    FeaturesTriplifier()

    graph = parse_nt_gz(output_dir / "features.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]
    usgs = config.prefix_list["usgs"]
    geosparql = config.prefix_list["geosparql"]
    gnisf_alias = config.prefix_list["gnisf-alias"]
    qudt = config.prefix_list["qudt"]

    assert (gnisf["1414314"], RDF.type, usgs["Summit"]) in graph

    # State code expanded to the full name for gnis:state and the alias
    assert list(graph.objects(gnisf["1414314"], gnis["state"])) == [
        gnisf_alias["Alaska"]
    ]
    aliases = parse_nt_gz(output_dir / "feature-aliases.nt.gz")
    assert list(
        aliases.objects(gnisf_alias["Alaska.Denali.Summit.Denali"], OWL.sameAs)
    ) == [gnisf["1414314"]]

    # Elevation only exists in the archived vintages
    elev_nodes = list(graph.objects(gnisf["1414314"], gnis["elevation"]))
    assert len(elev_nodes) == 1 and isinstance(elev_nodes[0], BNode)
    assert list(graph.objects(elev_nodes[0], qudt["numericValue"])) == [
        Literal("20157", datatype=XSD.double)
    ]

    # Geometry from the decimal coordinates; text-format "0" means unknown
    geom = URIRef(f"{config.geo_base}/point/gnisf.1414314")
    assert list(graph.objects(gnisf["1414314"], geosparql["hasGeometry"])) == [geom]
    wkt = list(graph.objects(geom, geosparql["asWKT"]))
    assert len(wkt) == 1 and "POINT(-151.0063 63.0690949)" in str(wkt[0])
    assert list(graph.objects(gnisf["999"], geosparql["hasGeometry"])) == []
    assert list(graph.objects(gnisf["999"], gnis["elevation"])) == []

    assert list(graph.objects(gnisf["999"], gnis["state"])) == [
        gnisf_alias["United_States_Virgin_Islands"]
    ]

    assert list(graph.objects(gnisf["1414314"], gnis["dateFeatureCreated"])) == [
        Literal("2000-01-01", datatype=XSD.date)
    ]


def test_names_from_archived_all_names(data_dirs, monkeypatch):
    input_dir, output_dir = data_dirs
    monkeypatch.setattr(config, "archive_mode", True)
    make_text_zip(
        input_dir,
        "AllNames.zip",
        "AllNames_20210825.txt",
        [
            "FEATURE_ID|FEATURE_NAME|FEATURE_NAME_OFFICIAL|CITATION|DATE_CREATED",
            "1414314|Denali|Y|Board decision 2015|08/28/2015",
            "1414314|Mount McKinley|N||01/01/2000",
        ],
    )

    NamesTriplifier()

    graph = parse_nt_gz(output_dir / "names.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]

    # In 2021 the official name was still Denali
    assert (gnisf["1414314"], RDFS.label, Literal("Denali", lang="en")) in graph
    assert list(graph.objects(gnisf["1414314"], gnis["officialName"])) == [
        Literal("Denali", lang="en")
    ]
    assert list(graph.objects(gnisf["1414314"], gnis["alternativeName"])) == [
        Literal("Mount McKinley", lang="en")
    ]


def test_history_from_archived_description_history(data_dirs, monkeypatch):
    input_dir, output_dir = data_dirs
    monkeypatch.setattr(config, "archive_mode", True)
    make_text_zip(
        input_dir,
        "Feature_Description_History.zip",
        "Feature_Description_History_20210825.txt",
        [
            "FEATURE_ID|DESCRIPTION|HISTORY",
            "1414314|Highest summit in North America|Named for a president.",
        ],
    )

    HistoryTriplifier()

    graph = parse_nt_gz(output_dir / "history.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]
    assert list(graph.objects(gnisf["1414314"], gnis["description"])) == [
        Literal("Highest summit in North America", lang="en")
    ]
    assert list(graph.objects(gnisf["1414314"], gnis["history"])) == [
        Literal("Named for a president.", lang="en")
    ]


def test_units_from_archived_govt_units(data_dirs, monkeypatch):
    input_dir, output_dir = data_dirs
    monkeypatch.setattr(config, "archive_mode", True)
    make_text_zip(
        input_dir,
        "GOVT_UNITS.zip",
        "GOVT_UNITS_20210825.txt",
        [
            "FEATURE_ID|UNIT_TYPE|COUNTY_NUMERIC|COUNTY_NAME|STATE_NUMERIC"
            "|STATE_ALPHA|STATE_NAME|COUNTRY_ALPHA|COUNTRY_NAME|FEATURE_NAME",
            "1419988|COUNTY|068|Denali|02|AK|Alaska|US|United States|Denali Borough",
            "1785533|STATE||;|02|AK|Alaska|US|United States|State of Alaska",
        ],
    )

    UnitsTriplifier()

    graph = parse_nt_gz(output_dir / "units.nt.gz")
    gnisf = config.prefix_list["gnisf"]
    gnis = config.prefix_list["gnis"]
    gnisf_alias = config.prefix_list["gnisf-alias"]

    assert (gnisf["1419988"], RDF.type, gnis["County"]) in graph
    assert list(graph.objects(gnisf["1419988"], gnis["state"])) == [
        gnisf_alias["Alaska"]
    ]
    assert list(graph.objects(gnisf_alias["Alaska.Denali"], OWL.sameAs)) == [
        gnisf["1419988"]
    ]
    assert (gnisf["1785533"], RDF.type, gnis["State"]) in graph
    assert list(graph.objects(gnisf["1785533"], gnis["stateName"])) == [
        Literal("Alaska", lang="en")
    ]


def test_geonames_loader_reads_archived_national_file(data_dirs, monkeypatch):
    input_dir, _ = data_dirs
    monkeypatch.setattr(config, "archive_mode", True)
    _national_file_zip(input_dir)

    gnis = geonames_crosswalk._load_gnis()

    # The zero-coordinate row is dropped; the state code passes through
    assert list(gnis["feature_id"]) == ["1414314"]
    assert list(gnis["state"]) == ["AK"]
    assert list(gnis["name"]) == ["Denali"]

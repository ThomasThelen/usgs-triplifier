import gzip
from datetime import datetime

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, XSD

from .text_triplifier import triplify_text_files
from .triplifier import (
    NTStreamSink,
    TriplifierConfig,
    FieldDescriptor,
    clean,
    normalize_feature_id,
)
from ...config import config
from ...states import States

# Class name mappings
GNIS_CLASS_MAPPINGS = {
    "Range": "MountainRange",
    "Falls": "Waterfall",
    "Woods": "Woodland",
    "Oilfield": "OilField",
    "Civil": "CivilGovernment",
    "Pillar": "Rock",
}

# Track feature aliases for disambiguation
feature_aliases: dict[str, list[str]] = {}


class FeaturesTriplifier:
    """
    Abstraction over creating triples out of the features dataset.
    """

    def __init__(self):
        config.output_directory.mkdir(parents=True, exist_ok=True)
        field_mappings = {
            "feature_id": FieldDescriptor(
                predicate="gnis:featureId",
                object=self.feature_id_object,
            ),
            "feature_class": FieldDescriptor(
                predicate="rdf:type",
                object=self.feature_class_object,
            ),
            "state_name": FieldDescriptor(
                predicate="gnis:state",
                object=self.state_object,
                optional=True,
            ),
            "county_name": FieldDescriptor(
                predicate="gnis:county",
                object=self.county_object,
                optional=True,
            ),
            "prim_lat_dec": self.prim_lat_dec_field,
            "map_name": FieldDescriptor(
                predicate="gnis:mapName",
                object=self.map_name_object,
                optional=True,
            ),
            "date_created": FieldDescriptor(
                predicate="gnis:dateFeatureCreated",
                object=self.date_object,
                optional=True,
            ),
            "date_edited": FieldDescriptor(
                predicate="gnis:dateFeatureEdited",
                object=self.date_object,
                optional=True,
            ),
        }
        # Only legacy dumps have an elevation column
        if config.legacy_dump:
            field_mappings["elev_in_ft"] = self.elev_in_ft_field
        triples_mapping = TriplifierConfig(
            subject=self.get_subject,
            fields=field_mappings,
        )
        # Legacy dumps put the features in NationalFile
        pattern = (
            "NationalFile*.zip" if config.legacy_dump else "DomesticNames*_Text.zip"
        )
        triplify_text_files(triples_mapping, pattern, "features")
        self._write_aliases()

    def get_subject(self, row: dict, graph: Graph) -> str | None:
        """
        Generate subject IRI for a GNIS feature.

        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: Subject IRI string or None if invalid.
        """
        feature_id = normalize_feature_id(row.get("feature_id", ""))

        # NationalFile rows carry only the state code; expand it here (rows
        # are shared with the field processors, so gnis:state and the alias
        # both see the full name)
        if not row.get("state_name") and row.get("state_alpha"):
            alpha = str(row["state_alpha"])
            row["state_name"] = States.name_for(alpha) or alpha

        # Get and normalize class name
        feature_class = str(row.get("feature_class", "")).replace(" ", "")
        if feature_class in GNIS_CLASS_MAPPINGS:
            feature_class = GNIS_CLASS_MAPPINGS[feature_class]

        # Get state name (GPKG uses state_name instead of state_alpha)
        state_name = str(row.get("state_name", ""))

        # Build feature alias
        feature_name = str(row.get("feature_name", ""))
        county_name = str(row.get("county_name", ""))
        alias_id = f"{clean(state_name)}.{clean(county_name)}.{feature_class}.{clean(feature_name)}"

        # Track aliases for later disambiguation
        if alias_id in feature_aliases:
            feature_aliases[alias_id].append(feature_id)
        else:
            feature_aliases[alias_id] = [feature_id]

        return f"gnisf:{feature_id}"

    def feature_id_object(self, value: str, row: dict, graph: Graph) -> Literal:
        """
        Convert feature ID to literal.

        :param value: Feature ID value.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal containing the feature ID.
        """
        return Literal(value)

    def feature_class_object(self, value: str, row: dict, graph: Graph) -> URIRef:
        """
        Convert feature class to RDF type.

        :param value: Feature class name.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: URIRef for the corresponding USGS ontology class.
        """
        class_name = value.replace(" ", "")
        if class_name in GNIS_CLASS_MAPPINGS:
            class_name = GNIS_CLASS_MAPPINGS[class_name]
        return config.prefix_list["usgs"][class_name]

    def state_object(self, value: str, row: dict, graph: Graph) -> URIRef | str:
        """
        Convert state name to feature alias URI.

        :param value: State name value.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: URIRef for the state alias or empty string if no value.
        """
        if not value:
            return ""
        return config.prefix_list["gnisf-alias"][clean(value)]

    def county_object(self, value: str, row: dict, graph: Graph) -> URIRef:
        """
        Convert county name to feature alias URI.

        :param value: County name value.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: URIRef for the county alias or UnknownCounty if no value.
        """
        if value:
            state_name = str(row.get("state_name", ""))
            return config.prefix_list["gnisf-alias"][
                f"{clean(state_name)}.{clean(value)}"
            ]
        return config.prefix_list["gnis"]["UnknownCounty"]

    def prim_lat_dec_field(self, value: str, row: dict, graph: Graph) -> dict | None:
        """
        Process primary latitude and generate the point geometry.

        :param value: Primary latitude value.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph to add geometry triples to.
        :return: Dictionary of predicate-object pairs or None if no geometry.
        """
        # Unknown coordinates are written as "0.0" in the current products
        # and "0" in legacy dumps
        if not value or value in ("0.0", "0"):
            return None

        lat = value
        lng = str(row.get("prim_long_dec") or "")
        if not lng:
            return None

        feature_id = normalize_feature_id(row.get("feature_id", ""))

        geom_iri = f"{config.geo_base}/point/gnisf.{feature_id}"
        point_wkt = f"POINT({lng} {lat})"

        # Add WKT literal to geometry node
        geom_uri = URIRef(geom_iri)
        geosparql = config.prefix_list["geosparql"]

        wkt_literal = Literal(
            f"<http://www.opengis.net/def/crs/OGC/1.3/CRS84>{point_wkt}",
            datatype=geosparql["wktLiteral"],
        )
        graph.add((geom_uri, geosparql["asWKT"], wkt_literal))

        return {
            "geosparql:hasGeometry": [f">{geom_iri}"],
        }

    def elev_in_ft_field(self, value: str, row: dict, graph: Graph) -> dict | None:
        """
        Process elevation in feet and return nested blank node with QUDT properties.

        :param value: Elevation value in feet.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: Dictionary with nested blank node properties or None if no elevation.
        """
        elev_value = value.strip()
        if not elev_value or elev_value == "0":
            return None

        return {
            "gnis:elevation": {
                "qudt:numericValue": [f'^xsd:double"{elev_value}'],
                "qudt:unit": ["unit:FT"],
            },
        }

    def map_name_object(self, value: str, row: dict, graph: Graph) -> Literal:
        """
        Convert map name to language-tagged literal.

        :param value: Map name value.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with English language tag.
        """
        return Literal(value, lang="en")

    def date_object(self, value: str, row: dict, graph: Graph) -> Literal | str:
        """
        Convert date string to XSD date literal.

        :param value: Date string value.
        :param row: Dictionary representing a source row.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with XSD date datatype or empty string if no value.
        """
        if not value:
            return ""
        try:
            # Handle ISO format from GPKG (e.g., '1998-10-06T06:13:42')
            if "T" in value:
                dt = datetime.fromisoformat(value)
            else:
                dt = datetime.strptime(value, "%m/%d/%Y")
            return Literal(dt.strftime("%Y-%m-%d"), datatype=XSD.date)
        except ValueError:
            return Literal(value)

    def _write_aliases(self) -> None:
        """
        Writes the feature aliases collected while the features streamed.
        """
        gnisf = config.prefix_list["gnisf"]
        gnisf_alias = config.prefix_list["gnisf-alias"]
        gnis = config.prefix_list["gnis"]

        # Stream the aliases out; millions of them accumulate over a full run
        aliases_path = config.output_directory / "feature-aliases.nt.gz"
        with gzip.open(aliases_path, "wt", encoding="utf-8") as out:
            sink = NTStreamSink(out)
            for alias, features in feature_aliases.items():
                if not alias:
                    continue
                alias_uri = gnisf_alias[alias]

                if len(features) == 1:
                    # Unique - add owl:sameAs
                    sink.add((alias_uri, OWL.sameAs, gnisf[features[0]]))
                else:
                    # Ambiguous - add disambiguation links
                    for feature_id in features:
                        sink.add(
                            (alias_uri, gnis["disambiguatesTo"], gnisf[feature_id])
                        )
        print(f"Aliases written to {aliases_path}")


def main():
    """Run the features triplifier."""
    config.output_directory.mkdir(parents=True, exist_ok=True)
    FeaturesTriplifier()


if __name__ == "__main__":
    main()

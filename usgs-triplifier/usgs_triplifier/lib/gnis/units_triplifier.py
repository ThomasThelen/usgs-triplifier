import re

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL

from .triplifier import triplify_all, TriplifierConfig, FieldDescriptor
from ...config import config


class UnitsTriplifier:
    """
    Abstraction over creating RDF triples about government units

    Uses the GovernmentUnits table from GPKG files which contains:
        - feature_id, unit_type (STATE/COUNTY)
        - state_alpha, state_name, state_numeric
        - county_name, county_numeric
        - country_alpha, country_name
        - feature_name
    """

    def __init__(self):
        field_mappings = {
            "feature_id": FieldDescriptor(
                predicate="gnis:featureId",
                object=self.feature_id_object,
            ),
            "unit_type": FieldDescriptor(
                predicate="rdf:type",
                object=self.unit_type_object,
            ),
            "county_numeric": FieldDescriptor(
                predicate="gnis:countyCode",
                object=self.county_numeric_object,
                optional=True,
            ),
            "county_name": FieldDescriptor(
                predicate="gnis:countyName",
                object=self.county_name_object,
                optional=True,
            ),
            "state_numeric": FieldDescriptor(
                predicate="gnis:stateId",
                object=self.state_numeric_object,
                optional=True,
            ),
            "state_alpha": FieldDescriptor(
                predicate="gnis:stateCode",
                object=self.state_alpha_object,
                optional=True,
            ),
            "state_name": self.state_name_field,
            "country_name": FieldDescriptor(
                predicate="gnis:country",
                object=self.country_name_object,
            ),
            "feature_name": FieldDescriptor(
                predicate="rdfs:label",
                object=self.feature_name_object,
            ),
        }
        triples_mapping = TriplifierConfig(
            subject=self.get_subject,
            fields=field_mappings,
        )
        triplify_all(triples_mapping, "GovernmentUnits", "units")

    def clean(self, s: str) -> str:
        """
        Clean IRIs by replacing non-word characters with underscores.

        :param s: String to clean.
        :return: Cleaned string with non-word characters replaced by underscores.
        """
        return re.sub(r"[^\w]", "_", s)

    def get_subject(self, row: dict, graph: Graph) -> str | None:
        """
        Generate subject IRI for a GNIS unit and add alias sameAs relation.

        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph to add sameAs relations to.
        :return: Subject IRI string or None if invalid unit type.
        """
        # Get feature ID (handle both string and int)
        feature_id_raw = row.get("feature_id", "")
        if isinstance(feature_id_raw, (int, float)):
            feature_id = str(int(feature_id_raw))
        else:
            feature_id = str(feature_id_raw).lstrip("0") or "0"

        feature_iri = f"gnisf:{feature_id}"

        # Build alias based on unit type
        unit_type = str(row.get("unit_type", ""))
        state_name = str(row.get("state_name", ""))
        county_name = str(row.get("county_name", ""))

        if unit_type == "COUNTY":
            alias = f"{self.clean(state_name)}.{self.clean(county_name)}"
        elif unit_type == "STATE":
            alias = self.clean(state_name)
        else:
            # Skip unknown unit types
            return None

        # Add owl:sameAs from alias to feature
        alias_uri = config.prefix_list["gnisf-alias"][alias]
        feature_uri = config.prefix_list["gnisf"][feature_id]
        graph.add((alias_uri, OWL.sameAs, feature_uri))

        return feature_iri

    def feature_id_object(self, value: str, row: dict, graph: Graph) -> Literal:
        """
        Convert feature ID to literal.

        :param value: Feature ID value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal containing the feature ID.
        """
        return Literal(value)

    def unit_type_object(self, value: str, row: dict, graph: Graph) -> URIRef:
        """
        Convert unit type to RDF type (e.g., COUNTY -> gnis:County).

        :param value: Unit type value (e.g., 'COUNTY', 'STATE').
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: URIRef for the corresponding GNIS ontology class.
        """
        # Title case: COUNTY -> County, STATE -> State
        class_name = value[0] + value[1:].lower()
        return config.prefix_list["gnis"][class_name]

    def county_numeric_object(self, value: str, row: dict, graph: Graph) -> Literal:
        """
        Convert county numeric code to literal.

        :param value: County numeric code value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal containing the county code.
        """
        return Literal(value)

    def county_name_object(self, value: str, row: dict, graph: Graph) -> Literal:
        """
        Convert county name to language-tagged literal.

        :param value: County name value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with English language tag.
        """
        return Literal(value, lang="en")

    def state_numeric_object(
        self, value: str, row: dict, graph: Graph
    ) -> Literal | str:
        """
        Convert state numeric code to literal (only for STATE units).

        :param value: State numeric code value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal containing the state code or empty string for non-STATE units.
        """
        if str(row.get("unit_type", "")) == "STATE":
            return Literal(value)
        return ""

    def state_alpha_object(self, value: str, row: dict, graph: Graph) -> Literal | str:
        """
        Convert state alpha code to literal.

        :param value: State alpha code value (e.g., 'CA', 'NY').
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal containing the state code or empty string for non-STATE units.
        """
        if str(row.get("unit_type", "")) == "STATE":
            return Literal(value)
        return ""

    def state_name_field(self, value: str, row: dict, graph: Graph) -> dict | None:
        """
        Process state name field differently based on unit type.

        :param value: State name value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: Dictionary of predicate-object pairs or None if no value.
        """
        if not value:
            return None

        if str(row.get("unit_type", "")) == "COUNTY":
            # For counties, link to state alias
            return {
                "gnis:state": [f"gnisf-alias:{self.clean(value)}"],
            }
        else:
            # For states, add state name as literal
            return {
                "gnis:stateName": [Literal(value, lang="en")],
            }

    def country_name_object(self, value: str, row: dict, graph: Graph) -> URIRef:
        """
        Convert country name to feature alias URI.

        :param value: Country name value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: URIRef for the country alias.
        """
        return config.prefix_list["gnisf-alias"][self.clean(value)]

    def feature_name_object(self, value: str, row: dict, graph: Graph) -> Literal:
        """
        Convert feature name to language-tagged literal.

        :param value: Feature name value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with English language tag.
        """
        return Literal(value, lang="en")


if __name__ == "__main__":
    config.output_directory.mkdir(parents=True, exist_ok=True)
    UnitsTriplifier()

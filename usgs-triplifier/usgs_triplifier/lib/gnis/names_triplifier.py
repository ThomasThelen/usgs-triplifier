"""
GNIS Names Triplifier Configuration.

Processes GNIS GPKG files and generates RDF triples for
feature names (official and alternative names).
"""

from datetime import datetime

from rdflib import Graph, Literal
from rdflib.namespace import XSD

from .triplifier import triplify_all, TriplifierConfig, FieldDescriptor
from ...config import config


class NamesTriplifier:
    """
    Abstraction over triplifying the Gaz_Names table.
    Uses the Gaz_Names table from GPKG files which contains:
        - feature_id, feature_name
        - feature_name_official (1 = official, 0 = alternative)
        - name_permanent_identifier
    """

    def __init__(self):
        # Column mappings
        field_mappings = {
            "feature_name": NamesTriplifier.feature_name_field,
            "citation": FieldDescriptor(
                predicate="gnis:citation",
                object=NamesTriplifier.citation_object,
                optional=True,
            ),
            "date_created": FieldDescriptor(
                predicate="gnis:dateNameCreated",
                object=NamesTriplifier.date_created_object,
                optional=True,
            ),
        }
        triples_mapping = TriplifierConfig(
            subject=self.get_subject,
            fields=field_mappings,
        )
        # Run triplifier on all GPKG files, reading from Gaz_Names table
        triplify_all(triples_mapping, "Gaz_Names", "names")

    @staticmethod
    def get_subject(row: dict, graph: Graph) -> str | None:
        """
        Generate subject IRI for a GNIS feature.

        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: Subject IRI string or None if invalid.
        """
        feature_id_raw = row.get("feature_id", "")
        if isinstance(feature_id_raw, (int, float)):
            feature_id = str(int(feature_id_raw))
        else:
            feature_id = str(feature_id_raw).lstrip("0") or "0"
        return f"gnisf:{feature_id}"

    @staticmethod
    def feature_name_field(value: str, row: dict, graph: Graph) -> dict | None:
        """
        Process feature name based on whether it's official or alternative.

        :param value: Feature name value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: Dictionary of predicate-object pairs or None if no value.
        """
        if not value:
            return None

        # Check if official (1) or alternative (0)
        is_official = row.get("feature_name_official")
        if isinstance(is_official, (int, float)):
            is_official = int(is_official) == 1
        else:
            is_official = str(is_official) == "1"

        if is_official:
            # Official name: add as label and official name
            return {
                "rdfs:label": [Literal(value, lang="en")],
                "gnis:officialName": [Literal(value, lang="en")],
            }
        else:
            # Alternative name
            return {
                "gnis:alternativeName": [Literal(value, lang="en")],
            }

    @staticmethod
    def citation_object(value: str, row: dict, graph: Graph) -> Literal | str:
        """
        Convert citation to literal (only for official names).

        :param value: Citation text value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal or URIRef for unknown citation, or empty string.
        """
        # Only process citation for official names
        is_official = row.get("feature_name_official")
        if isinstance(is_official, (int, float)):
            is_official = int(is_official) == 1
        else:
            is_official = str(is_official) == "1"

        if not is_official:
            return ""

        if not value or value.strip() == "":
            return ""

        if value == "Citation Unknown":
            return "gnis:UnknownCitation"

        return Literal(value, lang="en")

    @staticmethod
    def date_created_object(value: str, row: dict, graph: Graph) -> Literal | str:
        """
        Convert date created to XSD date literal (only for official names).

        :param value: Date string value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with XSD date datatype or empty string.
        """
        # Only process date for official names
        is_official = row.get("feature_name_official")
        if isinstance(is_official, (int, float)):
            is_official = int(is_official) == 1
        else:
            is_official = str(is_official) == "1"

        if not is_official:
            return ""

        if not value or value.strip() == "":
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


def main():
    """Run the names triplifier."""
    # Ensure output directory exists
    config.output_directory.mkdir(parents=True, exist_ok=True)
    NamesTriplifier()


if __name__ == "__main__":
    main()

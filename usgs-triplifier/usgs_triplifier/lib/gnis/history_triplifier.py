from rdflib import Graph, Literal

from .text_triplifier import triplify_text_files
from .triplifier import (
    TriplifierConfig,
    FieldDescriptor,
    normalize_feature_id,
)
from ...config import config
from ...output_files import OutputFiles
from ...usgs_products import UsgsProducts


class HistoryTriplifier:
    """
    Abstraction over triplifying the feature descriptions and histories
    """

    def __init__(self):
        # Column mappings
        field_mappings = {
            "description": FieldDescriptor(
                predicate="gnis:description",
                object=HistoryTriplifier.create_description,
                optional=True,
            ),
            "history": FieldDescriptor(
                predicate="gnis:history",
                object=HistoryTriplifier.create_history,
                optional=True,
            ),
        }
        triples_mapping = TriplifierConfig(
            subject=self.get_subject,
            fields=field_mappings,
        )

        triplify_text_files(
            triples_mapping,
            UsgsProducts.HISTORY.pattern_for(config.legacy_dump),
            OutputFiles.HISTORY,
        )

    @staticmethod
    def get_subject(row: dict, graph: Graph) -> str | None:
        """
        Generate subject IRI for a GNIS feature.

        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: Subject IRI string or None if invalid.
        """
        return f"gnisf:{normalize_feature_id(row.get('feature_id', ''))}"

    @staticmethod
    def create_description(value: str, row: dict, graph: Graph) -> Literal | str:
        """
        Convert description to language-tagged literal.

        :param value: Description text value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with English language tag or empty string if no value.
        """
        # Skip empty or whitespace-only descriptions
        if not value or value.strip() == "":
            return ""
        return Literal(value.strip(), lang="en")

    @staticmethod
    def create_history(value: str, row: dict, graph: Graph) -> Literal | str:
        """
        Convert history to language-tagged literal.

        :param value: History text value.
        :param row: Dictionary representing a row from the GPKG table.
        :param graph: RDF graph (unused but required by interface).
        :return: RDF Literal with English language tag or empty string if no value.
        """
        # Skip empty or whitespace-only history
        if not value or value.strip() == "":
            return ""
        return Literal(value.strip(), lang="en")


def main():
    """Run the history triplifier."""
    config.output_directory.mkdir(parents=True, exist_ok=True)
    HistoryTriplifier()


if __name__ == "__main__":
    main()

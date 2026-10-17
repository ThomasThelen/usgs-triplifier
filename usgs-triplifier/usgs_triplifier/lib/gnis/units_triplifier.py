from collections.abc import Callable
from typing import ClassVar

from rdflib import Literal, URIRef
from rdflib.namespace import OWL

from ...output_files import OutputFiles
from ...usgs_products import UsgsProduct, UsgsProducts
from .identifiers import FeatureIds
from .rdf import NTriplesWriter
from .triplifier import FieldDescriptor, Triplifier


class UnitsTriplifier(Triplifier):
    """
    Converts the GNIS government units (GovernmentUnits) into units.nt.gz.

    Only COUNTY and STATE rows are written. Each gets owl:sameAs from its
    gnisf-alias: IRI (the state, or state.county), which is how features'
    gnis:state and gnis:county links reach the unit.
    """

    product: ClassVar[UsgsProduct] = UsgsProducts.UNITS
    output_name: ClassVar[str] = OutputFiles.UNITS

    def fields(self) -> dict[str, FieldDescriptor | Callable]:
        """
        Lists the unit columns that become triples.

        :return: Mapping of column name to its field mapping.
        """
        return {
            "feature_id": FieldDescriptor("gnis:featureId", self.plain_literal),
            "unit_type": FieldDescriptor("rdf:type", self.unit_type_object),
            "county_numeric": FieldDescriptor(
                "gnis:countyCode", self.county_numeric_object, optional=True
            ),
            "county_name": FieldDescriptor(
                "gnis:countyName", self.english_literal, optional=True
            ),
            "state_numeric": FieldDescriptor(
                "gnis:stateId", self.state_only_object, optional=True
            ),
            "state_alpha": FieldDescriptor(
                "gnis:stateCode", self.state_only_object, optional=True
            ),
            "state_name": self.state_name_field,
            "country_name": FieldDescriptor("gnis:country", self.country_name_object),
            "feature_name": FieldDescriptor("rdfs:label", self.english_literal),
        }

    def subject(self, row: dict[str, str], writer: NTriplesWriter) -> str | None:
        """
        Builds the unit's IRI and writes owl:sameAs from its alias to it.

        :param row: Source row.
        :param writer: Writer the owl:sameAs triple is added to.
        :return: The unit's gnisf: IRI, or None for a unit that is neither a
            COUNTY nor a STATE.
        """
        unit_type = row.get("unit_type", "")
        state = FeatureIds.alias_part(row.get("state_name", ""))
        if unit_type == "COUNTY":
            alias = f"{state}.{FeatureIds.alias_part(row.get('county_name', ''))}"
        elif unit_type == "STATE":
            alias = state
        else:
            return None

        feature_id = FeatureIds.normalize(row.get("feature_id", ""))
        writer.add(
            (
                self.config.prefix_list["gnisf-alias"][alias],
                OWL.sameAs,
                self.config.prefix_list["gnisf"][feature_id],
            )
        )
        return f"gnisf:{feature_id}"

    def unit_type_object(self, value: str, row: dict) -> URIRef:
        """
        Builds the rdf:type of the unit, e.g. COUNTY to gnis:County.

        :param value: Unit type in capitals.
        :param row: Source row (unused).
        :return: The gnis: class IRI.
        """
        return self.config.prefix_list["gnis"][value.capitalize()]

    def county_numeric_object(self, value: str, row: dict) -> Literal:
        """
        Builds the gnis:countyCode literal. County FIPS codes have three
        digits, and the source drops leading zeros, so they are restored.

        :param value: County code.
        :param row: Source row (unused).
        :return: The three-digit code as a plain literal.
        """
        return Literal(value.zfill(3))

    def state_only_object(self, value: str, row: dict) -> Literal | str:
        """
        Builds the gnis:stateId or gnis:stateCode literal, which only STATE
        units get.

        :param value: State FIPS code or two-letter code.
        :param row: Source row; unit_type selects whether a triple is written.
        :return: The value as a plain literal for a STATE, otherwise an empty
            string.
        """
        return Literal(value) if row.get("unit_type") == "STATE" else ""

    def state_name_field(
        self, value: str, row: dict, writer: NTriplesWriter
    ) -> dict | None:
        """
        Builds the state triple: a COUNTY gets gnis:state linking to its
        state's alias; a STATE gets its name as gnis:stateName.

        :param value: Full state name.
        :param row: Source row; unit_type selects the triple.
        :param writer: Writer the row's triples go to (unused).
        :return: The predicate-object pair, or None when the state name is empty.
        """
        if not value:
            return None
        if row.get("unit_type") == "COUNTY":
            return {"gnis:state": [f"gnisf-alias:{FeatureIds.alias_part(value)}"]}
        return {"gnis:stateName": [Literal(value, lang="en")]}

    def country_name_object(self, value: str, row: dict) -> URIRef:
        """
        Builds the gnis:country link to the country's alias.

        :param value: Country name.
        :param row: Source row (unused).
        :return: The country's gnisf-alias: IRI.
        """
        return self.config.prefix_list["gnisf-alias"][FeatureIds.alias_part(value)]

import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar, TextIO

import requests

from ..output_files import OutputFiles
from .crosswalk import Crosswalk
from .gnis.identifiers import FeatureIds


class WikidataCrosswalk(Crosswalk):
    """
    Links GNIS features to Wikidata and the datasets Wikidata links them to.

    Wikidata items record their GNIS feature id in property P590. For every
    such item the crosswalk writes these links.

        - owl:sameAs the Wikidata item
        - owl:sameAs the DBpedia resource of the item's English Wikipedia article
        - owl:sameAs the Who's On First place (P6766)
        - skos:closeMatch the Library of Congress authority (P244)
        - skos:closeMatch the Getty Thesaurus of Geographic Names place (P1667)

    The items' GeoNames ids (P1566) are written to wikidata-geonames.csv.
    """

    output_name: ClassVar[str] = OutputFiles.WIKIDATA_CROSSWALK

    QUERY: ClassVar[
        str
    ] = """SELECT ?item ?gnisId ?article ?geonamesId ?wofId ?locId ?tgnId WHERE {
  ?item wdt:P590 ?gnisId .
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
  OPTIONAL { ?item wdt:P1566 ?geonamesId . }
  OPTIONAL { ?item wdt:P6766 ?wofId . }
  OPTIONAL { ?item wdt:P244 ?locId . }
  OPTIONAL { ?item wdt:P1667 ?tgnId . }
}"""

    # The endpoint sometimes returns errors or truncated results under load,
    # so a failed query is retried, waiting RETRY_WAIT_S times the attempt
    # number in between
    ATTEMPTS: ClassVar[int] = 3
    RETRY_WAIT_S: ClassVar[int] = 15

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def build(self) -> Path | None:
        """
        Queries Wikidata and writes the links and the GeoNames pairs.

        :return: Path of the links file, or None when every query attempt failed.
        """
        bindings = self._query()
        if bindings is None:
            self._log.warning("Wikidata query failed; writing no Wikidata links")
            return None

        pairs_path = self.config.output_directory / OutputFiles.WIKIDATA_GEONAMES_PAIRS
        with open(pairs_path, "w", encoding="utf-8") as pairs:
            self.write_lines(self._links(bindings, pairs))
        return self.output_path

    def _query(self) -> list[dict] | None:
        """
        Runs QUERY against the Wikidata SPARQL endpoint.

        :return: The result bindings, or None when every attempt failed.
        """
        for attempt in range(1, self.ATTEMPTS + 1):
            try:
                response = requests.post(
                    self.config.wikidata_endpoint,
                    data={"query": self.QUERY},
                    headers={
                        "Accept": "application/sparql-results+json",
                        "User-Agent": "usgs-triplifier (support@dataone.org)",
                    },
                    timeout=300,
                )
                response.raise_for_status()
                # Some returned values contain raw control characters, which
                # json.loads rejects unless strict is False
                return json.loads(response.text, strict=False)["results"]["bindings"]
            except (requests.RequestException, ValueError, KeyError) as error:
                self._log.warning(f"Wikidata query attempt {attempt} failed: {error}")
                time.sleep(self.RETRY_WAIT_S * attempt)
        return None

    def _links(self, bindings: list[dict], pairs: TextIO) -> Iterator[str]:
        """
        Yields the link lines for the query results and writes each GeoNames
        pair to the pairs file. Results whose GNIS id is not a number are skipped.

        :param bindings: Query result bindings.
        :param pairs: Open text file the "feature_id,geonameid" lines are written to.
        :return: Iterator of N-Triples lines.
        """
        for binding in bindings:
            gnis_id = binding["gnisId"]["value"].strip()
            if not gnis_id.isdigit():
                continue
            feature = self.feature_iri(gnis_id)

            yield f"{feature} {self.OWL_SAMEAS} <{binding['item']['value']}> ."
            if "article" in binding:
                title = binding["article"]["value"].rsplit("/wiki/", 1)[-1]
                yield f"{feature} {self.OWL_SAMEAS} <http://dbpedia.org/resource/{title}> ."
            if self._numeric(binding, "geonamesId"):
                feature_id = FeatureIds.normalize(gnis_id)
                pairs.write(f"{feature_id},{binding['geonamesId']['value']}\n")
            if self._numeric(binding, "wofId"):
                wof_id = binding["wofId"]["value"]
                yield f"{feature} {self.OWL_SAMEAS} <https://whosonfirst.org/id/{wof_id}/> ."
            if "locId" in binding:
                loc_uri = self._loc_authority_uri(binding["locId"]["value"])
                yield f"{feature} {self.SKOS_CLOSEMATCH} <{loc_uri}> ."
            if self._numeric(binding, "tgnId"):
                tgn_id = binding["tgnId"]["value"]
                yield f"{feature} {self.SKOS_CLOSEMATCH} <http://vocab.getty.edu/tgn/{tgn_id}> ."

    @staticmethod
    def _numeric(binding: dict, variable: str) -> bool:
        """
        Checks whether a query result has a numeric value for a variable.

        :param binding: One query result binding.
        :param variable: Variable name, e.g. "wofId".
        :return: True when the variable is bound to a string of digits.
        """
        return variable in binding and binding[variable]["value"].isdigit()

    @staticmethod
    def _loc_authority_uri(loc_id: str) -> str:
        """
        Builds the id.loc.gov URI of a Library of Congress authority.

        :param loc_id: P244 value. Ids starting with "sh" are subject headings;
            all others are name authorities.
        :return: The authority URI.
        """
        namespace = "subjects" if loc_id.startswith("sh") else "names"
        return f"http://id.loc.gov/authorities/{namespace}/{loc_id}"

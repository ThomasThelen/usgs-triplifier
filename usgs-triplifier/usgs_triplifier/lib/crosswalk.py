import gzip
import json
import logging
import time
from pathlib import Path

import requests

from ..config import config
from ..output_files import OutputFiles
from .gnis.identifiers import FeatureIds

QUERY = """SELECT ?item ?gnisId ?article ?geonamesId ?wofId ?locId ?tgnId WHERE {
  ?item wdt:P590 ?gnisId .
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
  OPTIONAL { ?item wdt:P1566 ?geonamesId . }
  OPTIONAL { ?item wdt:P6766 ?wofId . }
  OPTIONAL { ?item wdt:P244 ?locId . }
  OPTIONAL { ?item wdt:P1667 ?tgnId . }
}"""

OWL_SAMEAS = "<http://www.w3.org/2002/07/owl#sameAs>"
SKOS_CLOSEMATCH = "<http://www.w3.org/2004/02/skos/core#closeMatch>"

logger = logging.getLogger(__name__)


def build_crosswalk() -> Path | None:
    """
    Write the gzipped N-Triples crosswalk to the output directory.

    :return: Path of the written file, or None when the harvest failed.
    """
    bindings = None
    for attempt in range(3):
        try:
            response = requests.post(
                config.wikidata_endpoint,
                data={"query": QUERY},
                headers={
                    "Accept": "application/sparql-results+json",
                    "User-Agent": "usgs-triplifier (support@dataone.org)",
                },
                timeout=300,
            )
            response.raise_for_status()
            # strict=False: labels occasionally carry control characters
            bindings = json.loads(response.text, strict=False)["results"]["bindings"]
            break
        except (requests.RequestException, ValueError, KeyError) as error:
            logger.warning(f"Wikidata harvest attempt {attempt + 1} failed: {error}")
            time.sleep(15 * (attempt + 1))
    if bindings is None:
        logger.warning("Wikidata crosswalk harvest failed, skipping")
        return None

    output_path = config.output_directory / OutputFiles.WIKIDATA_CROSSWALK
    reference_path = config.output_directory / OutputFiles.WIKIDATA_GEONAMES_PAIRS
    n_links = 0
    n_reference = 0
    with (
        gzip.open(output_path, "wt", encoding="utf-8") as out,
        open(reference_path, "w", encoding="utf-8") as ref,
    ):
        for binding in bindings:
            gnis_id = binding["gnisId"]["value"].strip()
            if not gnis_id.isdigit():
                continue
            feature_id = FeatureIds.normalize(gnis_id)
            feature = f"<{config.lod_base}/gnis/feature/{feature_id}>"

            lines = [f"{feature} {OWL_SAMEAS} <{binding['item']['value']}> ."]
            if "article" in binding:
                title = binding["article"]["value"].rsplit("/wiki/", 1)[-1]
                lines.append(
                    f"{feature} {OWL_SAMEAS} <http://dbpedia.org/resource/{title}> ."
                )
            if "geonamesId" in binding and binding["geonamesId"]["value"].isdigit():
                ref.write(f"{feature_id},{binding['geonamesId']['value']}\n")
                n_reference += 1
            if "wofId" in binding and binding["wofId"]["value"].isdigit():
                lines.append(
                    f"{feature} {OWL_SAMEAS} "
                    f"<https://whosonfirst.org/id/{binding['wofId']['value']}/> ."
                )
            if "locId" in binding:
                loc_uri = _loc_authority_uri(binding["locId"]["value"])
                lines.append(f"{feature} {SKOS_CLOSEMATCH} <{loc_uri}> .")
            if "tgnId" in binding and binding["tgnId"]["value"].isdigit():
                lines.append(
                    f"{feature} {SKOS_CLOSEMATCH} "
                    f"<http://vocab.getty.edu/tgn/{binding['tgnId']['value']}> ."
                )

            out.write("\n".join(lines) + "\n")
            n_links += len(lines)

    logger.info(f"Wrote {n_links} crosswalk links to {output_path.name}")
    logger.info(
        f"Wrote {n_reference} curated GeoNames pairs to "
        f"{reference_path.name} (QA reference only)"
    )
    return output_path


def _loc_authority_uri(loc_id: str) -> str:
    """Library of Congress authority URI for a P244 identifier."""
    namespace = "subjects" if loc_id.startswith("sh") else "names"
    return f"http://id.loc.gov/authorities/{namespace}/{loc_id}"

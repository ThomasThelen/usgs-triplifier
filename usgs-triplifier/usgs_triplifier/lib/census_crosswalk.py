"""
Census GEOID crosswalk from the Census Bureau's national gazetteer files.

Since 2008 the Census "ANSI code" for places and counties has been the GNIS
Feature ID, so GEOID <-> GNIS is an exact key join over two small files - no
heuristics. GEOIDs are the join key for effectively all U.S. statistical
data; carrying them makes every GNIS place and county directly joinable
against Census products.

Emits, per matched feature:

    gnisf:<id> gnis:censusGeoid "<GEOID>" .
    gnisf:<id> owl:sameAs <https://datacommons.org/browser/geoId/<GEOID>> .

The second line is the same key wearing its Data Commons address: Google's
statistical knowledge graph identifies U.S. places by geoId/<FIPS>, so the
GEOID join doubles as a Data Commons crosswalk for free.

Best-effort like the other crosswalks: unreachable gazetteer files skip the
step rather than failing the build.
"""

import gzip
import io
import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests

from ..config import config
from .crosswalk import OWL_SAMEAS
from .gnis.triplifier import normalize_feature_id

CENSUS_CROSSWALK_BASENAME = "census-crosswalk.nt.gz"

GAZETTEER_FILES = ["Gaz_counties_national.zip", "Gaz_place_national.zip"]

logger = logging.getLogger(__name__)


def build_census_crosswalk() -> Path | None:
    """
    Write the gzipped N-Triples Census crosswalk to the output directory.

    :return: Path of the written file, or None when the gazetteer files were
        unavailable.
    """
    frames = []
    for basename in GAZETTEER_FILES:
        year = config.census_gazetteer_year
        url = f"{config.census_gazetteer_base}/{year}_Gazetteer/{year}_{basename}"
        try:
            response = requests.get(url, timeout=300)
            response.raise_for_status()
            frames.append(_read_gazetteer(response.content))
        except (requests.RequestException, zipfile.BadZipFile, KeyError) as error:
            logger.warning(f"Census gazetteer unavailable ({url}), skipping: {error}")
            return None

    gazetteer = pd.concat(frames, ignore_index=True)
    geoid_property = f"<{config.lod_base}/gnis/ontology/censusGeoid>"

    output_path = config.output_directory / CENSUS_CROSSWALK_BASENAME
    n_links = 0
    with gzip.open(output_path, "wt", encoding="utf-8") as out:
        for row in gazetteer.itertuples():
            ansi = str(row.ANSICODE).strip()
            geoid = str(row.GEOID).strip()
            if not ansi.isdigit() or not geoid:
                continue
            feature = f"<{config.lod_base}/gnis/feature/{normalize_feature_id(ansi)}>"
            out.write(f'{feature} {geoid_property} "{geoid}" .\n')
            out.write(
                f"{feature} {OWL_SAMEAS} "
                f"<https://datacommons.org/browser/geoId/{geoid}> .\n"
            )
            n_links += 2

    logger.info(f"Wrote {n_links} Census GEOID links to {output_path.name}")
    return output_path


def _read_gazetteer(zip_bytes: bytes) -> pd.DataFrame:
    """GEOID and ANSICODE columns of a zipped national gazetteer file."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
        raw = zf.read(txt_names[0])
    # the delimiter changed between vintages: tab through 2024, pipe from 2025
    header = raw.split(b"\n", 1)[0]
    sep = "|" if b"|" in header else "\t"
    frame = pd.read_csv(
        io.BytesIO(raw), sep=sep, dtype=str, encoding="latin-1", quoting=3
    )
    # so does header whitespace
    frame.columns = [c.strip() for c in frame.columns]
    return frame[["GEOID", "ANSICODE"]].dropna()

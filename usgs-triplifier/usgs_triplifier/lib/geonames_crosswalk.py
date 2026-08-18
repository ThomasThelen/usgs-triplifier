"""
GeoNames crosswalk by name-and-distance alignment.

Every GeoNames link in GNIS-LD comes from this module: the crosswalk never
depends on another project's link set. The method, descended from the
original Node/PostGIS aligner: block on a normalized (name, state) match —
using the full name sets of BOTH gazetteers (GNIS variant names and
GeoNames alternate names) — then accept the nearest candidate within a
distance threshold, subject to guardrails that keep a heuristic out of
trouble in an owl:sameAs relation:

- Feature classes must be compatible (a stream never matches the town
  named after it).
- Point-like classes get a tighter distance threshold than extended
  features like streams and ridges.
- The winner must be unambiguous: a runner-up candidate at a similar
  distance means abstain, not guess.
- Matches are one-to-one: a GeoNames record links to at most one GNIS
  feature (two features sharing a GeoNames link would owl:sameAs-merge).
- Contention is decided by evidence, not luck: when several features
  claim one GeoNames record (or one feature has several candidates), the
  pair sharing the most names wins before distance breaks ties — the
  record for a mountain carries the mountain's whole name history, and
  only the right feature shares most of it.

QA comes at the end rather than the start: Wikidata's curated GNIS/GeoNames
pairs (written by the harvest as a reference file, never as triples) are an
independent set of human judgments over the same two gazetteers, and every
run scores its output against them, logs the agreement, and writes the
disagreements to a report for inspection.

Emits, per aligned feature:

    gnisf:<id> owl:sameAs <http://sws.geonames.org/<geonameid>/> .

Like the Wikidata harvest, this is best-effort: if the GeoNames dump can't
be fetched, the alignment is skipped rather than failing the build.
"""

import gzip
import logging
import re
import tempfile
import unicodedata
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import requests

from ..config import config
from .crosswalk import GEONAMES_REFERENCE_BASENAME, OWL_SAMEAS
from .gnis.triplifier import get_gpkg_zip_files, normalize_feature_id

GEONAMES_CROSSWALK_BASENAME = "geonames-crosswalk.nt.gz"
US_DUMP_BASENAME = "US.zip"

# Where the QA step records the matches that disagree with the curated
# Wikidata pairs. Not exported or loaded; a worklist for inspection.
QA_REPORT_BASENAME = "geonames-qa-disagreements.csv"

# GNIS carries full state names; the GeoNames admin1 code is the USPS
# abbreviation
STATE_ABBREVIATIONS = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "Puerto Rico": "PR",
    "Guam": "GU",
    "American Samoa": "AS",
    "Virgin Islands": "VI",
    "United States Virgin Islands": "VI",
    "Northern Mariana Islands": "MP",
    "Commonwealth of the Northern Mariana Islands": "MP",
}

# Word-level expansions applied during name normalization. Both gazetteers
# abbreviate inconsistently ("St. Marys River" vs "Saint Marys River").
NAME_ABBREVIATIONS = {
    "st": "saint",
    "ste": "sainte",
    "mt": "mount",
    "mtn": "mountain",
    "ft": "fort",
}

# GNIS feature class (spaces removed) -> GeoNames feature class letters a
# candidate may carry. Same-named neighbors of different kinds — a town and
# the creek it is named after — are the largest false-positive family, so
# incompatible pairs are rejected outright. Classes absent from this map are
# not gated.
CLASS_COMPATIBILITY = {
    # hydrography -> H
    "Arroyo": "H",
    "Bay": "H",
    "Bend": "H",
    "Canal": "H",
    "Channel": "H",
    "Falls": "H",
    "Glacier": "H",
    "Gut": "H",
    "Harbor": "H",
    "Lake": "H",
    "Rapids": "H",
    "Reservoir": "H",
    "Sea": "H",
    "Spring": "H",
    "Stream": "H",
    "Swamp": "H",
    "Well": "H",
    # hypsography / terrain -> T
    "Arch": "T",
    "Bar": "T",
    "Basin": "T",
    "Beach": "T",
    "Bench": "T",
    "Cape": "T",
    "Cliff": "T",
    "Crater": "T",
    "Flat": "T",
    "Gap": "T",
    "Island": "T",
    "Isthmus": "T",
    "Lava": "T",
    "Levee": "T",
    "Pillar": "T",
    "Plain": "T",
    "Range": "T",
    "Ridge": "T",
    "Rock": "T",
    "Slope": "T",
    "Summit": "T",
    "Valley": "T",
    # settlements and administration
    "PopulatedPlace": "P",
    "Census": "AL",
    "Civil": "A",
    "Military": "LS",
    # vegetation and land areas
    "Area": "L",
    "Forest": "VL",
    "Oilfield": "L",
    "Park": "L",
    "Reserve": "L",
    "Woods": "V",
    # spot features (mostly retired classes, present in archived vintages)
    "Airport": "S",
    "Bridge": "S",
    "Building": "S",
    "Cemetery": "S",
    "Church": "S",
    "Crossing": "RS",
    "Dam": "SH",
    "Hospital": "S",
    "Locale": "LS",
    "Mine": "S",
    "PostOffice": "S",
    "School": "S",
    "Tower": "S",
    "Trail": "R",
    "Tunnel": "RS",
}

# Point-like classes: both gazetteers place these as a single point, so
# same-feature coordinate disagreement is small and a tighter threshold
# cuts false positives. Extended features (streams, ridges, valleys) keep
# the configured default.
POINT_CLASSES = frozenset(
    {
        "PopulatedPlace",
        "Spring",
        "Well",
        "Airport",
        "Bridge",
        "Building",
        "Cemetery",
        "Church",
        "Crossing",
        "Dam",
        "Hospital",
        "Mine",
        "PostOffice",
        "School",
        "Tower",
    }
)

logger = logging.getLogger(__name__)


def build_geonames_crosswalk() -> Path | None:
    """
    Write the gzipped N-Triples GeoNames crosswalk to the output directory.

    :return: Path of the written file, or None when the dump was unavailable.
    """
    dump_path = _fetch_dump()
    if dump_path is None:
        return None

    gnis = _load_gnis()
    gnis["feature_id"] = gnis["feature_id"].map(normalize_feature_id)
    gnis["class_key"] = gnis["feature_class"].fillna("").str.replace(" ", "")
    gnis["key"] = _normalize_names(gnis["name"])
    gnis_keys = _with_variant_names(gnis)

    geonames = _explode_names(_load_geonames(dump_path))

    pairs = gnis_keys.merge(
        geonames, on=["key", "state"], suffixes=("_gnis", "_geonames")
    )
    pairs = pairs[_compatible(pairs["class_key"], pairs["gn_class"])]
    pairs["distance"] = _haversine_m(
        pairs["lat_gnis"],
        pairs["lon_gnis"],
        pairs["lat_geonames"],
        pairs["lon_geonames"],
    )
    pairs = pairs[pairs["distance"] <= _max_distance(pairs["class_key"])]

    # collapse per-key rows into one row per (feature, record); the number
    # of names the two records share is the strongest matching evidence
    pairs = pairs.groupby(["feature_id", "geonameid"], as_index=False).agg(
        distance=("distance", "min"), shared=("key", "size")
    )

    matches = _resolve(pairs)

    output_path = config.output_directory / GEONAMES_CROSSWALK_BASENAME
    n_links = 0
    with gzip.open(output_path, "wt", encoding="utf-8") as out:
        for row in matches.itertuples():
            feature = f"{config.lod_base}/gnis/feature/{row.feature_id}"
            out.write(
                f"<{feature}> {OWL_SAMEAS} "
                f"<http://sws.geonames.org/{row.geonameid}/> .\n"
            )
            n_links += 1
    logger.info(f"Wrote {n_links} GeoNames links to {output_path.name}")

    _qa_against_reference(matches)
    return output_path


def _with_variant_names(gnis: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (feature, normalized name): the official name plus every
    GNIS variant name, so both gazetteers contribute their full name sets.

    Variant names come from the AllNames dataset when it is present in the
    input directory (it always is in the ETL); without it the official
    names still align, with a note in the log.
    """
    frames = []
    for zip_path in sorted(config.input_directory.glob("AllNames*.zip")):
        with zipfile.ZipFile(zip_path, "r") as zf:
            txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
            for txt_name in txt_names:
                with zf.open(txt_name) as f:
                    frame = pd.read_csv(
                        f,
                        sep="|",
                        dtype=str,
                        encoding="utf-8-sig",
                        quoting=3,
                        usecols=lambda c: (
                            c.strip().lower() in ("feature_id", "feature_name")
                        ),
                    )
                frame.columns = [c.strip().lower() for c in frame.columns]
                frames.append(frame)
    if not frames:
        logger.info("No AllNames dataset staged; aligning on official names only")
        return gnis
    variants = pd.concat(frames, ignore_index=True).dropna()
    variants["feature_id"] = variants["feature_id"].map(normalize_feature_id)
    variants["key"] = _normalize_names(variants["feature_name"])
    extra = variants[["feature_id", "key"]].merge(
        gnis.drop(columns=["key"]), on="feature_id"
    )
    combined = pd.concat([gnis, extra], ignore_index=True)
    return combined.drop_duplicates(["feature_id", "key"])


def _normalize_names(names: pd.Series) -> pd.Series:
    """Blocking key: casefolded, unaccented, abbreviation-expanded names."""
    unique = names.dropna().unique()
    mapping = {n: _normalize_name(n) for n in unique}
    return names.map(mapping)


def _normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(name))
    flat = "".join(c for c in decomposed if not unicodedata.combining(c))
    flat = flat.lower().replace("'", "").replace(".", "")
    words = [w for w in re.split(r"[\s\-]+", flat) if w]
    return " ".join(NAME_ABBREVIATIONS.get(w, w) for w in words)


def _explode_names(geonames: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (normalized name, record): the primary name plus every
    alternate name, so a match isn't lost when the two gazetteers prefer
    different names for the same place.
    """
    primary = geonames.drop(columns=["alternatenames"]).assign(
        key=_normalize_names(geonames["name"])
    )
    alternates = geonames.dropna(subset=["alternatenames"]).copy()
    alternates["key"] = alternates.pop("alternatenames").str.split(",")
    alternates = alternates.explode("key")
    alternates = alternates[alternates["key"].str.len() > 0]
    alternates["key"] = _normalize_names(alternates["key"])
    exploded = pd.concat([primary, alternates.drop(columns=["name"])])
    return exploded.drop_duplicates(["geonameid", "key"])


def _compatible(class_key: pd.Series, gn_class: pd.Series) -> pd.Series:
    """Class gate: reject candidates whose kinds can't be the same feature."""
    allowed = class_key.map(CLASS_COMPATIBILITY)
    # unmapped GNIS classes (or missing GeoNames class) are not gated
    ungated = allowed.isna() | gn_class.isna()
    hits = pd.Series(
        [
            g in a if isinstance(a, str) and isinstance(g, str) else False
            for a, g in zip(allowed, gn_class)
        ],
        index=class_key.index,
    )
    return ungated | hits


def _max_distance(class_key: pd.Series) -> pd.Series:
    """Per-class acceptance threshold in metres."""
    return pd.Series(
        np.where(
            class_key.isin(POINT_CLASSES),
            config.geonames_point_max_distance_m,
            config.geonames_max_distance_m,
        ),
        index=class_key.index,
    )


def _resolve(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    Pick at most one candidate per feature — and one feature per candidate.

    Candidates are ranked by evidence first — the pair sharing the most
    names wins — with distance breaking ties. The winner must also be
    unambiguous: unless it out-shares the runner-up, the runner-up must be
    either ``geonames_ambiguity_ratio`` times farther or
    ``geonames_ambiguity_min_gap_m`` metres behind, otherwise the feature
    is left unlinked. Matches are then made one-to-one by keeping only
    pairs where the feature is also its GeoNames record's best claimant
    under the same ranking: two features sharing one GeoNames link would
    owl:sameAs-merge them.
    """
    pairs = pairs.sort_values(
        ["shared", "distance"], ascending=[False, True], kind="stable"
    )

    best = pairs.drop_duplicates("feature_id", keep="first")
    runners = pairs[~pairs.index.isin(best.index)].drop_duplicates(
        "feature_id", keep="first"
    )
    second_distance = best["feature_id"].map(
        runners.set_index("feature_id")["distance"]
    )
    second_shared = best["feature_id"].map(runners.set_index("feature_id")["shared"])
    unambiguous = (
        second_distance.isna()
        | (best["shared"] > second_shared)
        | (second_distance >= config.geonames_ambiguity_ratio * best["distance"])
        | (second_distance - best["distance"] >= config.geonames_ambiguity_min_gap_m)
    )
    best = best[unambiguous]

    # one-to-one: the feature must also be this record's best claimant
    gn_best = pairs.drop_duplicates("geonameid", keep="first")
    return best[best.index.isin(gn_best.index)]


def _reference_links() -> dict[str, set[str]]:
    """Curated GeoNames ids per feature id, from the harvest's QA reference."""
    reference_path = config.output_directory / GEONAMES_REFERENCE_BASENAME
    if not reference_path.exists():
        return {}
    reference: dict[str, set[str]] = {}
    with open(reference_path, encoding="utf-8") as f:
        for line in f:
            feature_id, _, geonameid = line.strip().partition(",")
            if feature_id and geonameid:
                reference.setdefault(feature_id, set()).add(geonameid)
    return reference


def _qa_against_reference(matches: pd.DataFrame) -> None:
    """
    QA: score the generated links against the curated Wikidata pairs.

    The reference pairs are independent human judgments over the same two
    gazetteers — the best available estimate of the alignment's precision.
    Agreement is logged, and the disagreeing matches are written to a
    report file as a worklist for inspection.
    """
    reference = _reference_links()
    if not reference:
        return
    overlap = matches[matches["feature_id"].isin(reference.keys())]
    if not len(overlap):
        return
    disagreements = [
        row
        for row in overlap.itertuples()
        if str(row.geonameid) not in reference[row.feature_id]
    ]
    agree = len(overlap) - len(disagreements)
    logger.info(
        f"QA: alignment agrees with the curated Wikidata pairs on {agree} of "
        f"{len(overlap)} features ({100 * agree / len(overlap):.1f}%)"
    )
    report_path = config.output_directory / QA_REPORT_BASENAME
    with open(report_path, "w", encoding="utf-8") as out:
        out.write("feature_id,aligned_geonameid,curated_geonameids\n")
        for row in disagreements:
            out.write(
                f"{row.feature_id},{row.geonameid},"
                f"{';'.join(sorted(reference[row.feature_id]))}\n"
            )
    logger.info(f"QA: wrote {len(disagreements)} disagreements to {report_path.name}")


def _fetch_dump() -> Path | None:
    """The GeoNames US dump, downloaded to the input directory when absent."""
    dump_path = config.input_directory / US_DUMP_BASENAME
    if dump_path.exists():
        return dump_path
    try:
        response = requests.get(config.geonames_url, stream=True, timeout=300)
        response.raise_for_status()
        config.input_directory.mkdir(parents=True, exist_ok=True)
        with open(dump_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    except requests.RequestException as error:
        logger.warning(f"GeoNames dump unavailable, skipping alignment: {error}")
        return None
    return dump_path


def _load_gnis() -> pd.DataFrame:
    """Feature id, name, class, state code, and coordinates from the inputs."""
    if config.archive_mode:
        return _load_gnis_archive()
    frames = []
    for zip_path in get_gpkg_zip_files():
        with zipfile.ZipFile(zip_path, "r") as zf:
            gpkg_files = [f for f in zf.namelist() if f.endswith(".gpkg")]
            with tempfile.TemporaryDirectory() as tmpdir:
                for gpkg_file in gpkg_files:
                    zf.extract(gpkg_file, tmpdir)
                    frames.append(
                        pyogrio.read_dataframe(
                            Path(tmpdir) / gpkg_file,
                            layer="DomesticNames",
                            columns=[
                                "feature_id",
                                "feature_name",
                                "feature_class",
                                "state_name",
                                "prim_lat_dec",
                                "prim_long_dec",
                            ],
                            read_geometry=False,
                        )
                    )
    gnis = pd.concat(frames, ignore_index=True).rename(
        columns={
            "feature_name": "name",
            "prim_lat_dec": "lat",
            "prim_long_dec": "lon",
        }
    )
    gnis["state"] = gnis["state_name"].map(STATE_ABBREVIATIONS)
    gnis = gnis.dropna(subset=["name", "state", "lat", "lon"])
    return gnis[gnis["lat"].astype(float) != 0.0]


def _load_gnis_archive() -> pd.DataFrame:
    """
    The same columns from an archived NationalFile dump (pre-GPKG vintages).

    The text vintages already carry the two-letter state code, so no
    name-to-abbreviation mapping is needed.
    """
    frames = []
    for zip_path in sorted(config.input_directory.glob("NationalFile*.zip")):
        frames.append(
            pd.read_csv(
                zip_path,
                sep="|",
                dtype=str,
                encoding="utf-8-sig",
                quoting=3,
                usecols=[
                    "FEATURE_ID",
                    "FEATURE_NAME",
                    "FEATURE_CLASS",
                    "STATE_ALPHA",
                    "PRIM_LAT_DEC",
                    "PRIM_LONG_DEC",
                ],
            )
        )
    gnis = pd.concat(frames, ignore_index=True).rename(
        columns={
            "FEATURE_ID": "feature_id",
            "FEATURE_NAME": "name",
            "FEATURE_CLASS": "feature_class",
            "STATE_ALPHA": "state",
            "PRIM_LAT_DEC": "lat",
            "PRIM_LONG_DEC": "lon",
        }
    )
    gnis = gnis.dropna(subset=["name", "state", "lat", "lon"])
    return gnis[gnis["lat"].astype(float) != 0.0]


def _load_geonames(dump_path: Path) -> pd.DataFrame:
    """id, names, coordinates, feature class, and admin1 from the US dump."""
    with zipfile.ZipFile(dump_path, "r") as zf:
        with zf.open("US.txt") as f:
            geonames = pd.read_csv(
                f,
                sep="\t",
                header=None,
                usecols=[0, 1, 3, 4, 5, 6, 10],
                names=[
                    "geonameid",
                    "name",
                    "alternatenames",
                    "lat",
                    "lon",
                    "gn_class",
                    "state",
                ],
                dtype={
                    "geonameid": "int64",
                    "name": "string",
                    "alternatenames": "string",
                    "lat": "float64",
                    "lon": "float64",
                    "gn_class": "string",
                    "state": "string",
                },
                quoting=3,
                na_filter=True,
            )
    return geonames.dropna(subset=["name", "state", "lat", "lon"])


def _haversine_m(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in metres, vectorized."""
    lat1, lon1, lat2, lon2 = (
        np.radians(np.asarray(v, dtype="float64")) for v in (lat1, lon1, lat2, lon2)
    )
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000 * np.arcsin(np.sqrt(a))

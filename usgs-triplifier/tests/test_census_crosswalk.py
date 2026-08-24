import gzip
import io
import zipfile

import requests

from usgs_triplifier.config import config
from usgs_triplifier.lib import census_crosswalk
from usgs_triplifier.lib.census_crosswalk import (
    CENSUS_CROSSWALK_BASENAME,
    build_census_crosswalk,
)

# 2025+ vintages are pipe-delimited with a GEOIDFQ column
COUNTIES = (
    "USPS|GEOID|GEOIDFQ|ANSICODE|NAME|ALAND\n"
    "AK|02068|0500000US02068|01419988|Denali Borough|32777.0\n"
)
# trailing whitespace in the header happens in real vintages
PLACES = (
    "USPS\tGEOID\tANSICODE\tNAME\tLSAD  \n"
    "IL\t1772000\t00428803\tSpringfield city\t25\n"
    "XX\t9999999\tnot-numeric\tBad Row\t25\n"
)


def _zip_bytes(txt_name, content):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(txt_name, content)
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def test_ansi_codes_join_to_geoids(data_dirs, monkeypatch):
    _, output_dir = data_dirs
    responses = {
        "counties": FakeResponse(
            _zip_bytes("2025_Gaz_counties_national.txt", COUNTIES)
        ),
        "place": FakeResponse(_zip_bytes("2025_Gaz_place_national.txt", PLACES)),
    }
    monkeypatch.setattr(
        census_crosswalk.requests,
        "get",
        lambda url, **kw: responses["counties" if "counties" in url else "place"],
    )

    path = build_census_crosswalk()

    assert path == output_dir / CENSUS_CROSSWALK_BASENAME
    with gzip.open(path, "rt", encoding="utf-8") as f:
        lines = f.read().splitlines()
    prop = f"<{config.lod_base}/gnis/ontology/censusGeoid>"
    # leading zeros: stripped from the GNIS id, preserved in the GEOID
    assert f'<{config.lod_base}/gnis/feature/1419988> {prop} "02068" .' in lines
    assert f'<{config.lod_base}/gnis/feature/428803> {prop} "1772000" .' in lines
    # the GEOID doubles as the Data Commons key
    sameas = "<http://www.w3.org/2002/07/owl#sameAs>"
    assert (
        f"<{config.lod_base}/gnis/feature/1419988> {sameas} "
        "<https://datacommons.org/browser/geoId/02068> ." in lines
    )
    assert len(lines) == 4  # the non-numeric ANSI row is skipped


def test_unreachable_gazetteer_is_not_fatal(data_dirs, monkeypatch):
    def boom(*a, **kw):
        raise requests.ConnectionError("census is down")

    monkeypatch.setattr(census_crosswalk.requests, "get", boom)
    assert build_census_crosswalk() is None

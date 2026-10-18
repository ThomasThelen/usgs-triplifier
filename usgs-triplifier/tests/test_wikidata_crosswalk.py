import gzip

import requests

from usgs_triplifier.lib import wikidata_crosswalk
from usgs_triplifier.lib.wikidata_crosswalk import WikidataCrosswalk
from usgs_triplifier.output_files import OutputFiles

WD = "http://www.wikidata.org/entity"


def _binding(
    item, gnis_id, article=None, geonames_id=None, wof_id=None, loc_id=None, tgn_id=None
):
    b = {
        "item": {"value": f"{WD}/{item}"},
        "gnisId": {"value": gnis_id},
    }
    if article:
        b["article"] = {"value": f"https://en.wikipedia.org/wiki/{article}"}
    if geonames_id:
        b["geonamesId"] = {"value": geonames_id}
    if wof_id:
        b["wofId"] = {"value": wof_id}
    if loc_id:
        b["locId"] = {"value": loc_id}
    if tgn_id:
        b["tgnId"] = {"value": tgn_id}
    return b


class FakeResponse:
    def __init__(self, bindings):
        import json as _json

        self.text = _json.dumps({"results": {"bindings": bindings}})

    def raise_for_status(self):
        pass


def test_harvest_writes_ntriples_links(data_dirs, monkeypatch, config):
    _, output_dir = data_dirs
    bindings = [
        _binding(
            "Q130018",
            "1414314",
            article="Denali",
            geonames_id="5868589",
            wof_id="102030739",
            loc_id="sh85082617",
            tgn_id="1116119",
        ),
        _binding("Q999", "0426595", loc_id="n81070921"),
        _binding("Q777", "not-a-gnis-id"),
    ]
    monkeypatch.setattr(
        wikidata_crosswalk.requests, "post", lambda *a, **kw: FakeResponse(bindings)
    )

    path = WikidataCrosswalk(config).build()

    assert path == output_dir / OutputFiles.WIKIDATA_CROSSWALK
    with gzip.open(path, "rt", encoding="utf-8") as f:
        lines = f.read().splitlines()
    feature = f"<{config.lod_base}/gnis/feature/1414314>"
    assert f"{feature} <http://www.w3.org/2002/07/owl#sameAs> <{WD}/Q130018> ." in lines
    assert (
        f"{feature} <http://www.w3.org/2002/07/owl#sameAs> <http://dbpedia.org/resource/Denali> ."
        in lines
    )
    # GeoNames ids are written to the pairs file and not as triples
    assert not any("sws.geonames.org" in line for line in lines)
    reference = (
        (output_dir / OutputFiles.WIKIDATA_GEONAMES_PAIRS).read_text().splitlines()
    )
    assert "1414314,5868589" in reference
    assert (
        f"{feature} <http://www.w3.org/2002/07/owl#sameAs> <https://whosonfirst.org/id/102030739/> ."
        in lines
    )
    assert (
        f"{feature} <http://www.w3.org/2004/02/skos/core#closeMatch> <http://vocab.getty.edu/tgn/1116119> ."
        in lines
    )
    # sh* ids are subject headings, everything else names; leading zeros are
    # normalized off the feature id
    assert (
        f"{feature} <http://www.w3.org/2004/02/skos/core#closeMatch> <http://id.loc.gov/authorities/subjects/sh85082617> ."
        in lines
    )
    assert (
        f"<{config.lod_base}/gnis/feature/426595> <http://www.w3.org/2004/02/skos/core#closeMatch> <http://id.loc.gov/authorities/names/n81070921> ."
        in lines
    )
    # malformed GNIS ids are skipped entirely
    assert not any("Q777" in line for line in lines)


def test_harvest_failure_is_not_fatal(data_dirs, monkeypatch, config):
    def boom(*a, **kw):
        raise requests.ConnectionError("no route to wikidata")

    monkeypatch.setattr(wikidata_crosswalk.requests, "post", boom)
    monkeypatch.setattr(wikidata_crosswalk.time, "sleep", lambda *_: None)
    assert WikidataCrosswalk(config).build() is None
    assert not (config.output_directory / OutputFiles.WIKIDATA_CROSSWALK).exists()

import json
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, PROV, RDF, RDFS, VOID, XSD

from ..config import config
from ..output_files import OutputFiles
from ..usgs_products import UsgsProducts


def build_id_for(build_time: datetime) -> str:
    """
    Release identifier for a build: YYMMDD, e.g. 260811.

    Shared by the metadata and the archive exporter so a build's release URI,
    dump filename, and sidecar all agree.
    """
    return build_time.strftime("%y%m%d")


def write_dataset_metadata(
    build_time: datetime | None = None,
    archive_path: Path | None = None,
    historical_path: Path | None = None,
) -> Path:
    """
    Write a VoID/DCAT description of the current build to the output directory.

    Describes two resources: the dataset itself (stable URI) and this release
    (dated version URI), linked with dcterms:hasVersion/isVersionOf. The URIs
    match the scheme the website publishes and documents: the dataset is
    <lod_base>/gnis and releases are <lod_base>/gnis/release/<yymmdd>.

    :param build_time: Timestamp identifying the build; defaults to now (UTC).
    :param archive_path: Exported release dump (from export_release); when
        given, recorded as a distribution downloadable from the website's
        /archive route.
    :param historical_path: Exported historical companion dump (records
        retained for features dropped upstream), recorded the same way.
    :return: Path of the written metadata file.
    """
    build_time = build_time or datetime.now(timezone.utc)
    build_id = build_id_for(build_time)

    dataset_uri = URIRef(f"{config.lod_base}/gnis")
    release_uri = URIRef(f"{config.lod_base}/gnis/release/{build_id}")

    graph = Graph()
    for prefix, ns in {
        "void": VOID,
        "dcat": DCAT,
        "dcterms": DCTERMS,
        "prov": PROV,
    }.items():
        graph.bind(prefix, ns)

    graph.add((dataset_uri, RDF.type, VOID.Dataset))
    graph.add((dataset_uri, RDF.type, DCAT.Dataset))
    graph.add((dataset_uri, DCTERMS.title, Literal("USGS GNIS Linked Data", lang="en")))
    graph.add((dataset_uri, DCTERMS.hasVersion, release_uri))

    graph.add((release_uri, RDF.type, VOID.Dataset))
    graph.add((release_uri, RDF.type, DCAT.Dataset))
    graph.add((release_uri, DCTERMS.isVersionOf, dataset_uri))
    graph.add((release_uri, DCTERMS.identifier, Literal(build_id)))
    graph.add(
        (
            release_uri,
            DCTERMS.created,
            Literal(build_time.isoformat(), datatype=XSD.dateTime),
        )
    )
    # dct:issued (a plain date) is what lineage queries key on; every
    # release record carries it, current and archived alike
    graph.add(
        (
            release_uri,
            DCTERMS.issued,
            Literal(build_time.date().isoformat(), datatype=XSD.date),
        )
    )

    # The pipeline that produced it
    activity = BNode()
    graph.add((release_uri, PROV.wasGeneratedBy, activity))
    graph.add((activity, RDF.type, PROV.Activity))
    graph.add((activity, RDFS.label, Literal(f"usgs-triplifier {_pipeline_version()}")))

    for url in UsgsProducts.source_urls(config.legacy_dump):
        graph.add((release_uri, DCTERMS.source, URIRef(url)))

    # The published release dump and its historical companion (records
    # retained for features dropped upstream), downloadable from the website
    for dump_path in (archive_path, historical_path):
        if dump_path is None:
            continue
        download_url = URIRef(f"{config.site_base}/archive/{dump_path.name}")
        graph.add((release_uri, DCAT.distribution, download_url))
        graph.add((download_url, RDF.type, DCAT.Distribution))
        graph.add((download_url, DCTERMS.title, Literal(dump_path.name)))
        graph.add((download_url, DCAT.downloadURL, download_url))
        graph.add((download_url, DCAT.mediaType, Literal("application/n-triples")))
        graph.add((download_url, DCAT.compressFormat, Literal("application/gzip")))
        graph.add(
            (
                download_url,
                DCAT.byteSize,
                Literal(dump_path.stat().st_size, datatype=XSD.integer),
            )
        )

    # Files this build produced
    for nt_path in sorted(config.output_directory.glob("*.nt.gz")):
        if nt_path.name == OutputFiles.RETAINED:
            continue
        distribution = URIRef(f"{release_uri}/{nt_path.name.replace('.nt.gz', '')}")
        graph.add((release_uri, DCAT.distribution, distribution))
        graph.add((distribution, RDF.type, DCAT.Distribution))
        graph.add((distribution, DCTERMS.title, Literal(nt_path.name)))
        graph.add(
            (
                distribution,
                DCAT.byteSize,
                Literal(nt_path.stat().st_size, datatype=XSD.integer),
            )
        )

    # Previous releases, from the archived dumps. Each load fully replaces
    # the graph, so the metadata must re-describe the whole lineage every
    # build for it to stay queryable.
    _add_archived_releases(graph, dataset_uri, skip_id=build_id)

    output_path = config.output_directory / OutputFiles.METADATA
    graph.serialize(destination=str(output_path), format="turtle")
    return output_path


def _add_archived_releases(graph: Graph, dataset_uri: URIRef, skip_id: str) -> None:
    """Add a release record for every archived dump except the current one."""
    archive_dir = config.archive_output_directory
    if not archive_dir.is_dir():
        return
    for dump_path in sorted(archive_dir.glob("*.nt.gz")):
        m_dump = OutputFiles.RELEASE.match(dump_path.name)
        if not m_dump or m_dump[1] == skip_id:
            continue
        release_id = m_dump[1]
        release_uri = URIRef(f"{config.lod_base}/gnis/release/{release_id}")

        graph.add((dataset_uri, DCTERMS.hasVersion, release_uri))
        graph.add((release_uri, RDF.type, VOID.Dataset))
        graph.add((release_uri, RDF.type, DCAT.Dataset))
        graph.add((release_uri, DCTERMS.isVersionOf, dataset_uri))
        graph.add((release_uri, DCTERMS.identifier, Literal(release_id)))
        graph.add(
            (
                release_uri,
                DCTERMS.issued,
                Literal(_published(dump_path, release_id), datatype=XSD.date),
            )
        )

        historical = dump_path.with_name(OutputFiles.historical_release(release_id))
        for dump in [dump_path, *([historical] if historical.exists() else [])]:
            download_url = URIRef(f"{config.site_base}/archive/{dump.name}")
            graph.add((release_uri, DCAT.distribution, download_url))
            graph.add((download_url, RDF.type, DCAT.Distribution))
            graph.add((download_url, DCTERMS.title, Literal(dump.name)))
            graph.add((download_url, DCAT.downloadURL, download_url))
            graph.add((download_url, DCAT.mediaType, Literal("application/n-triples")))
            graph.add((download_url, DCAT.compressFormat, Literal("application/gzip")))
            graph.add(
                (
                    download_url,
                    DCAT.byteSize,
                    Literal(dump.stat().st_size, datatype=XSD.integer),
                )
            )


def _published(dump_path: Path, release_id: str) -> str:
    """Release date: the sidecar's value, else derived from the YYMMDD id."""
    sidecar = OutputFiles.sidecar_for(dump_path)
    try:
        published = json.loads(sidecar.read_text()).get("published")
        if published:
            return published
    except OSError, ValueError:
        pass
    return f"20{release_id[0:2]}-{release_id[2:4]}-{release_id[4:6]}"


def _pipeline_version() -> str:
    """Installed package version, or 'unknown' when running from source."""
    try:
        return importlib_metadata.version("usgs-triplifier")
    except importlib_metadata.PackageNotFoundError:
        return "unknown"

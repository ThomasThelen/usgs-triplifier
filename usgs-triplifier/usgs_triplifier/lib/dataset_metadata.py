from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, PROV, RDF, RDFS, VOID, XSD

from ..config import config
from .dataset_downloader import BUCKET, GPKG_KEY, TEXT_DATASETS

S3_BASE = f"https://{BUCKET}.s3.amazonaws.com"

METADATA_BASENAME = "dataset-metadata.ttl"


def write_dataset_metadata(build_time: datetime | None = None) -> Path:
    """
    Write a VoID/DCAT description of the current build to the output directory.

    Describes two resources: the dataset itself (stable URI) and this build
    (dated version URI), linked with dcterms:hasVersion/isVersionOf per the
    versioned-record URI scheme.

    :param build_time: Timestamp identifying the build; defaults to now (UTC).
    :return: Path of the written metadata file.
    """
    build_time = build_time or datetime.now(timezone.utc)
    build_id = build_time.strftime("%Y-%m-%d")

    dataset_uri = URIRef(f"{config.lod_base}/dataset/gnis")
    build_uri = URIRef(f"{config.lod_base}/dataset/gnis/{build_id}")

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
    graph.add((dataset_uri, DCTERMS.hasVersion, build_uri))

    graph.add((build_uri, RDF.type, VOID.Dataset))
    graph.add((build_uri, RDF.type, DCAT.Dataset))
    graph.add((build_uri, DCTERMS.isVersionOf, dataset_uri))
    graph.add((build_uri, DCTERMS.identifier, Literal(build_id)))
    graph.add(
        (
            build_uri,
            DCTERMS.created,
            Literal(build_time.isoformat(), datatype=XSD.dateTime),
        )
    )

    # The pipeline that produced it
    activity = BNode()
    graph.add((build_uri, PROV.wasGeneratedBy, activity))
    graph.add((activity, RDF.type, PROV.Activity))
    graph.add((activity, RDFS.label, Literal(f"usgs-triplifier {_pipeline_version()}")))

    # Upstream sources
    for key in [GPKG_KEY, *TEXT_DATASETS]:
        graph.add((build_uri, DCTERMS.source, URIRef(f"{S3_BASE}/{key}")))

    # Files this build produced
    for ttl_path in sorted(config.output_directory.glob("*.ttl")):
        if ttl_path.name == METADATA_BASENAME:
            continue
        distribution = URIRef(f"{build_uri}/{ttl_path.stem}")
        graph.add((build_uri, DCAT.distribution, distribution))
        graph.add((distribution, RDF.type, DCAT.Distribution))
        graph.add((distribution, DCTERMS.title, Literal(ttl_path.name)))
        graph.add(
            (
                distribution,
                DCAT.byteSize,
                Literal(ttl_path.stat().st_size, datatype=XSD.integer),
            )
        )

    output_path = config.output_directory / METADATA_BASENAME
    graph.serialize(destination=str(output_path), format="turtle")
    return output_path


def _pipeline_version() -> str:
    """Installed package version, or 'unknown' when running from source."""
    try:
        return importlib_metadata.version("usgs-triplifier")
    except importlib_metadata.PackageNotFoundError:
        return "unknown"

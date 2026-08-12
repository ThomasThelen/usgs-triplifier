import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph

from ..config import config
from .dataset_metadata import METADATA_BASENAME, RETAINED_BASENAME, build_id_for


def export_release(build_time: datetime | None = None) -> Path:
    """
    Publish the build as a release dump in the archive directory.

    Concatenates every generated Turtle file into a single gzipped N-Triples
    dump named gnis-ld-<yymmdd>.nt.gz, with a <name>.meta.json sidecar
    carrying the display fields (id, published, triples, size) the website's
    archive scanner reads. Dropping these two files into the archive volume
    is the entire release-publishing handoff: the website derives its
    downloads page, release manifest, and VoID release records from them.

    The dump is a faithful conversion of the current upstream sources only;
    records retained for dropped features are published separately by
    export_historical.

    :param build_time: Timestamp identifying the build; defaults to now (UTC).
    :return: Path of the written dump.
    """
    build_time = build_time or datetime.now(timezone.utc)
    build_id = build_id_for(build_time)

    archive_dir = config.archive_output_directory
    archive_dir.mkdir(parents=True, exist_ok=True)
    dump_path = archive_dir / f"gnis-ld-{build_id}.nt.gz"

    n_triples = 0
    with gzip.open(dump_path, "wt", encoding="utf-8") as out:
        # One file at a time keeps peak memory at a single dataset's graph,
        # the same bound as the triplify step itself.
        for ttl_path in sorted(config.output_directory.glob("*.ttl")):
            if ttl_path.name in (METADATA_BASENAME, RETAINED_BASENAME):
                continue
            graph = Graph()
            graph.parse(ttl_path, format="turtle")
            out.write(graph.serialize(format="nt"))
            n_triples += len(graph)

    _write_sidecar(dump_path, build_time, n_triples)
    return dump_path


def export_historical(build_time: datetime | None = None) -> Path:
    """
    Publish the retained records as this release's historical companion dump.

    Copies retained-features.ttl (already N-Triples lines, written by
    retention.build_retained) into the archive as
    gnis-ld-historical-<yymmdd>.nt.gz with the same sidecar contract as the
    main dump, so the website can pair the two by their shared YYMMDD id.

    :param build_time: Timestamp identifying the build; defaults to now (UTC).
    :return: Path of the written dump.
    """
    build_time = build_time or datetime.now(timezone.utc)
    build_id = build_id_for(build_time)

    archive_dir = config.archive_output_directory
    archive_dir.mkdir(parents=True, exist_ok=True)
    dump_path = archive_dir / f"gnis-ld-historical-{build_id}.nt.gz"

    retained_path = config.output_directory / RETAINED_BASENAME
    n_triples = 0
    with open(retained_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n_triples += 1
    with (
        open(retained_path, "rb") as f_in,
        gzip.open(dump_path, "wb") as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)

    _write_sidecar(dump_path, build_time, n_triples)
    return dump_path


def _write_sidecar(dump_path: Path, build_time: datetime, n_triples: int) -> None:
    """Write the .meta.json display fields the website's scanner reads."""
    sidecar = {
        "id": build_id_for(build_time),
        "published": build_time.date().isoformat(),
        "triples": f"{n_triples:,}",
        "size": _format_size(dump_path.stat().st_size),
    }
    sidecar_path = dump_path.parent / (dump_path.name.replace(".nt.gz", ".meta.json"))
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n")


def _format_size(n_bytes: int) -> str:
    """Human-readable size, matching the website's own formatting."""
    if n_bytes >= 1e9:
        return f"{n_bytes / 1e9:.1f} GB"
    if n_bytes >= 1e6:
        return f"{n_bytes / 1e6:.1f} MB"
    return f"{max(1, round(n_bytes / 1e3))} KB"

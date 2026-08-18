import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..config import config
from .dataset_metadata import RETAINED_BASENAME, build_id_for


def export_release(build_time: datetime | None = None) -> Path:
    """
    Publish the build as a release dump in the archive directory.

    Concatenates the generated N-Triples files into a single gzipped dump
    named gnis-ld-<yymmdd>.nt.gz, with a <name>.meta.json sidecar
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
        # The generated files are already deduplicated N-Triples, so the
        # export is a pure streaming concatenation.
        for nt_path in sorted(config.output_directory.glob("*.nt.gz")):
            if nt_path.name == RETAINED_BASENAME:
                continue
            with gzip.open(nt_path, "rt", encoding="utf-8") as f:
                for line in f:
                    out.write(line)
                    n_triples += 1

    _write_sidecar(dump_path, build_time, n_triples)
    return dump_path


def export_historical(build_time: datetime | None = None) -> Path:
    """
    Publish the retained records as this release's historical companion dump.

    Copies the retained-features dump (written by retention.build_retained)
    into the archive as gnis-ld-historical-<yymmdd>.nt.gz with the same
    sidecar contract as the main dump, so the website can pair the two by
    their shared YYMMDD id.

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
    with gzip.open(retained_path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n_triples += 1
    shutil.copyfile(retained_path, dump_path)

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

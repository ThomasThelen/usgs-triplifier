"""
Remove exact duplicate triples from the generated dumps.

The triplifiers stream their output (an rdflib Graph would silently
deduplicate, but costs over a kilobyte of index per triple), so repeated
source rows or overlapping datasets can emit the same statement twice.
This pass rewrites each generated file, keeping the first occurrence of
every triple, with a single digest set shared across files so cross-file
duplicates (e.g. the same alias asserted by two datasets) are removed too.
"""

import gzip
import hashlib
import logging
import os
from pathlib import Path

from ..config import config
from .dataset_metadata import RETAINED_BASENAME

logger = logging.getLogger(__name__)


def remove_duplicate_triples() -> int:
    """
    Rewrite every generated .nt.gz in the output directory without duplicates.

    :return: Number of duplicate lines removed across all files.
    """
    seen: set[int] = set()
    n_removed = 0
    for path in sorted(config.output_directory.glob("*.nt.gz")):
        # Retained records are diffed from already-deduplicated dumps
        if path.name == RETAINED_BASENAME:
            continue
        n_removed += _dedupe_file(path, seen)
    logger.info(f"Removed {n_removed} duplicate triples")
    return n_removed


def _dedupe_file(path: Path, seen: set[int]) -> int:
    """Rewrite one dump keeping only lines not yet in ``seen``."""
    tmp_path = path.with_name(path.name + ".tmp")
    n_removed = 0
    with (
        gzip.open(path, "rt", encoding="utf-8") as f_in,
        gzip.open(tmp_path, "wt", encoding="utf-8") as f_out,
    ):
        for line in f_in:
            # 16-byte digests instead of the lines themselves: the set for a
            # full run holds tens of millions of entries
            digest = int.from_bytes(
                hashlib.blake2b(line.encode("utf-8"), digest_size=16).digest(), "big"
            )
            if digest in seen:
                n_removed += 1
                continue
            seen.add(digest)
            f_out.write(line)
    os.replace(tmp_path, path)
    return n_removed

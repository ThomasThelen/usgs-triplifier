"""
Text file triplifier for GNIS pipe-delimited text files.

Processes the AllNames_*.txt files extracted from USGS text dataset zips
to extract citations, dates, and alternative names.
"""

import csv
import gzip
import tempfile
import zipfile
from pathlib import Path

from tqdm import tqdm

from .triplifier import (
    FieldDescriptor,
    NTStreamSink,
    TriplifierConfig,
    _add_pairs,
    _add_triple,
    _resolve_iri,
)
from ...config import config


def triplify_text_files(
    triplifier_config: TriplifierConfig,
    file_pattern: str,
    output_basename: str,
    file_filter: str | None = None,
) -> NTStreamSink:
    """
    Process text files from zip archives in the input directory.

    :param triplifier_config: Configuration for field mappings.
    :param file_pattern: Glob pattern to match zip files (e.g., '*_Text.zip').
    :param output_basename: Basename for the output file.
    :param file_filter: Optional substring filter for text file names within zips.
    :return: The sink the triples were streamed through.
    """
    zip_files = sorted(config.input_directory.glob(file_pattern))

    if not zip_files:
        print(
            f"No text zip files found matching {file_pattern} in {config.input_directory}"
        )
        return NTStreamSink()

    print(f"Found {len(zip_files)} text zip files")

    output_dir = config.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_basename}.nt.gz"

    with gzip.open(output_path, "wt", encoding="utf-8") as out:
        sink = NTStreamSink(out)
        for zip_path in zip_files:
            print(f"Processing {zip_path.name}")
            _process_text_zip(zip_path, triplifier_config, sink, file_filter)

    print(f"Output written to {output_path}")
    return sink


def _process_text_zip(
    zip_path: Path,
    triplifier_config: TriplifierConfig,
    sink: NTStreamSink,
    file_filter: str | None = None,
) -> None:
    """
    Extract and process text files from a zip archive.

    :param zip_path: Path to the zip file.
    :param triplifier_config: Configuration for field mappings.
    :param sink: Streaming triple sink.
    :param file_filter: Optional substring filter for text file names.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find text files
        txt_files = [f for f in zf.namelist() if f.endswith(".txt")]

        # Apply filter if specified
        if file_filter:
            txt_files = [f for f in txt_files if file_filter in f]

        if not txt_files:
            print(f"  No matching text files found in {zip_path.name}")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            for txt_file in txt_files:
                print(f"  Extracting {txt_file}")
                zf.extract(txt_file, tmpdir)
                txt_path = Path(tmpdir) / txt_file
                _process_text_file(txt_path, triplifier_config, sink)


def _process_text_file(
    txt_path: Path,
    triplifier_config: TriplifierConfig,
    sink: NTStreamSink,
) -> None:
    """
    Process a pipe-delimited text file.

    :param txt_path: Path to the text file.
    :param triplifier_config: Configuration for field mappings.
    :param sink: Streaming triple sink.
    """
    # Count lines for progress bar
    with open(txt_path, "r", encoding="utf-8-sig") as f:
        total_lines = sum(1 for _ in f) - 1  # Subtract header

    with open(txt_path, "r", encoding="utf-8-sig") as f:
        # The files are purely pipe-delimited; QUOTE_NONE keeps embedded
        # double quotes (in names and citations) from merging fields or rows.
        reader = csv.DictReader(f, delimiter="|", quoting=csv.QUOTE_NONE)
        # Archived vintages (pre-GPKG, through 2021) use uppercase headers;
        # the field mappings are written against the modern lowercase names.
        reader.fieldnames = [name.lower() for name in (reader.fieldnames or [])]

        pbar = tqdm(
            total=total_lines,
            unit="rows",
            desc=f"Processing {txt_path.name}",
            bar_format="{l_bar}{bar:40}{r_bar}",
        )

        for row in reader:
            _process_row(row, triplifier_config, sink)
            pbar.update(1)

        pbar.close()


def _process_row(
    row: dict,
    triplifier_config: TriplifierConfig,
    sink: NTStreamSink,
) -> None:
    """
    Process a single row from the text file.

    :param row: Dictionary representing a row.
    :param triplifier_config: Configuration for field mappings.
    :param sink: Streaming triple sink.
    """
    # Get subject IRI
    subject_iri = triplifier_config.subject(row, sink)
    if not subject_iri:
        return

    subject = _resolve_iri(subject_iri)

    # Process each field
    for field_name, descriptor in triplifier_config.fields.items():
        value = row.get(field_name, "")

        # Function descriptor - returns pairs to add
        if callable(descriptor) and not isinstance(descriptor, FieldDescriptor):
            pairs = descriptor(value, row, sink)
            if pairs:
                _add_pairs(sink, subject, pairs)

        # Object descriptor
        elif isinstance(descriptor, FieldDescriptor):
            if not value:
                # Skip missing values silently for text files
                continue

            if descriptor.predicate and descriptor.object:
                predicate = _resolve_iri(descriptor.predicate)
                obj = descriptor.object(value, row, sink)

                if obj:
                    _add_triple(sink, subject, predicate, obj)

import csv
import gzip
import logging
import tempfile
import zipfile
from pathlib import Path

from tqdm import tqdm

from .triplifier import NTStreamSink, TriplifierConfig, _process_row
from ...config import config

logger = logging.getLogger(__name__)


def triplify_text_files(
    triplifier_config: TriplifierConfig,
    file_pattern: str,
    output_name: str,
    file_filter: str | None = None,
) -> NTStreamSink:
    """
    Process text files from zip archives in the input directory.

    :param triplifier_config: Configuration for field mappings.
    :param file_pattern: Glob pattern to match zip files (e.g., '*_Text.zip').
    :param output_name: Name of the gzipped N-Triples file written to the
        output directory.
    :param file_filter: Optional substring filter for text file names within zips.
    :return: The sink the triples were streamed through.
    :raises FileNotFoundError: If no zip matches the pattern.
    """
    zip_files = sorted(config.input_directory.glob(file_pattern))

    if not zip_files:
        raise FileNotFoundError(
            f"No text zip files matching {file_pattern} in {config.input_directory}"
        )

    logger.info(f"Found {len(zip_files)} text zip files")

    output_dir = config.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    with gzip.open(output_path, "wt", encoding="utf-8") as out:
        sink = NTStreamSink(out)
        for zip_path in zip_files:
            logger.info(f"Processing {zip_path.name}")
            _process_text_zip(zip_path, triplifier_config, sink, file_filter)

    logger.info(f"Output written to {output_path}")
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
            logger.warning(f"No matching text files found in {zip_path.name}")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            for txt_file in txt_files:
                logger.info(f"Extracting {txt_file}")
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
        reader = csv.DictReader(f, delimiter="|", quoting=csv.QUOTE_NONE, restval="")
        reader.fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]

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

import csv
import io
import logging
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar


class TextSource:
    """
    Reads the rows of the pipe-delimited text files inside the zips in a
    directory whose names match a pattern.

    Header names are stripped and lowercased, because legacy dumps use
    uppercase headers and the current products lowercase ones.
    """

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, directory: Path, pattern: str) -> None:
        """
        Finds the zips to read.

        :param directory: Directory holding the zips.
        :param pattern: Glob matching the zip names.
        :raises FileNotFoundError: If no zip matches the pattern.
        """
        self.zip_paths = sorted(directory.glob(pattern))
        if not self.zip_paths:
            raise FileNotFoundError(f"No zip files matching {pattern} in {directory}")

    def rows(self) -> Iterator[dict[str, str]]:
        """
        Yields every row of every .txt file in the zips, in file order.

        :return: Iterator of rows, each a mapping of lowercase column name to value.
        """
        for zip_path in self.zip_paths:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = [n for n in zf.namelist() if n.endswith(".txt")]
                if not names:
                    self._log.warning(f"No text files in {zip_path.name}")
                for name in names:
                    self._log.info(f"Reading {name} from {zip_path.name}")
                    yield from self._read(zf, name)

    def _read(self, zf: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
        """
        Yields the rows of one text file in a zip.

        :param zf: Open zip file.
        :param name: Name of the text file inside the zip.
        :return: Iterator of rows.
        """
        with (
            zf.open(name) as raw,
            io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as f,
        ):
            reader = csv.DictReader(
                f, delimiter="|", quoting=csv.QUOTE_NONE, restval=""
            )
            reader.fieldnames = [n.strip().lower() for n in reader.fieldnames or []]
            yield from reader

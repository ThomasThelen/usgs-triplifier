import gzip
import json
import shutil
from datetime import datetime
from pathlib import Path

from ..config import Config
from ..output_files import OutputFiles


class ReleaseExporter:
    """
    Writes a release's files to the archive output directory.

    Each release file comes with a gnis-ld-<yymmdd>.meta.json beside it with its
    id, publication date, triple count and size.
    """

    def __init__(self, config: Config):
        """
        Creates the exporter.

        :param config: Settings holding the output and archive output directories.
        """
        self.config = config

    def export_release(self, build_time: datetime) -> Path:
        """
        Writes the release file, gnis-ld-<yymmdd>.nt.gz.

        :param build_time: Time the release is dated with.
        :return: Path of the release file.
        """
        release_id = OutputFiles.release_id(build_time)
        path = self._archive_dir() / OutputFiles.release(release_id)

        triples = 0
        with gzip.open(path, "wt", encoding="utf-8") as out:
            # Concatenate the generated files, except retained-features.nt.gz,
            # into the release file, counting one triple per line
            for nt_path in sorted(self.config.output_directory.glob("*.nt.gz")):
                if nt_path.name == OutputFiles.RETAINED:
                    continue
                with gzip.open(nt_path, "rt", encoding="utf-8") as f:
                    for line in f:
                        out.write(line)
                        triples += 1

        self._write_sidecar(path, build_time, triples)
        return path

    def export_historical(self, build_time: datetime) -> Path:
        """
        Writes the historical release file, gnis-ld-historical-<yymmdd>.nt.gz.

        :param build_time: Time the release is dated with.
        :return: Path of the historical release file.
        :raises FileNotFoundError: If retained-features.nt.gz has not been written.
        """
        release_id = OutputFiles.release_id(build_time)
        path = self._archive_dir() / OutputFiles.historical_release(release_id)

        retained_path = self.config.output_directory / OutputFiles.RETAINED
        with gzip.open(retained_path, "rt", encoding="utf-8") as f:
            triples = sum(1 for line in f if line.strip())
        shutil.copyfile(retained_path, path)

        self._write_sidecar(path, build_time, triples)
        return path

    def _archive_dir(self) -> Path:
        """
        Returns the archive output directory, creating it if missing.

        :return: The directory.
        """
        archive_dir = self.config.archive_output_directory
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir

    def _write_sidecar(self, path: Path, build_time: datetime, triples: int) -> None:
        """
        Writes the .meta.json file the website reads for a release file.

        :param path: Release file the JSON describes.
        :param build_time: Time the release is dated with.
        :param triples: Number of triples in the release file.
        """
        sidecar = {
            "id": OutputFiles.release_id(build_time),
            "published": build_time.date().isoformat(),
            "triples": f"{triples:,}",
            "size": self.format_size(path.stat().st_size),
        }
        OutputFiles.sidecar_for(path).write_text(json.dumps(sidecar, indent=2) + "\n")

    @staticmethod
    def format_size(n_bytes: int) -> str:
        """
        Formats a file size the way the website does (format_size in
        gnis-ld.org's lib/js/server.ts): decimal units, one decimal place for
        MB and GB, at least 1 KB.

        :param n_bytes: Size in bytes.
        :return: The size, e.g. "3.5 MB".
        """
        if n_bytes >= 1e9:
            return f"{n_bytes / 1e9:.1f} GB"
        if n_bytes >= 1e6:
            return f"{n_bytes / 1e6:.1f} MB"
        return f"{max(1, round(n_bytes / 1e3))} KB"

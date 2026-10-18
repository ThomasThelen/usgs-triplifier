import logging
from pathlib import Path
from typing import ClassVar

from rdflib import Graph

from ..config import Config
from ..output_files import OutputFiles
from .gnis.rdf import NTriplesWriter


class OntologyWriter:
    """
    Writes the gnis and usgs ontologies to the output directory as gzipped
    N-Triples, so they are released and loaded with the data.
    """

    # Directory holding the vendored Turtle files
    ONTOLOGIES_DIR: ClassVar[Path] = Path(__file__).parent.parent / "ontologies"

    # Base IRI written in the Turtle files; replaced with lod_base when loaded
    SOURCE_LOD_BASE: ClassVar[str] = "http://gnis-ld.org/lod"

    # Website IRI written in the Turtle files (rdfs:seeAlso); replaced with
    # site_base when loaded
    SOURCE_SITE_BASE: ClassVar[str] = "https://gnis-ld.org"

    # Turtle file name -> output file name
    FILES: ClassVar[dict[str, str]] = {
        "gnis.ttl": OutputFiles.ONTOLOGY_GNIS,
        "usgs.ttl": OutputFiles.ONTOLOGY_USGS,
    }

    _log: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, config: Config) -> None:
        """
        Creates the writer.

        :param config: Settings holding the output directory, lod_base and
            site_base.
        """
        self.config = config

    def write(self) -> list[Path]:
        """
        Writes every ontology in FILES to the output directory, with the
        triples in sorted order so two runs produce identical files.

        :return: Paths of the written files.
        """
        paths = []
        for source_name, output_name in self.FILES.items():
            path = self.config.output_directory / output_name
            graph = self.load(source_name)
            with NTriplesWriter(path) as writer:
                for triple in sorted(graph):
                    writer.add(triple)
            self._log.info(f"Wrote {len(writer)} ontology triples to {path}")
            paths.append(path)
        return paths

    def load(self, source_name: str) -> Graph:
        """
        Parses a vendored ontology with its base IRI replaced by lod_base and
        its website IRI by site_base.

        :param source_name: File name in ONTOLOGIES_DIR, e.g. "gnis.ttl".
        :return: The ontology graph.
        """
        text = (self.ONTOLOGIES_DIR / source_name).read_text(encoding="utf-8")
        text = text.replace(self.SOURCE_LOD_BASE, self.config.lod_base)
        text = text.replace(self.SOURCE_SITE_BASE, self.config.site_base)
        return Graph().parse(data=text, format="turtle")

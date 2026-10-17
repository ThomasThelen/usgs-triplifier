import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.serializers.nt import _nt_row

from ...config import config

logger = logging.getLogger(__name__)


class NTStreamSink:
    """
    Graph-shaped triple sink that streams each triple as an N-Triples line.

    The full datasets are far too large to hold as rdflib Graphs (the
    indexes cost well over a kilobyte per triple), and each row's triples
    are independent, so they are written the moment they are produced and
    peak memory stays flat. Duplicate triples are not collapsed here; the
    ETL removes them in a dedicated pass over the finished files.
    """

    def __init__(self, out=None):
        self._out = out
        self._count = 0

    def add(self, triple) -> None:
        self._out.write(_nt_row(triple))
        self._count += 1

    def bind(self, prefix, namespace) -> None:
        """No-op: N-Triples has no prefixes."""

    def __len__(self) -> int:
        return self._count


@dataclass
class FieldDescriptor:
    """Describes how to map a field to RDF predicates/objects."""

    predicate: str
    object: Callable[[str, dict, Graph], Any] | None = None
    optional: bool = False


@dataclass
class TriplifierConfig:
    """Configuration for the triplifier."""

    subject: Callable[[dict, Graph], str | None]
    fields: dict[str, FieldDescriptor | Callable]


def normalize_feature_id(raw: Any) -> str:
    """
    Normalize a feature id to the canonical string form used in gnisf: IRIs.

    :param raw: Feature id as read from a GPKG table or text file.
    :return: Canonical feature id string.
    """
    if isinstance(raw, (int, float)):
        return str(int(raw))
    return str(raw).lstrip("0") or "0"


def clean(s: str) -> str:
    """
    Clean IRIs by replacing non-word characters with underscores.

    :param s: String to clean.
    :return: Cleaned string with non-word characters replaced by underscores.
    """
    return re.sub(r"[^\w]", "_", s)


def _process_row(
    row_dict: dict, triplifier_config: TriplifierConfig, sink: NTStreamSink
) -> None:
    """
    Emit the triples for one source row into the sink.

    :param row_dict: Source row as a mapping of column name to value.
    :param triplifier_config: Subject function and field mappings to apply.
    :param sink: Streaming triple sink the row's triples are written to.
    :raises ValueError: If a non-optional field has no value.
    """
    subject_iri = triplifier_config.subject(row_dict, sink)
    if not subject_iri:
        return

    subject = _resolve_iri(subject_iri)

    for field_name, descriptor in triplifier_config.fields.items():
        value = row_dict.get(field_name)
        value = "" if value is None else str(value)

        if callable(descriptor) and not isinstance(descriptor, FieldDescriptor):
            pairs = descriptor(value, row_dict, sink)
            if pairs:
                _add_pairs(sink, subject, pairs)
        elif isinstance(descriptor, FieldDescriptor):
            if not value:
                if descriptor.optional:
                    continue
                raise ValueError(f'Missing value for column "{field_name}"')
            if descriptor.predicate and descriptor.object:
                predicate = _resolve_iri(descriptor.predicate)
                obj = descriptor.object(value, row_dict, sink)
                if obj:
                    _add_triple(sink, subject, predicate, obj)


def _resolve_iri(iri_str: str) -> URIRef:
    """
    Resolve a prefixed IRI string to a full URIRef.

    :param iri_str: IRI string, possibly prefixed (e.g., 'gnisf:123').
    :return: Full URIRef representing the node.
    """
    if iri_str.startswith(">"):
        return URIRef(iri_str[1:])
    if ":" in iri_str:
        prefix, local = iri_str.split(":", 1)
        if prefix in config.prefix_list:
            ns = config.prefix_list[prefix]
            if hasattr(ns, "__getitem__"):
                return ns[local]
            return URIRef(str(ns) + local)
    return URIRef(iri_str)


def _add_pairs(graph: Graph, subject: URIRef, pairs: dict) -> None:
    """
    Add predicate-object pairs for a subject.

    :param graph: RDF graph to add triples to.
    :param subject: Subject node.
    :param pairs: Dictionary of predicate -> list of objects.
    """
    for predicate_str, objects in pairs.items():
        predicate = _resolve_iri(predicate_str)
        if not isinstance(objects, list):
            objects = [objects]
        for obj in objects:
            _add_triple(graph, subject, predicate, obj)


def _add_triple(graph: Graph, subject: URIRef, predicate: URIRef, obj: Any) -> None:
    """
    Add a single triple to the graph.

    Dict objects become a blank node whose predicate-object pairs are added
    recursively (e.g. an elevation node with qudt:numericValue/qudt:unit).

    :param graph: RDF graph to add the triple to.
    :param subject: Subject node.
    :param predicate: Predicate URIRef.
    :param obj: Object (string notation, URIRef, Literal, or nested dict).
    """
    if isinstance(obj, (URIRef, Literal)):
        graph.add((subject, predicate, obj))
    elif isinstance(obj, str):
        parsed_obj = _parse_object(obj)
        graph.add((subject, predicate, parsed_obj))
    elif isinstance(obj, dict):
        node = BNode()
        graph.add((subject, predicate, node))
        _add_pairs(graph, node, obj)
    else:
        logger.warning(f"Skipping unsupported object type {type(obj)!r}: {obj}")


def _parse_object(obj_str: str) -> URIRef | Literal:
    """
    Parse a graphy-style object notation.

    Notation:
        - '"value' -> plain literal
        - '@lang"value' -> language-tagged literal
        - '^datatype"value' -> typed literal
        - 'prefix:local' -> named node
        - '>uri' -> full URI

    :param obj_str: Object string in graphy notation.
    :return: Parsed URIRef or Literal.
    """
    if obj_str.startswith(">"):
        return URIRef(obj_str[1:])
    elif obj_str.startswith('"'):
        return Literal(obj_str[1:])
    elif obj_str.startswith("@"):
        lang_end = obj_str.index('"')
        lang = obj_str[1:lang_end]
        value = obj_str[lang_end + 1 :]
        return Literal(value, lang=lang)
    elif obj_str.startswith("^"):
        type_end = obj_str.index('"')
        datatype_str = obj_str[1:type_end]
        value = obj_str[type_end + 1 :]
        datatype = _resolve_iri(datatype_str)
        return Literal(value, datatype=datatype)
    elif ":" in obj_str:
        return _resolve_iri(obj_str)
    else:
        return Literal(obj_str)

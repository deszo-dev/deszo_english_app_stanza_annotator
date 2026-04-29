from typing import Any

from stanza_annotator._internal.core import (
    project_stanza_document,
    raw_document_to_dict,
)
from stanza_annotator.models import AnnotatedDocument


def document_to_annotated_document(document: Any) -> AnnotatedDocument:
    return project_stanza_document(document)


def document_to_raw_dict(document: Any) -> dict[str, Any] | None:
    return raw_document_to_dict(document)

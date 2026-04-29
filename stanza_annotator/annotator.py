from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from stanza_annotator._internal.core import (
    project_stanza_document,
    raw_document_to_dict,
)
from stanza_annotator._internal.stanza_adapter import DefaultStanzaAdapter
from stanza_annotator._internal.types import StanzaAdapter
from stanza_annotator._internal.validation import validate_prepared_text
from stanza_annotator.config import StanzaAnnotatorConfig
from stanza_annotator.debug import write_debug_file
from stanza_annotator.errors import ConfigurationError
from stanza_annotator.models import AnnotatedDocument


class StanzaAnnotator:
    def __init__(
        self,
        config: StanzaAnnotatorConfig | Mapping[str, object] | None = None,
        *,
        adapter: StanzaAdapter | None = None,
    ) -> None:
        try:
            self.config = (
                config
                if isinstance(config, StanzaAnnotatorConfig)
                else StanzaAnnotatorConfig.model_validate(config or {})
            )
        except ValidationError as exc:
            raise ConfigurationError("invalid stanza annotator configuration") from exc
        self._adapter = adapter or DefaultStanzaAdapter(self.config)

    def annotate(self, text: str) -> AnnotatedDocument:
        """Annotate prepared UTF-8 text and return a deterministic document."""
        validate_prepared_text(text)

        if not text.strip():
            document = AnnotatedDocument()
            self._write_debug_if_enabled(
                text=text,
                annotated_document=document,
                raw_document=None,
                empty_input=True,
            )
            return document

        raw_document = self._adapter.annotate(text)
        document = project_stanza_document(raw_document)
        self._write_debug_if_enabled(
            text=text,
            annotated_document=document,
            raw_document=raw_document_to_dict(raw_document),
            empty_input=False,
        )
        return document

    def _write_debug_if_enabled(
        self,
        *,
        text: str,
        annotated_document: AnnotatedDocument,
        raw_document: dict[str, Any] | None,
        empty_input: bool,
    ) -> None:
        if not self.config.debug:
            return

        gpu_decision = getattr(self._adapter, "gpu_decision", None)
        metadata = {
            "language": self.config.language,
            "processors": self.config.processors,
            "tokenize_pretokenized": self.config.tokenize_pretokenized,
            "empty_input": empty_input,
            "input_length": len(text),
            "gpu_requested": self.config.use_gpu,
            "gpu_effective": getattr(gpu_decision, "effective", False),
            "gpu_fallback_reason": getattr(gpu_decision, "fallback_reason", None),
        }
        write_debug_file(
            debug_dir=self.config.debug_dir,
            annotated_document=annotated_document,
            raw_document=raw_document,
            metadata=metadata,
        )

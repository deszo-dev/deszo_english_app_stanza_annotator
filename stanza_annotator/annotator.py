from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stanza_annotator.config import StanzaAnnotatorConfig
from stanza_annotator.converter import (
    document_to_annotated_document,
    document_to_raw_dict,
)
from stanza_annotator.debug import write_debug_file
from stanza_annotator.models import AnnotatedDocument


@dataclass(frozen=True)
class GpuDecision:
    requested: bool
    effective: bool
    fallback_reason: str | None = None


class StanzaAnnotator:
    def __init__(self, config: StanzaAnnotatorConfig | dict[str, Any] | None = None) -> None:
        self.config = (
            config
            if isinstance(config, StanzaAnnotatorConfig)
            else StanzaAnnotatorConfig.model_validate(config or {})
        )
        self._pipeline: Any | None = None
        self._gpu_decision: GpuDecision | None = None

    def annotate(self, text: str) -> AnnotatedDocument:
        if not text.strip():
            document = AnnotatedDocument()
            self._write_debug_if_enabled(
                text=text,
                annotated_document=document,
                raw_document=None,
                empty_input=True,
            )
            return document

        pipeline = self._get_pipeline()
        stanza_document = pipeline(text)
        document = document_to_annotated_document(stanza_document)
        self._write_debug_if_enabled(
            text=text,
            annotated_document=document,
            raw_document=document_to_raw_dict(stanza_document),
            empty_input=False,
        )
        return document

    @property
    def gpu_decision(self) -> GpuDecision | None:
        return self._gpu_decision

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        stanza = self._import_stanza()
        self._gpu_decision = _decide_gpu(self.config.use_gpu)

        if self.config.auto_download:
            stanza.download(
                self.config.language,
                processors=self.config.processors,
                verbose=self.config.logging.enabled,
            )

        self._pipeline = stanza.Pipeline(
            lang=self.config.language,
            processors=self.config.processors,
            use_gpu=self._gpu_decision.effective,
            tokenize_pretokenized=self.config.tokenize_pretokenized,
            verbose=self.config.logging.enabled,
        )
        return self._pipeline

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

        gpu_decision = self._gpu_decision or _decide_gpu(self.config.use_gpu)
        metadata = {
            "language": self.config.language,
            "processors": self.config.processors,
            "tokenize_pretokenized": self.config.tokenize_pretokenized,
            "empty_input": empty_input,
            "input_length": len(text),
            "gpu_requested": gpu_decision.requested,
            "gpu_effective": gpu_decision.effective,
            "gpu_fallback_reason": gpu_decision.fallback_reason,
        }
        write_debug_file(
            debug_dir=self.config.debug_dir,
            annotated_document=annotated_document,
            raw_document=raw_document,
            metadata=metadata,
        )

    @staticmethod
    def _import_stanza() -> Any:
        try:
            import stanza
        except ImportError as exc:
            raise RuntimeError(
                "stanza is not installed. Install the package with `pip install stanza-annotator`."
            ) from exc
        return stanza


def _decide_gpu(requested: bool) -> GpuDecision:
    if not requested:
        return GpuDecision(requested=False, effective=False)

    try:
        import torch
    except ImportError:
        return GpuDecision(
            requested=True,
            effective=False,
            fallback_reason="torch is not installed",
        )

    try:
        if torch.cuda.is_available():
            return GpuDecision(requested=True, effective=True)
    except Exception as exc:
        return GpuDecision(
            requested=True,
            effective=False,
            fallback_reason=f"CUDA availability check failed: {exc}",
        )

    return GpuDecision(
        requested=True,
        effective=False,
        fallback_reason="CUDA is not available",
    )

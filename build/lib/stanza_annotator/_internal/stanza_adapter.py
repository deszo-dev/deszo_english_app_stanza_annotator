from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stanza_annotator.config import StanzaAnnotatorConfig
from stanza_annotator.errors import StanzaRuntimeError


@dataclass(frozen=True)
class GpuDecision:
    requested: bool
    effective: bool
    fallback_reason: str | None = None


class DefaultStanzaAdapter:
    def __init__(self, config: StanzaAnnotatorConfig) -> None:
        self._config = config
        self._pipeline: Any | None = None
        self._gpu_decision: GpuDecision | None = None

    @property
    def gpu_decision(self) -> GpuDecision | None:
        return self._gpu_decision

    def annotate(self, text: str) -> Any:
        try:
            return self._get_pipeline()(text)
        except StanzaRuntimeError:
            raise
        except Exception as exc:
            raise StanzaRuntimeError("Stanza annotation failed") from exc

    def _get_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        stanza = _import_stanza()
        self._gpu_decision = _decide_gpu(self._config.use_gpu)

        try:
            if self._config.auto_download:
                stanza.download(
                    self._config.language,
                    processors=self._config.processors,
                    verbose=self._config.logging.enabled,
                )

            self._pipeline = stanza.Pipeline(
                lang=self._config.language,
                processors=self._config.processors,
                use_gpu=self._gpu_decision.effective,
                tokenize_pretokenized=self._config.tokenize_pretokenized,
                verbose=self._config.logging.enabled,
            )
        except Exception as exc:
            raise StanzaRuntimeError("Stanza pipeline initialization failed") from exc

        return self._pipeline


def _import_stanza() -> Any:
    try:
        import stanza
    except ImportError as exc:
        raise StanzaRuntimeError("stanza is not installed") from exc
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

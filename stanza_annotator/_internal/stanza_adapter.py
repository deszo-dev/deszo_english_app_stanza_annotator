from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from stanza_annotator.config import StanzaAnnotatorConfig
from stanza_annotator.errors import StanzaRuntimeError
from stanza_annotator._internal.types import (
    RawStanzaDocument,
    RawStanzaEntity,
    RawStanzaSentence,
    RawStanzaToken,
    RawStanzaWord,
)


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

    def annotate_batch(self, texts: Sequence[str]) -> Sequence[RawStanzaDocument]:
        if not texts:
            return []
        try:
            pipeline = self._get_pipeline()
        except StanzaRuntimeError as exc:
            raise StanzaRuntimeError("Stanza model unavailable") from exc

        try:
            raw_documents = pipeline(list(texts))
        except ValueError as exc:
            # Some Stanza versions reject list[str] input for tokenize pipelines.
            # Keep the public batch contract, but fall back to per-text calls inside
            # the adapter when batch/list processing is unavailable.
            if "must be a string or a Document object" not in str(exc):
                raise StanzaRuntimeError("Stanza batch annotation failed") from exc
            try:
                raw_documents = [pipeline(text) for text in texts]
            except Exception as inner_exc:
                raise StanzaRuntimeError("Stanza batch annotation failed") from inner_exc
        except Exception as exc:
            raise StanzaRuntimeError("Stanza batch annotation failed") from exc

        if not isinstance(raw_documents, list):
            raw_documents = [raw_documents]
        return [self._convert_document(document) for document in raw_documents]

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

    def _convert_document(self, document: Any) -> RawStanzaDocument:
        sentences = []
        for sentence in getattr(document, "sentences", []):
            tokens = []
            for token in getattr(sentence, "tokens", []):
                words = [
                    RawStanzaWord(
                        text=str(getattr(word, "text", "")),
                        lemma=str(getattr(word, "lemma", "")),
                        upos=str(getattr(word, "upos", "")),
                        deprel=str(getattr(word, "deprel", "")),
                        head=int(getattr(word, "head", 0) or 0),
                        start_char=int(getattr(word, "start_char", 0)),
                        end_char=int(getattr(word, "end_char", 0)),
                        xpos=(
                            None
                            if getattr(word, "xpos", None) is None
                            else str(getattr(word, "xpos"))
                        ),
                        feats=(
                            None
                            if getattr(word, "feats", None) is None
                            else str(getattr(word, "feats"))
                        ),
                    )
                    for word in getattr(token, "words", [])
                ]
                tokens.append(
                    RawStanzaToken(
                        text=str(getattr(token, "text", "")),
                        start_char=int(
                            getattr(token, "start_char", words[0].start_char if words else 0)
                        ),
                        end_char=int(
                            getattr(token, "end_char", words[-1].end_char if words else 0)
                        ),
                        words=words,
                    )
                )
            sentences.append(
                RawStanzaSentence(
                    text=str(getattr(sentence, "text", "")),
                    start_char=int(getattr(sentence, "start_char", 0)),
                    end_char=int(getattr(sentence, "end_char", 0)),
                    tokens=tokens,
                )
            )

        entities = []
        for entity in getattr(document, "entities", []):
            entities.append(
                RawStanzaEntity(
                    text=str(getattr(entity, "text", "")),
                    type=str(getattr(entity, "type", getattr(entity, "ner", ""))),
                    start_char=int(getattr(entity, "start_char", 0)),
                    end_char=int(getattr(entity, "end_char", 0)),
                )
            )

        return RawStanzaDocument(sentences=sentences, entities=entities)


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

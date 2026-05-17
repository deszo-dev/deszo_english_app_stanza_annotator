from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from stanza_annotator._internal.stanza_adapter import DefaultStanzaAdapter
from stanza_annotator._internal.types import (
    RawStanzaDocument,
    RawStanzaSentence,
    RawStanzaToken,
    RawStanzaWord,
    StanzaAdapter,
)
from stanza_annotator._internal.validation import validate_prepared_text
from stanza_annotator.config import ContentSelectionConfig, StanzaAnnotatorConfig
from stanza_annotator.errors import ConfigurationError
from stanza_annotator.models import AnnotatedDocument, Entity, Sentence, Token, Word
from stanza_annotator.runtime_metadata import (
    PipelineRuntimeMetadata,
    StageRuntimeMetadata,
    canonical_json,
    get_module_version,
    pipeline_runtime_metadata,
    stanza_annotation_runtime_metadata,
)

OUTPUT_SCHEMA_VERSION = "stanza_annotator.v2.0"
SUPPORTED_UPSTREAM_SCHEMA = "epub_content_extractor.v3.0"


class StanzaAnnotator:
    def __init__(
        self,
        config: StanzaAnnotatorConfig | Mapping[str, object] | None = None,
        *,
        adapter: StanzaAdapter | None = None,
        clock: Callable[[], datetime] | None = None,
        annotator_version: str | None = None,
    ) -> None:
        try:
            self.config = (
                config
                if isinstance(config, StanzaAnnotatorConfig)
                else StanzaAnnotatorConfig.model_validate(config or {})
            )
        except ValidationError as exc:
            raise ConfigurationError("invalid stanza annotator configuration") from exc
        self._adapter = adapter
        self._clock = clock or (lambda: datetime.now(UTC))
        self._annotator_version = annotator_version or get_module_version(
            "stanza-annotator"
        )

    def annotate(self, text: str) -> AnnotatedDocument:
        validate_prepared_text(text)
        if not text.strip():
            return AnnotatedDocument()
        adapter = self._adapter or DefaultStanzaAdapter(self.config)
        raw_documents = adapter.annotate_batch([text])
        if len(raw_documents) != 1:
            raise ConfigurationError("batch adapter returned invalid document count")
        raw_document = raw_documents[0]
        return AnnotatedDocument(
            sentences=[self._legacy_sentence(sentence) for sentence in raw_document.sentences],
            entities=[self._legacy_entity(entity) for entity in raw_document.entities],
        )

    def annotate_epub_result(
        self,
        epub_result: dict,
        config: dict | None = None,
    ) -> dict[str, Any]:
        if not isinstance(config, (dict, type(None))):
            raise TypeError("config must be a mapping or None")

        started_at = self._clock()
        started_clock = perf_counter()

        try:
            effective_config, diagnostics = self._resolve_config(config)
        except ValidationError as exc:
            return self._failed_result(
                code="invalid_config",
                message="Invalid config field.",
                diagnostics=[self._config_diagnostic(exc)],
                config_snapshot=self.config.model_dump(mode="json"),
                started_at=started_at,
                duration_ms=0,
            )

        validation = self._validate_upstream_input(epub_result)
        if validation["status"] != "ok":
            return self._failed_result(
                code=validation["error_code"],
                message=validation["message"],
                diagnostics=validation["diagnostics"],
                config_snapshot=self._snapshot_config(effective_config),
                started_at=started_at,
                duration_ms=0,
            )

        try:
            result = self._annotate_validated_input(
                book=validation["book"],
                upstream_diagnostics=validation["upstream_diagnostics"],
                extraction=validation["extraction"],
                effective_config=effective_config,
                started_at=started_at,
                started_clock=started_clock,
            )
        except Exception as exc:
            runtime_diagnostic = {
                "code": "quality_warning",
                "severity": "warning",
                "message": "Internal annotation failure.",
                "entity_type": "stanza_runtime",
            }
            code = "internal_error"
            message = "Unexpected internal error."
            if isinstance(exc, RuntimeError):
                code = "stanza_runtime_failed"
                message = "Stanza runtime failed."
                runtime_diagnostic = {
                    "code": "quality_warning",
                    "severity": "warning",
                    "message": "Stanza runtime failed.",
                    "entity_type": "stanza_runtime",
                }
            return self._failed_result(
                code=code,
                message=message,
                diagnostics=[runtime_diagnostic],
                config_snapshot=self._snapshot_config(effective_config),
                started_at=started_at,
                duration_ms=max(0, int((perf_counter() - started_clock) * 1000)),
            )

        return result

    def runtime_metadata(self) -> PipelineRuntimeMetadata:
        return pipeline_runtime_metadata()

    def stage_runtime_metadata(self) -> StageRuntimeMetadata:
        return stanza_annotation_runtime_metadata()

    def _resolve_config(
        self, config: dict | None
    ) -> tuple[StanzaAnnotatorConfig, list[dict[str, Any]]]:
        if config is None:
            config = {}
        effective_config = StanzaAnnotatorConfig.model_validate(config)
        return effective_config, []

    def _validate_upstream_input(self, epub_result: object) -> dict[str, Any]:
        if not isinstance(epub_result, Mapping):
            return self._invalid_input("Input is not a supported EPUB extraction result.")

        if epub_result.get("schema_version") != SUPPORTED_UPSTREAM_SCHEMA:
            return {
                "status": "failed",
                "error_code": "unsupported_upstream_schema",
                "message": "Unsupported upstream schema version.",
                "diagnostics": [],
            }

        if epub_result.get("status") == "failed":
            return {
                "status": "failed",
                "error_code": "upstream_epub_extraction_failed",
                "message": "Upstream EPUB extraction failed.",
                "diagnostics": [],
            }

        try:
            book = deepcopy(epub_result["book"])
            extraction = deepcopy(epub_result["extraction"])
            upstream_diagnostics = deepcopy(epub_result.get("diagnostics", []))
        except Exception:
            return self._invalid_input("Input is not a supported EPUB extraction result.")

        if not isinstance(book, dict) or book.get("language") != "en":
            return self._invalid_input("Input is not a supported EPUB extraction result.")

        source_file = ((book.get("metadata") or {}).get("source_file") or {})
        file_name = source_file.get("file_name")
        if isinstance(file_name, str) and not self._is_safe_basename(file_name):
            return {
                "status": "failed",
                "error_code": "invalid_input",
                "message": "Unsafe upstream source file name.",
                "diagnostics": [
                    {
                        "code": "invalid_source_file_name",
                        "severity": "error",
                        "message": "Upstream source file name is unsafe.",
                        "entity_type": "input",
                        "field": "book.metadata.source_file.file_name",
                    }
                ],
            }

        for chapter in book.get("chapters", []):
            if "paragraphs" in chapter:
                return self._invalid_input("Forbidden chapter paragraphs in upstream input.")

        return {
            "status": "ok",
            "book": book,
            "extraction": extraction,
            "upstream_diagnostics": upstream_diagnostics,
        }

    def _annotate_validated_input(
        self,
        *,
        book: dict[str, Any],
        upstream_diagnostics: list[dict[str, Any]],
        extraction: dict[str, Any],
        effective_config: StanzaAnnotatorConfig,
        started_at: datetime,
        started_clock: float,
    ) -> dict[str, Any]:
        selection = self._materialize_selection(
            effective_config.content_selection, extraction["config"]
        )
        book_out = deepcopy(book)
        plan = self._build_text_unit_plan(book_out, selection)

        if not any(unit["selected"] for unit in plan):
            return self._failed_result(
                code="no_annotatable_text",
                message="Effective config selects no annotatable text units.",
                diagnostics=[],
                config_snapshot=self._snapshot_config(effective_config, selection),
                started_at=started_at,
                duration_ms=0,
            )

        diagnostics: list[dict[str, Any]] = []
        adapter_inputs: list[dict[str, Any]] = []
        summary = {
            "text_unit_count": 0,
            "annotated_text_unit_count": 0,
            "skipped_text_unit_count": 0,
            "chapter_count": len(book_out.get("chapters", [])),
            "front_matter_section_count": len(book_out.get("front_matter", [])),
            "back_matter_section_count": len(book_out.get("back_matter", [])),
            "paragraph_count": sum(
                len(section.get("paragraphs", []))
                for section in book_out.get("front_matter", []) + book_out.get("back_matter", [])
            ),
            "footnote_count": self._count_footnotes(book_out),
            "sentence_count": 0,
            "token_count": 0,
            "word_count": 0,
            "entity_count": 0,
            "warning_count": 0,
            "error_count": 0,
        }

        for unit in plan:
            target = unit["target"]
            if not unit["selected"]:
                self._mark_excluded(unit, target)
                if unit["represented"]:
                    summary["text_unit_count"] += 1
                    summary["skipped_text_unit_count"] += 1
                continue

            summary["text_unit_count"] += 1
            text = unit["text"]
            if text == "":
                self._mark_skipped(unit, target, "empty_text")
                diagnostics.append(
                    {
                        "code": "text_unit_empty",
                        "severity": "warning",
                        "message": "Selected text unit is empty and was skipped.",
                        "entity_type": "text_unit",
                        "entity_id": unit["text_unit_id"],
                        "field": "text",
                    }
                )
                summary["skipped_text_unit_count"] += 1
                continue

            if len(text) > effective_config.max_text_unit_chars:
                self._mark_skipped(unit, target, "too_large")
                diagnostics.append(
                    {
                        "code": "text_unit_too_large",
                        "severity": "warning",
                        "message": "Selected text unit exceeds max_text_unit_chars and was skipped.",
                        "entity_type": "text_unit",
                        "entity_id": unit["text_unit_id"],
                        "field": "text",
                    }
                )
                summary["skipped_text_unit_count"] += 1
                continue

            adapter_inputs.append(unit)

        adapter = self._adapter or DefaultStanzaAdapter(effective_config)
        raw_documents: list[RawStanzaDocument] = []
        for batch in self._chunk(adapter_inputs, effective_config.batch_size):
            texts = [unit["text"] for unit in batch]
            try:
                batch_result = list(adapter.annotate_batch(texts))
            except Exception as exc:
                raise RuntimeError("adapter failure") from exc
            if len(batch_result) != len(texts):
                raise RuntimeError("adapter batch length mismatch")
            raw_documents.extend(batch_result)

        for unit, raw_document in zip(adapter_inputs, raw_documents, strict=True):
            annotation = self._build_text_annotation(unit, raw_document)
            self._mark_annotated(unit, unit["target"], annotation)
            summary["annotated_text_unit_count"] += 1
            summary["sentence_count"] += annotation["summary"]["sentence_count"]
            summary["token_count"] += annotation["summary"]["token_count"]
            summary["word_count"] += annotation["summary"]["word_count"]
            summary["entity_count"] += annotation["summary"]["entity_count"]

        summary["warning_count"] = sum(
            1 for item in diagnostics if item["severity"] == "warning"
        )
        summary["error_count"] = sum(
            1 for item in diagnostics if item["severity"] == "error"
        )

        source_book_fingerprint = self._fingerprint(book)
        annotation_input_fingerprint = self._annotation_input_fingerprint(
            source_book_fingerprint=source_book_fingerprint,
            selection=[unit for unit in plan if unit["selected"]],
            effective_config=effective_config,
        )

        result = {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "status": "succeeded",
            "document": {
                "source": {
                    "upstream_schema_version": SUPPORTED_UPSTREAM_SCHEMA,
                    "upstream_extractor_version": extraction["extractor_version"],
                    "upstream_summary": extraction["summary"],
                    "upstream_diagnostics": upstream_diagnostics,
                    "source_file": book_out["metadata"].get("source_file"),
                    "source_book_fingerprint": source_book_fingerprint,
                    "annotation_input_fingerprint": annotation_input_fingerprint,
                },
                "book": book_out,
            },
            "diagnostics": diagnostics,
            "annotation": {
                "annotator_version": self._annotator_version,
                "stanza_version": self._stanza_version(),
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "finished_at": self._clock().isoformat().replace("+00:00", "Z"),
                "duration_ms": max(0, int((perf_counter() - started_clock) * 1000)),
                "config": self._snapshot_config(effective_config, selection),
                "summary": summary,
            },
        }

        if effective_config.include_debug:
            result["debug"] = {
                "text_unit_plan": [
                    {
                        "text_unit_id": unit["text_unit_id"],
                        "kind": unit["kind"],
                        "selected": unit["selected"],
                    }
                    for unit in plan
                ],
                "raw_stanza_summaries": [],
                "adapter_timings": [],
                "projection_warnings": [],
                "redaction": {
                    "applied": True,
                    "text_preview_max_chars": 0,
                },
            }

        if self._serialized_size(result) > effective_config.max_output_json_bytes:
            return self._failed_result(
                code="output_too_large",
                message="Serialized result exceeds max_output_json_bytes.",
                diagnostics=[],
                config_snapshot=self._snapshot_config(effective_config, selection),
                started_at=started_at,
                duration_ms=max(0, int((perf_counter() - started_clock) * 1000)),
            )

        return result

    def _snapshot_config(
        self,
        config: StanzaAnnotatorConfig,
        selection: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = config.model_dump(mode="json")
        if selection is not None:
            payload["content_selection"] = dict(selection)
        return payload

    def _materialize_selection(
        self,
        config: ContentSelectionConfig,
        extraction_config: Mapping[str, Any],
    ) -> dict[str, Any]:
        if config.mode == "chapter_text_only":
            return {
                "mode": "chapter_text_only",
                "include_chapters": False,
                "include_front_matter": False,
                "include_back_matter": False,
                "include_footnotes": False,
                "include_chapter_titles": False,
                "include_section_titles": False,
            }
        if config.mode == "chapters_only":
            return {
                "mode": "chapters_only",
                "include_chapters": True,
                "include_front_matter": False,
                "include_back_matter": False,
                "include_footnotes": False,
                "include_chapter_titles": config.include_chapter_titles,
                "include_section_titles": False,
            }
        if config.mode == "canonical_from_epub_config":
            return {
                "mode": "canonical_from_epub_config",
                "include_chapters": True,
                "include_front_matter": bool(
                    extraction_config.get("include_front_matter_in_canonical_text", False)
                ),
                "include_back_matter": bool(
                    extraction_config.get("include_back_matter_in_canonical_text", False)
                ),
                "include_footnotes": bool(
                    extraction_config.get("include_footnotes_in_canonical_text", False)
                ),
                "include_chapter_titles": bool(
                    extraction_config.get("include_chapter_titles_in_canonical_text", False)
                ),
                "include_section_titles": bool(
                    extraction_config.get("include_section_titles_in_canonical_text", False)
                ),
            }
        if config.mode == "all_readable":
            return {
                "mode": "all_readable",
                "include_chapters": True,
                "include_front_matter": True,
                "include_back_matter": True,
                "include_footnotes": True,
                "include_chapter_titles": config.include_chapter_titles,
                "include_section_titles": config.include_section_titles,
            }
        return config.model_dump(mode="json")

    def _build_text_unit_plan(
        self, book: dict[str, Any], selection: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []

        for index, section in enumerate(book.get("front_matter", [])):
            units.extend(
                self._section_units(
                    section=section,
                    owner_type="front_matter",
                    selection=selection,
                )
            )

        for chapter in book.get("chapters", []):
            units.append(
                {
                    "text_unit_id": f"{chapter['id']}:text",
                    "kind": "chapter_text",
                    "text": chapter["text"],
                    "selected": selection["mode"] != "custom"
                    or selection["include_chapters"],
                    "represented": True,
                    "target": chapter,
                    "status_key": "text_annotation_status",
                    "reason_key": "text_skipped_reason",
                    "annotation_key": "text_annotation",
                    "owner_type": "chapter",
                    "owner_id": chapter["id"],
                    "source_field": "text",
                }
            )
            if chapter.get("title") is not None:
                title_selected = False
                if selection["mode"] == "canonical_from_epub_config":
                    title_selected = bool(selection["include_chapter_titles"])
                elif selection["mode"] in {"all_readable", "chapters_only", "custom"}:
                    title_selected = bool(selection["include_chapter_titles"])
                units.append(
                    {
                        "text_unit_id": f"{chapter['id']}:title",
                        "kind": "chapter_title",
                        "text": chapter["title"],
                        "selected": title_selected,
                        "represented": title_selected,
                        "target": chapter,
                        "status_key": "title_annotation_status",
                        "reason_key": "title_skipped_reason",
                        "annotation_key": "title_annotation",
                        "owner_type": "chapter",
                        "owner_id": chapter["id"],
                        "source_field": "title",
                    }
                )
            for footnote in chapter.get("footnotes", []):
                units.append(self._footnote_unit(footnote, chapter, "chapter", selection))

        for section in book.get("back_matter", []):
            units.extend(
                self._section_units(
                    section=section,
                    owner_type="back_matter",
                    selection=selection,
                )
            )

        for footnote in book.get("footnotes", []):
            units.append(self._footnote_unit(footnote, {"id": "book"}, "book", selection))
        return units

    def _section_units(
        self,
        *,
        section: dict[str, Any],
        owner_type: str,
        selection: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        include_text = bool(
            selection["include_front_matter"] if owner_type == "front_matter" else selection["include_back_matter"]
        )
        units = [
            {
                "text_unit_id": f"{section['id']}:text",
                "kind": "section_text",
                "text": section["text"],
                "selected": include_text,
                "represented": include_text,
                "target": section,
                "status_key": "text_annotation_status",
                "reason_key": "text_skipped_reason",
                "annotation_key": "text_annotation",
                "owner_type": owner_type,
                "owner_id": section["id"],
                "source_field": "text",
            }
        ]
        if section.get("title") is not None:
            title_selected = bool(selection["include_section_titles"]) and include_text
            units.append(
                {
                    "text_unit_id": f"{section['id']}:title",
                    "kind": "section_title",
                    "text": section["title"],
                    "selected": title_selected,
                    "represented": title_selected,
                    "target": section,
                    "status_key": "title_annotation_status",
                    "reason_key": "title_skipped_reason",
                    "annotation_key": "title_annotation",
                    "owner_type": owner_type,
                    "owner_id": section["id"],
                    "source_field": "title",
                }
            )
        for footnote in section.get("footnotes", []):
            units.append(self._footnote_unit(footnote, section, owner_type, selection))
        return units

    def _footnote_unit(
        self,
        footnote: dict[str, Any],
        owner: dict[str, Any],
        owner_type: str,
        selection: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "text_unit_id": footnote["id"],
            "kind": "footnote",
            "text": footnote["text"],
            "selected": bool(selection["include_footnotes"]),
            "represented": True,
            "target": footnote,
            "status_key": "annotation_status",
            "reason_key": "skipped_reason",
            "annotation_key": "annotation",
            "owner_type": owner_type,
            "owner_id": owner["id"],
            "source_field": "text",
            "footnote_id": footnote["id"],
        }

    def _mark_excluded(self, unit: dict[str, Any], target: dict[str, Any]) -> None:
        if unit["represented"]:
            target[unit["status_key"]] = "skipped"
            target[unit["reason_key"]] = "excluded_by_config"

    def _mark_skipped(
        self, unit: dict[str, Any], target: dict[str, Any], reason: str
    ) -> None:
        target[unit["status_key"]] = "skipped"
        target[unit["reason_key"]] = reason

    def _mark_annotated(
        self, unit: dict[str, Any], target: dict[str, Any], annotation: dict[str, Any]
    ) -> None:
        target[unit["status_key"]] = "annotated"
        target[unit["annotation_key"]] = annotation

    def _build_text_annotation(
        self, unit: dict[str, Any], raw_document: RawStanzaDocument
    ) -> dict[str, Any]:
        sentences = []
        entities = []
        word_id_map: dict[tuple[int, int], str] = {}

        for sentence_number, sentence in enumerate(raw_document.sentences, start=1):
            sentence_id = f"{unit['text_unit_id']}:s{sentence_number:04d}"
            token_payloads = []
            word_payloads = []
            word_counter = 0

            for token_number, token in enumerate(sentence.tokens, start=1):
                token_id = f"{sentence_id}:t{token_number:04d}"
                token_word_ids = []
                for word in token.words:
                    word_counter += 1
                    word_id = f"{sentence_id}:w{word_counter:04d}"
                    word_id_map[(sentence_number, word_counter)] = word_id
                    token_word_ids.append(word_id)
                    word_payloads.append(
                        self._word_payload(unit["text_unit_id"], sentence_id, word_counter, word)
                    )
                token_payloads.append(
                    {
                        "id": token_id,
                        "text_unit_id": unit["text_unit_id"],
                        "sentence_id": sentence_id,
                        "token_number": token_number,
                        "text": token.text,
                        "start_char": token.start_char,
                        "end_char": token.end_char,
                        "word_ids": token_word_ids,
                    }
                )

            for word_payload in word_payloads:
                if word_payload["head"] > 0:
                    word_payload["head_word_id"] = word_payloads[word_payload["head"] - 1]["id"]

            sentences.append(
                {
                    "id": sentence_id,
                    "text_unit_id": unit["text_unit_id"],
                    "sentence_number": sentence_number,
                    "text": sentence.text,
                    "start_char": sentence.start_char,
                    "end_char": sentence.end_char,
                    "tokens": token_payloads,
                    "words": word_payloads,
                }
            )

        for entity_number, entity in enumerate(raw_document.entities, start=1):
            entities.append(
                {
                    "id": f"{unit['text_unit_id']}:e{entity_number:04d}",
                    "text_unit_id": unit["text_unit_id"],
                    "entity_number": entity_number,
                    "text": entity.text,
                    "type": entity.type,
                    "start_char": entity.start_char,
                    "end_char": entity.end_char,
                }
            )

        return {
            "text_unit_id": unit["text_unit_id"],
            "ref": {
                "text_unit_id": unit["text_unit_id"],
                "kind": unit["kind"],
                "owner_type": unit["owner_type"],
                "owner_id": unit["owner_id"],
                "source_field": unit["source_field"],
                **({"footnote_id": unit["footnote_id"]} if "footnote_id" in unit else {}),
            },
            "text": unit["text"],
            "sentences": sentences,
            "entities": entities,
            "summary": {
                "sentence_count": len(sentences),
                "token_count": sum(len(sentence["tokens"]) for sentence in sentences),
                "word_count": sum(len(sentence["words"]) for sentence in sentences),
                "entity_count": len(entities),
            },
        }

    def _word_payload(
        self,
        text_unit_id: str,
        sentence_id: str,
        word_number: int,
        word: RawStanzaWord,
    ) -> dict[str, Any]:
        payload = {
            "id": f"{sentence_id}:w{word_number:04d}",
            "text_unit_id": text_unit_id,
            "sentence_id": sentence_id,
            "word_number": word_number,
            "text": word.text,
            "lemma": word.lemma,
            "upos": word.upos,
            "head": word.head,
            "deprel": word.deprel,
            "start_char": word.start_char,
            "end_char": word.end_char,
        }
        if word.xpos is not None:
            payload["xpos"] = word.xpos
        if word.feats is not None:
            payload["feats"] = word.feats
        return payload

    def _legacy_sentence(self, sentence: RawStanzaSentence) -> Sentence:
        return Sentence(
            text=sentence.text,
            tokens=[self._legacy_token(token) for token in sentence.tokens],
            words=[self._legacy_word(word) for token in sentence.tokens for word in token.words],
        )

    def _legacy_token(self, token: RawStanzaToken) -> Token:
        return Token(text=token.text, words=[self._legacy_word(word) for word in token.words])

    def _legacy_word(self, word: RawStanzaWord) -> Word:
        return Word(
            text=word.text,
            lemma=word.lemma,
            upos=word.upos,
            xpos=word.xpos,
            feats=word.feats,
            head=word.head,
            deprel=word.deprel,
            start_char=word.start_char,
            end_char=word.end_char,
        )

    def _legacy_entity(self, entity: Any) -> Entity:
        return Entity(
            text=entity.text,
            type=entity.type,
            start_char=entity.start_char,
            end_char=entity.end_char,
        )

    def _annotation_input_fingerprint(
        self,
        *,
        source_book_fingerprint: str,
        selection: Sequence[dict[str, Any]],
        effective_config: StanzaAnnotatorConfig,
    ) -> str:
        config_payload = self._snapshot_config(effective_config)
        config_payload.pop("include_debug", None)
        config_payload.pop("logging", None)
        config_payload.pop("batch_size", None)
        payload = {
            "supported_upstream_schema_version": SUPPORTED_UPSTREAM_SCHEMA,
            "source_book_fingerprint": source_book_fingerprint,
            "selected_text_units": [
                {
                    "id": unit["text_unit_id"],
                    "kind": unit["kind"],
                    "owner_type": unit["owner_type"],
                    "owner_id": unit["owner_id"],
                    "source_field": unit["source_field"],
                    "text": unit["text"],
                }
                for unit in selection
            ],
            "effective_config_without_include_debug_and_logging": config_payload,
            "stanza_version": self._stanza_version(),
            "stanza_model_identity": "default-en",
            "projection_contract_version": OUTPUT_SCHEMA_VERSION,
        }
        return self._fingerprint(payload)

    def _fingerprint(self, value: object) -> str:
        return f"sha256:{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"

    def _stanza_version(self) -> str:
        try:
            return metadata.version("stanza")
        except metadata.PackageNotFoundError:
            return "unknown"

    def _serialized_size(self, value: object) -> int:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def _failed_result(
        self,
        *,
        code: str,
        message: str,
        diagnostics: list[dict[str, Any]],
        config_snapshot: Mapping[str, Any],
        started_at: datetime,
        duration_ms: int,
    ) -> dict[str, Any]:
        finished_at = self._clock()
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "status": "failed",
            "error": {
                "code": code,
                "message": message,
                "recoverable": False,
            },
            "diagnostics": diagnostics,
            "annotation": {
                "annotator_version": self._annotator_version,
                "stanza_version": self._stanza_version(),
                "started_at": started_at.isoformat().replace("+00:00", "Z"),
                "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
                "duration_ms": duration_ms,
                "config": dict(config_snapshot),
                "summary": {
                    "text_unit_count": 0,
                    "annotated_text_unit_count": 0,
                    "skipped_text_unit_count": 0,
                    "chapter_count": 0,
                    "front_matter_section_count": 0,
                    "back_matter_section_count": 0,
                    "paragraph_count": 0,
                    "footnote_count": 0,
                    "sentence_count": 0,
                    "token_count": 0,
                    "word_count": 0,
                    "entity_count": 0,
                    "warning_count": sum(
                        1 for item in diagnostics if item["severity"] == "warning"
                    ),
                    "error_count": max(
                        1, sum(1 for item in diagnostics if item["severity"] == "error")
                    ),
                },
            },
        }

    def _config_diagnostic(self, exc: ValidationError) -> dict[str, Any]:
        field = ".".join(str(item) for item in exc.errors()[0]["loc"]) or "config"
        return {
            "code": "invalid_config_field",
            "severity": "error",
            "message": "Invalid config field.",
            "entity_type": "config",
            "field": field,
        }

    def _invalid_input(self, message: str) -> dict[str, Any]:
        return {
            "status": "failed",
            "error_code": "invalid_input",
            "message": message,
            "diagnostics": [],
        }

    def _chunk(self, items: Sequence[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
        return [list(items[index : index + size]) for index in range(0, len(items), size)]

    def _count_footnotes(self, book: Mapping[str, Any]) -> int:
        total = len(book.get("footnotes", []))
        total += sum(len(chapter.get("footnotes", [])) for chapter in book.get("chapters", []))
        total += sum(len(section.get("footnotes", [])) for section in book.get("front_matter", []))
        total += sum(len(section.get("footnotes", [])) for section in book.get("back_matter", []))
        return total

    def _is_safe_basename(self, value: str) -> bool:
        if not value or "/" in value or "\\" in value or ".." in value:
            return False
        return not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)

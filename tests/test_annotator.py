import json
from datetime import UTC, datetime
from pathlib import Path

from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator._internal.types import (
    RawStanzaDocument,
    RawStanzaEntity,
    RawStanzaSentence,
    RawStanzaToken,
    RawStanzaWord,
)

FIXTURES = Path(__file__).resolve().parents[1] / "docs" / "testing" / "fixtures"


class FakeBatchAdapter:
    def __init__(self, documents: list[RawStanzaDocument]) -> None:
        self.documents = documents
        self.calls: list[list[str]] = []

    def annotate_batch(self, texts: list[str]) -> list[RawStanzaDocument]:
        self.calls.append(list(texts))
        return self.documents[: len(texts)]


class RaisingBatchAdapter:
    def annotate_batch(self, texts: list[str]) -> list[RawStanzaDocument]:
        raise RuntimeError("synthetic adapter failure: SECRET_TOKEN")


class BadBatchAdapter:
    def annotate_batch(self, texts: list[str]) -> list[RawStanzaDocument]:
        return []


def _load_json(*parts: str) -> dict:
    return json.loads(FIXTURES.joinpath(*parts).read_text(encoding="utf-8"))


def _fixed_clock() -> datetime:
    return datetime(2000, 1, 1, tzinfo=UTC)


def _raw_document_for_text(text: str) -> RawStanzaDocument:
    if text == "Alice sees Bob.":
        words = [
            RawStanzaWord("Alice", "Alice", "PROPN", "nsubj", 2, 0, 5),
            RawStanzaWord("sees", "see", "VERB", "root", 0, 6, 10),
            RawStanzaWord("Bob", "Bob", "PROPN", "obj", 2, 11, 14),
        ]
        tokens = [
            RawStanzaToken("Alice", 0, 5, [words[0]]),
            RawStanzaToken("sees", 6, 10, [words[1]]),
            RawStanzaToken("Bob", 11, 14, [words[2]]),
        ]
        return RawStanzaDocument(
            sentences=[RawStanzaSentence(text, 0, 15, tokens)],
            entities=[],
        )
    if text == "Before the story.":
        words = [
            RawStanzaWord("Before", "before", "ADP", "case", 3, 0, 6),
            RawStanzaWord("the", "the", "DET", "det", 3, 7, 10),
            RawStanzaWord("story", "story", "NOUN", "root", 0, 11, 16),
        ]
        tokens = [
            RawStanzaToken("Before", 0, 6, [words[0]]),
            RawStanzaToken("the", 7, 10, [words[1]]),
            RawStanzaToken("story", 11, 16, [words[2]]),
        ]
        return RawStanzaDocument(
            sentences=[RawStanzaSentence(text, 0, 17, tokens)],
            entities=[],
        )
    word = RawStanzaWord(text, text.lower(), "X", "root", 0, 0, len(text))
    token = RawStanzaToken(text, 0, len(text), [word])
    return RawStanzaDocument(
        sentences=[RawStanzaSentence(text, 0, len(text), [token])],
        entities=[],
    )


def test_annotate_epub_result_default_selects_only_chapter_text() -> None:
    adapter = FakeBatchAdapter([_raw_document_for_text("Alice sees Bob.")])
    annotator = StanzaAnnotator(
        {"use_gpu": False},
        adapter=adapter,
        clock=_fixed_clock,
        annotator_version="2.0.0",
    )

    result = annotator.annotate_epub_result(
        _load_json("input", "minimal_success_epub_result.json"),
        _load_json("config", "default_minimal.json"),
    )

    chapter = result["document"]["book"]["chapters"][0]
    assert result["status"] == "succeeded"
    assert adapter.calls == [["Alice sees Bob."]]
    assert "paragraphs" not in chapter
    assert chapter["text_annotation_status"] == "annotated"
    assert chapter["text_annotation"]["ref"]["kind"] == "chapter_text"
    assert chapter["text_annotation"]["text"] == "Alice sees Bob."


def test_batch_size_two_groups_five_chapters_as_221() -> None:
    texts = [f"Text {index}." for index in range(1, 6)]
    adapter = FakeBatchAdapter([_raw_document_for_text(text) for text in texts])
    annotator = StanzaAnnotator(
        {"use_gpu": False},
        adapter=adapter,
        clock=_fixed_clock,
        annotator_version="2.0.0",
    )

    result = annotator.annotate_epub_result(
        _load_json("input", "complex_batch_epub_result.json"),
        _load_json("config", "batch_size_2.json"),
    )

    assert result["status"] == "succeeded"
    assert adapter.calls == [
        ["Text 1.", "Text 2."],
        ["Text 3.", "Text 4."],
        ["Text 5."],
    ]


def test_custom_front_matter_section_text_annotates_section_and_skips_chapters() -> None:
    adapter = FakeBatchAdapter([_raw_document_for_text("Before the story.")])
    annotator = StanzaAnnotator(
        {"use_gpu": False},
        adapter=adapter,
        clock=_fixed_clock,
        annotator_version="2.0.0",
    )

    result = annotator.annotate_epub_result(
        _load_json("input", "complex_batch_epub_result.json"),
        _load_json("config", "custom_front_matter_section_text.json"),
    )

    section = result["document"]["book"]["front_matter"][0]
    assert adapter.calls == [["Before the story."]]
    assert section["text_annotation"]["ref"]["kind"] == "section_text"
    assert "annotation" not in section["paragraphs"][0]
    for chapter in result["document"]["book"]["chapters"]:
        assert chapter["text_annotation_status"] == "skipped"
        assert chapter["text_skipped_reason"] == "excluded_by_config"


def test_empty_chapter_text_is_skipped_without_adapter_call() -> None:
    adapter = FakeBatchAdapter([])
    annotator = StanzaAnnotator(
        {"use_gpu": False},
        adapter=adapter,
        clock=_fixed_clock,
        annotator_version="2.0.0",
    )

    result = annotator.annotate_epub_result(
        _load_json("input", "empty_chapter_text_epub_result.json"),
        _load_json("config", "default_minimal.json"),
    )

    chapter = result["document"]["book"]["chapters"][0]
    assert adapter.calls == []
    assert chapter["text_annotation_status"] == "skipped"
    assert chapter["text_skipped_reason"] == "empty_text"
    assert result["diagnostics"][0]["code"] == "text_unit_empty"


def test_runtime_adapter_exception_maps_to_failed_result() -> None:
    annotator = StanzaAnnotator(
        {"use_gpu": False},
        adapter=RaisingBatchAdapter(),
        clock=_fixed_clock,
        annotator_version="2.0.0",
    )

    result = annotator.annotate_epub_result(
        _load_json("input", "minimal_success_epub_result.json"),
        _load_json("config", "default_minimal.json"),
    )

    assert result["status"] == "failed"
    assert result["error"]["code"] == "stanza_runtime_failed"
    assert result["diagnostics"][0]["entity_type"] == "stanza_runtime"


def test_runtime_batch_length_mismatch_maps_to_failed_result() -> None:
    annotator = StanzaAnnotator(
        {"use_gpu": False},
        adapter=BadBatchAdapter(),
        clock=_fixed_clock,
        annotator_version="2.0.0",
    )

    result = annotator.annotate_epub_result(
        _load_json("input", "minimal_success_epub_result.json"),
        _load_json("config", "default_minimal.json"),
    )

    assert result["status"] == "failed"
    assert result["error"]["code"] == "stanza_runtime_failed"

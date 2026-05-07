import json
from pathlib import Path

import pytest

from stanza_annotator.cli import main
from stanza_annotator.errors import StanzaRuntimeError
from stanza_annotator.models import AnnotatedDocument, Sentence, Token, Word


def _sample_document() -> AnnotatedDocument:
    word = Word(
        text="I",
        lemma="I",
        upos="PRON",
        xpos=None,
        feats="Person=1|Number=Sing",
        head=2,
        deprel="nsubj",
        start_char=0,
        end_char=1,
    )
    return AnnotatedDocument(
        sentences=[
            Sentence(
                text="I am tired.",
                tokens=[Token(text="I", words=[word])],
                words=[word],
            )
        ],
        entities=[],
    )


class _StaticAnnotator:
    def __init__(self, document: AnnotatedDocument) -> None:
        self._document = document

    def annotate(self, text: str) -> AnnotatedDocument:
        return self._document


class _RaisingAnnotator:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def annotate(self, text: str) -> AnnotatedDocument:
        raise self._exc


def test_cli_writes_empty_document_for_empty_file(tmp_path: Path) -> None:
    input_path = tmp_path / "empty.txt"
    output_path = tmp_path / "out.json"
    input_path.write_text("\n", encoding="utf-8")

    exit_code = main([str(input_path), "--output", str(output_path), "--no-download"])

    assert exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "sentences": [],
        "entities": [],
    }


def test_cli_invalid_processors_return_expected_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--processors", "tokenize,pos", "--no-download"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "processors" in captured.err


def test_cli_success_writes_document_only_to_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = _sample_document()
    input_path = tmp_path / "in.txt"
    input_path.write_text("I am tired.", encoding="utf-8")

    exit_code = main(
        [str(input_path), "--no-download"],
        annotator_factory=lambda cfg: _StaticAnnotator(document),
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == document.model_dump(mode="json")


def test_cli_missing_input_file_returns_1(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "does_not_exist.txt"

    exit_code = main([str(missing), "--no-download"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""


def test_cli_stanza_runtime_error_exit_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "in.txt"
    input_path.write_text("hello", encoding="utf-8")

    exit_code = main(
        [str(input_path), "--no-download"],
        annotator_factory=lambda cfg: _RaisingAnnotator(
            StanzaRuntimeError("boom")
        ),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "boom" in captured.err


def test_cli_unexpected_error_exit_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "in.txt"
    input_path.write_text("hello", encoding="utf-8")

    exit_code = main(
        [str(input_path), "--no-download"],
        annotator_factory=lambda cfg: _RaisingAnnotator(RuntimeError("oops")),
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""


def test_cli_no_partial_output_file_on_error(tmp_path: Path) -> None:
    input_path = tmp_path / "in.txt"
    input_path.write_text("hello", encoding="utf-8")
    output_path = tmp_path / "out.json"

    exit_code = main(
        [str(input_path), "--output", str(output_path), "--no-download"],
        annotator_factory=lambda cfg: _RaisingAnnotator(
            StanzaRuntimeError("boom")
        ),
    )

    assert exit_code == 2
    assert not output_path.exists()


def test_cli_debug_flag_does_not_change_stdout_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = _sample_document()
    input_path = tmp_path / "in.txt"
    input_path.write_text("I am tired.", encoding="utf-8")

    main(
        [str(input_path), "--no-download"],
        annotator_factory=lambda cfg: _StaticAnnotator(document),
    )
    plain = capsys.readouterr().out

    main(
        [
            str(input_path),
            "--debug",
            "--debug-dir",
            str(tmp_path / "dbg"),
            "--no-download",
        ],
        annotator_factory=lambda cfg: _StaticAnnotator(document),
    )
    debug = capsys.readouterr().out

    assert plain == debug
    assert json.loads(plain) == document.model_dump(mode="json")

import json
from pathlib import Path

import pytest

from stanza_annotator.cli import main


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

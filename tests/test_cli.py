import json
from pathlib import Path

import pytest

from stanza_annotator.cli import main

FIXTURES = Path(__file__).resolve().parents[1] / "docs" / "testing" / "fixtures"


class _StaticAnnotator:
    def __init__(self, result: dict) -> None:
        self._result = result

    def annotate_epub_result(self, epub_result: dict, config: dict | None = None) -> dict:
        return self._result


def _load_json(*parts: str) -> dict:
    return json.loads(FIXTURES.joinpath(*parts).read_text(encoding="utf-8"))


def test_cli_success_stdout_json(capsys: pytest.CaptureFixture[str]) -> None:
    result = _load_json("expected", "minimal_success_output.normalized.json")
    input_path = FIXTURES / "input" / "minimal_success_epub_result.json"
    config_path = FIXTURES / "config" / "default_minimal.json"

    exit_code = main(
        ["annotate", str(input_path), "--config", str(config_path)],
        annotator_factory=lambda cfg: _StaticAnnotator(result),
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == result


def test_cli_invalid_config_exits_4(capsys: pytest.CaptureFixture[str]) -> None:
    input_path = FIXTURES / "input" / "minimal_success_epub_result.json"
    config_path = FIXTURES / "config" / "invalid_unknown_field.json"

    exit_code = main(["annotate", str(input_path), "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 4
    assert json.loads(captured.out)["error"]["code"] == "invalid_config"


def test_cli_rejects_dual_stdin_usage(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["annotate", "-", "--config", "-"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "stdin" in captured.err.lower()


def test_cli_output_write_failure_returns_3(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _load_json("expected", "minimal_success_output.normalized.json")
    input_path = FIXTURES / "input" / "minimal_success_epub_result.json"
    output_path = tmp_path / "out_dir"
    output_path.mkdir()

    exit_code = main(
        ["annotate", str(input_path), "--output", str(output_path)],
        annotator_factory=lambda cfg: _StaticAnnotator(result),
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""

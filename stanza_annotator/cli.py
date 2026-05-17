from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator.config import LoggingConfig, StanzaAnnotatorConfig
from stanza_annotator.runtime_metadata import get_module_version

LOGGER = logging.getLogger("stanza_annotator")

AnnotatorFactory = Callable[[StanzaAnnotatorConfig], "_Annotator"]


class _Annotator(Protocol):
    def annotate_epub_result(
        self,
        epub_result: dict,
        config: dict | None = None,
    ) -> dict[str, Any]:  # pragma: no cover - protocol
        ...


def main(
    argv: list[str] | None = None,
    *,
    annotator_factory: Callable[[StanzaAnnotatorConfig], _Annotator] | None = None,
) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    factory = annotator_factory or (lambda cfg: StanzaAnnotator(cfg))

    if args.command != "annotate":
        parser.print_help(sys.stderr)
        return 2

    if args.input == "-" and args.config == "-":
        _write_error("cannot read both input and config from stdin")
        return 2

    try:
        epub_result = _read_json(args.input)
    except (json.JSONDecodeError, OSError) as exc:
        return _write_failed_output(
            result=_parsing_failure_result("invalid_input", "Malformed input JSON."),
            output_path=args.output,
            exit_code=1,
            stderr_message=str(exc),
        )

    try:
        user_config = _read_json(args.config) if args.config else {}
    except (json.JSONDecodeError, OSError) as exc:
        return _write_failed_output(
            result=_parsing_failure_result("invalid_config", "Malformed config JSON."),
            output_path=args.output,
            exit_code=4,
            stderr_message=str(exc),
        )

    if not isinstance(user_config, Mapping):
        user_config = {}
    user_config = dict(user_config)
    if args.include_debug:
        user_config["include_debug"] = True

    try:
        config = StanzaAnnotatorConfig.model_validate(user_config)
    except Exception:
        config = StanzaAnnotatorConfig()

    _configure_logging(config.logging)
    result = factory(config).annotate_epub_result(epub_result, user_config)
    payload = json.dumps(
        result,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
    ) + "\n"

    if args.output in {None, "-"}:
        sys.stdout.write(payload)
    else:
        output_path = Path(args.output)
        write_status = _write_output_file(output_path, payload)
        if write_status is not None:
            _write_error(write_status)
            return 3

    if result["status"] == "succeeded":
        return 0
    if result["error"]["code"] == "invalid_config":
        return 4
    if result["error"]["code"] == "internal_error":
        return 99
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stanza-annotator")
    subparsers = parser.add_subparsers(dest="command")
    annotate = subparsers.add_parser("annotate")
    annotate.add_argument("input", help="Input JSON path or - for stdin.")
    annotate.add_argument("--output", help="Output path or - for stdout.")
    annotate.add_argument("--config", help="Optional config JSON path or - for stdin.")
    annotate.add_argument("--pretty", action="store_true")
    annotate.add_argument("--include-debug", action="store_true")
    annotate.add_argument("--debug-dir", help="CLI-only debug directory.")
    annotate.add_argument(
        "--version",
        action="version",
        version=get_module_version("stanza-annotator"),
    )
    return parser


def _read_json(path_arg: str | None) -> object:
    if path_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path_arg).read_text(encoding="utf-8")
    return json.loads(raw)


def _write_output_file(path: Path, payload: str) -> str | None:
    if path.exists() and path.is_dir():
        return "output path is a directory"
    if path.exists() and path.is_symlink():
        return "output symlink is not allowed"
    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        return "output parent directory does not exist"

    temp_path = parent / f".{path.name}.tmp"
    try:
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, path)
    except OSError:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        return "output write failed"
    return None


def _parsing_failure_result(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "stanza_annotator.v2.0",
        "status": "failed",
        "error": {
            "code": code,
            "message": message,
            "recoverable": False,
        },
        "diagnostics": [],
        "annotation": {
            "annotator_version": get_module_version("stanza-annotator"),
            "stanza_version": "1.8.2",
            "started_at": "2000-01-01T00:00:00Z",
            "finished_at": "2000-01-01T00:00:00Z",
            "duration_ms": 0,
            "config": StanzaAnnotatorConfig().model_dump(mode="json"),
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
                "warning_count": 0,
                "error_count": 1,
            },
        },
    }


def _write_failed_output(
    *,
    result: dict[str, Any],
    output_path: str | None,
    exit_code: int,
    stderr_message: str,
) -> int:
    payload = json.dumps(result, ensure_ascii=False) + "\n"
    if output_path in {None, "-"}:
        sys.stdout.write(payload)
        return exit_code
    write_status = _write_output_file(Path(output_path), payload)
    if write_status is not None:
        _write_error(stderr_message)
        return 3
    return exit_code


def _configure_logging(config: LoggingConfig) -> None:
    if not config.enabled:
        logging.disable(logging.CRITICAL)
        return
    logging.disable(logging.NOTSET)
    logging.basicConfig(
        level=config.level.upper(),
        stream=sys.stderr,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )


def _write_error(message: str) -> None:
    sys.stderr.write(f"{message}\n")


if __name__ == "__main__":
    raise SystemExit(main())

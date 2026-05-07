from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator.config import (
    DEFAULT_PROCESSORS,
    LoggingConfig,
    StanzaAnnotatorConfig,
)
from stanza_annotator.errors import (
    AnnotationError,
    ConfigurationError,
    InputValidationError,
    StanzaRuntimeError,
)
from stanza_annotator.models import AnnotatedDocument

LOGGER = logging.getLogger("stanza_annotator")

AnnotatorFactory = Callable[[StanzaAnnotatorConfig], "_Annotator"]


class _Annotator(Protocol):
    def annotate(self, text: str) -> AnnotatedDocument:  # pragma: no cover - protocol
        ...


def main(
    argv: list[str] | None = None,
    *,
    annotator_factory: Callable[[StanzaAnnotatorConfig], _Annotator] | None = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    factory = annotator_factory or (lambda cfg: StanzaAnnotator(cfg))

    try:
        config = _resolve_config(args)
        _configure_logging(config)
        LOGGER.info("annotation cli started")

        text = _read_input(args.input)
        document = factory(config).annotate(text)
        output = document.model_dump_json(indent=2) + "\n"

        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        LOGGER.info("annotation cli finished")
        return 0
    except (ConfigurationError, InputValidationError, ValidationError, OSError) as exc:
        _write_error(str(exc))
        return 1
    except StanzaRuntimeError as exc:
        _write_error(str(exc))
        return 2
    except AnnotationError as exc:
        _write_error(str(exc))
        return 2
    except Exception:
        _write_error("unexpected system error")
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stanza-annotate",
        description="Annotate prepared UTF-8 English text with Stanza.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Input UTF-8 text file. Reads stdin when omitted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JSON file. Writes stdout when omitted.",
    )
    parser.add_argument("--language", default=None)
    parser.add_argument("--processors", default=None)
    parser.add_argument("--debug", "-d", action="store_true")
    parser.add_argument("--debug-dir", type=Path, default=Path("debug"))
    parser.add_argument("--tokenize-pretokenized", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"])

    gpu = parser.add_mutually_exclusive_group()
    gpu.add_argument("--use-gpu", dest="use_gpu", action="store_true", default=None)
    gpu.add_argument("--no-gpu", dest="use_gpu", action="store_false")
    return parser


def _read_input(path: Path | None) -> str:
    if path is None:
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def _resolve_config(args: argparse.Namespace) -> StanzaAnnotatorConfig:
    debug_enabled = args.debug or _env_bool("STANZA_ANNOTATOR_DEBUG", default=False)
    if args.log_level is not None:
        log_level = args.log_level
    elif debug_enabled:
        log_level = "debug"
    else:
        log_level = os.getenv("STANZA_ANNOTATOR_LOG_LEVEL", "info")
    logging_config = LoggingConfig.model_validate(
        {
            "enabled": _env_bool("STANZA_ANNOTATOR_LOGGING", default=True),
            "level": log_level,
        }
    )
    return StanzaAnnotatorConfig.model_validate(
        {
            "language": args.language or os.getenv("STANZA_ANNOTATOR_LANGUAGE", "en"),
            "processors": args.processors
            or os.getenv("STANZA_ANNOTATOR_PROCESSORS", DEFAULT_PROCESSORS),
            "use_gpu": (
                args.use_gpu
                if args.use_gpu is not None
                else _env_bool("STANZA_ANNOTATOR_USE_GPU", default=True)
            ),
            "tokenize_pretokenized": args.tokenize_pretokenized
            or _env_bool("STANZA_ANNOTATOR_TOKENIZE_PRETOKENIZED", default=False),
            "auto_download": not args.no_download
            and _env_bool("STANZA_ANNOTATOR_AUTO_DOWNLOAD", default=True),
            "debug": debug_enabled,
            "debug_dir": args.debug_dir,
            "logging": logging_config,
        }
    )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _configure_logging(config: StanzaAnnotatorConfig) -> None:
    if not config.logging.enabled:
        logging.disable(logging.CRITICAL)
        return

    logging.disable(logging.NOTSET)
    logging.basicConfig(
        level=config.logging.level.upper(),
        stream=sys.stderr,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True,
    )


def _write_error(message: str) -> None:
    sys.stderr.write(f"{message}\n")


if __name__ == "__main__":
    raise SystemExit(main())

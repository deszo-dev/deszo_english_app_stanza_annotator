from __future__ import annotations

import argparse
import sys
from pathlib import Path

from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator.config import DEFAULT_PROCESSORS, StanzaAnnotatorConfig


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    text = _read_input(args.input)
    config = StanzaAnnotatorConfig(
        language=args.language,
        processors=args.processors,
        use_gpu=args.use_gpu,
        tokenize_pretokenized=args.tokenize_pretokenized,
        auto_download=not args.no_download,
        debug=args.debug,
        debug_dir=args.debug_dir,
    )
    document = StanzaAnnotator(config).annotate(text)
    output = document.model_dump_json(indent=2) + "\n"

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


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
    parser.add_argument("--language", default="en")
    parser.add_argument("--processors", default=DEFAULT_PROCESSORS)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--debug-dir", type=Path, default=Path("debug"))
    parser.add_argument("--tokenize-pretokenized", action="store_true")
    parser.add_argument("--no-download", action="store_true")

    gpu = parser.add_mutually_exclusive_group()
    gpu.add_argument("--use-gpu", dest="use_gpu", action="store_true", default=True)
    gpu.add_argument("--no-gpu", dest="use_gpu", action="store_false")
    return parser


def _read_input(path: Path | None) -> str:
    if path is None:
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

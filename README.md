# `stanza_annotator`

`stanza_annotator` annotates structured English EPUB content produced by `epub_content_extractor.v3.0` and returns a `stanza_annotator.v2.0` result with:

- preserved EPUB structure;
- per-text-unit Stanza annotations;
- upstream provenance;
- diagnostics and summary counters;
- optional debug payload.

The official module contract is documented in:

- [architecture](docs/architecture/stanza_annotator_architecture.md)
- [testing guide](docs/testing/stanza_annotator_testing.md)
- [config schema](docs/architecture/schema/stanza_annotator_config.v2.0.schema.json)
- [output schema](docs/architecture/schema/stanza_annotator.v2.0.schema.json)

## Install

```bash
pip install -e ".[dev]"
```

Stanza models are downloaded automatically on first real annotation run unless `auto_download=false`.

## Python API

```python
import json

from stanza_annotator import StanzaAnnotator

epub_result = json.loads(open("epub_content.json", "r", encoding="utf-8").read())

annotator = StanzaAnnotator({"use_gpu": False})
result = annotator.annotate_epub_result(
    epub_result,
    {
        "content_selection": {"mode": "chapter_text_only"},
        "batch_size": 8,
    },
)

print(result["status"])
print(result["annotation"]["summary"]["sentence_count"])
```

Official document-level API:

- `StanzaAnnotator.annotate_epub_result(epub_result, config=None)`

Compatibility helper retained for low-level use:

- `StanzaAnnotator.annotate(text)` for plain prepared text

## CLI

```bash
stanza-annotator annotate epub_content.json --pretty
```

With explicit config and debug sidecar output:

```bash
stanza-annotator annotate \
  epub_content.json \
  --config annotator_config.json \
  --output annotation.json \
  --include-debug \
  --debug-dir debug \
  --pretty
```

CLI rules:

- positional `INPUT.json` reads `epub_content_extractor.v3.0` JSON.
- `--config PATH` reads annotator config JSON.
- `INPUT.json = -` and `--config -` cannot be used together.
- `--include-debug` affects only top-level debug payload and must not change production annotation fields.
- `--debug-dir` is CLI-only and is not part of the library config contract.
- stdout stays machine-readable JSON unless `--output` is used.

Exit codes:

- `0`: success
- `1`: structured failed result for input/runtime/domain failures
- `2`: CLI usage error
- `3`: output write failure
- `4`: invalid config

## Config Summary

Main config fields:

- `language`: must be `"en"`
- `processors`: must be `"tokenize,mwt,pos,lemma,depparse,ner"`
- `use_gpu`
- `auto_download`
- `content_selection`
- `batch_size`
- `max_text_unit_chars`
- `max_output_json_bytes`
- `include_debug`
- `logging`

Supported `content_selection.mode` values:

- `chapter_text_only`
- `canonical_from_epub_config`
- `all_readable`
- `chapters_only`
- `custom`

## Output Summary

Successful results contain:

- `schema_version: "stanza_annotator.v2.0"`
- `status: "succeeded"`
- `document`
- `diagnostics`
- `annotation`

Failed results contain:

- `schema_version: "stanza_annotator.v2.0"`
- `status: "failed"`
- `error`
- `diagnostics`
- `annotation`

By default the module annotates only `book.chapters[].text`. `chapters[].paragraphs` is not a supported upstream v3.0 production field and is not emitted in output.

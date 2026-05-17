# stanza_annotator — Testing Guide v2.0

This guide defines automation-ready contract tests for `stanza_annotator.v2.0` aligned with `epub_content_extractor.v3.0`.

The central regression gate is:

```text
chapters[].paragraphs is not an upstream v3.0 production field and MUST NOT be used as an annotation source or emitted in stanza_annotator output.
```

Default annotation target:

```text
book.chapters[].text
```

## 1. Test environment and fake adapter

All API/unit tests MUST use constructor injection:

```python
annotator = StanzaAnnotator(adapter=fake_adapter, clock=fixed_clock, annotator_version="2.0.0")
```

Tests MUST NOT download Stanza models, instantiate the production Stanza adapter, perform network calls, or monkey-patch private globals.

Required fake adapter protocol:

```python
class FakeBatchAdapter:
    def __init__(self):
        self.calls = []

    def annotate_batch(self, texts):
        self.calls.append(list(texts))
        return [make_raw_document(text) for text in texts]
```

Required assertions for every adapter-based test:

- The annotator calls `annotate_batch()`, not per-text `annotate()`.
- Every call length satisfies `1 <= len(call) <= batch_size`.
- Skipped text units are not present in adapter calls.
- Returned documents map back to selected text units by original order.

## 2. Fixture layout

Committed fixture layout:

```text
docs/testing/fixtures/input/*.json
docs/testing/fixtures/input/invalid/*.json
docs/testing/fixtures/config/*.json
docs/testing/fixtures/expected/*.normalized.json
docs/testing/fixtures/adapter/*.json
```

Mandatory baseline fixtures:

| Fixture | Purpose |
|---|---|
| `input/minimal_success_epub_result.json` | one valid chapter with `chapter.text` |
| `input/complex_batch_epub_result.json` | five chapters plus one front-matter section |
| `input/empty_chapter_text_epub_result.json` | defensive empty selected text-unit case |
| `input/limit_boundary_10_exact_epub_result.json` | `chapter.text` length exactly 10 for inclusive limit test |
| `input/limit_boundary_10_over_epub_result.json` | `chapter.text` length 11 for over-limit skip test |
| `input/sensitive_strings_epub_result.json` | exact sensitive strings for diagnostics/stderr/debug redaction tests |
| `input/future_upstream_schema_epub_result.json` | future unsupported upstream version `epub_content_extractor.v4.0` |
| `input/unsupported_upstream_schema.json` | unsupported upstream version |
| `input/upstream_failed_result.json` | failed upstream extractor result |
| `input/invalid/chapter_paragraphs.invalid.json` | forbidden stale upstream field |
| `config/default_minimal.json` | `{}` |
| `config/batch_size_2.json` | partial user config with only `batch_size` |
| `config/max_text_unit_chars_10.json` | partial user config with `max_text_unit_chars = 10` |
| `config/custom_front_matter_section_text.json` | custom section-text-only selection |
| `expected/minimal_success_output.normalized.json` | default success golden |
| `expected/empty_chapter_text_skipped_output.normalized.json` | empty selected text skipped golden |
| `expected/limit_boundary_10_exact_output.normalized.json` | exact-at-limit annotation golden |
| `expected/limit_boundary_10_over_skipped_output.normalized.json` | over-limit skipped golden |
| `expected/minimal_failed_unsupported_upstream.normalized.json` | unsupported upstream golden |
| `expected/minimal_failed_upstream_failed.normalized.json` | failed upstream golden |
| `expected/minimal_failed_invalid_config.normalized.json` | invalid config golden |

## 3. Snapshot normalization

Golden-output snapshots may normalize only:

```text
annotation.started_at
annotation.finished_at
annotation.duration_ms
```

Use schema-valid sentinel values:

```json
{
  "annotation.started_at": "2000-01-01T00:00:00Z",
  "annotation.finished_at": "2000-01-01T00:00:00Z",
  "annotation.duration_ms": 0
}
```

Do not normalize IDs, text, sentence/token offsets, counts, diagnostics, adapter call order, selected text-unit order, fingerprints, `stanza_version`, `annotator_version`, or config values. Tests SHOULD use fixed fake providers for version, model identity, clock, and fingerprints.

## 4. Contract test matrix

| ID | Area | Purpose | Priority | Fixture / exact source |
|---|---|---|---:|---|
| TC-P0-001 | Config | Empty user config `{}` validates | P0 | `config/default_minimal.json` |
| TC-P0-002 | Config | Partial `{"batch_size": 2}` validates | P0 | `config/batch_size_2.json` |
| TC-P0-003 | Schema | Output schema rejects `document.book.chapters[].paragraphs` | P0 | mutate `expected/minimal_success_output.normalized.json` |
| TC-P0-004 | Schema | Output schema rejects annotation fields inside paragraph objects | P0 | mutate front/back paragraph object |
| TC-P0-005 | API | Fake adapter constructor injection works | P0 | `input/minimal_success_epub_result.json` + `{}` |
| TC-P0-006 | Input | Empty selected `chapter.text` is skipped, not invalid | P0 | `input/empty_chapter_text_epub_result.json` |
| TC-P0-007 | Batch | `batch_size = 2` with five chapters makes calls `[2,2,1]` | P0 | `input/complex_batch_epub_result.json` + `config/batch_size_2.json` |
| TC-P0-008 | Input | Upstream `chapters[].paragraphs` is rejected before adapter call | P0 | `input/invalid/chapter_paragraphs.invalid.json` |
| TC-P0-009 | Runtime | Adapter exception maps to `stanza_runtime_failed` | P0 | fake raising adapter |
| TC-P0-010 | Runtime | Adapter batch length mismatch maps to `stanza_runtime_failed` | P0 | fake bad adapter |
| TC-P1-001 | CLI | Success without `--output` writes JSON to stdout | P1 | minimal input |
| TC-P1-002 | CLI | Invalid config exits `4` and emits failed JSON when output channel available | P1 | `config/invalid_unknown_field.json` |
| TC-P1-003 | CLI/FS | Output write failure exits `3` and does not fall back to stdout | P1 | unwritable/symlink output path |
| TC-P1-004 | Selection | Custom front-matter section text is annotated as one `section_text` unit | P1 | `complex_batch_epub_result.json` + custom config |
| TC-P1-005 | Limits | `len(text) == max_text_unit_chars` is accepted | P1 | `input/limit_boundary_10_exact_epub_result.json` + `config/max_text_unit_chars_10.json` |
| TC-P1-006 | Limits | `len(text) == max_text_unit_chars + 1` is skipped | P1 | `input/limit_boundary_10_over_epub_result.json` + `config/max_text_unit_chars_10.json` |
| TC-P1-007 | Determinism | Repeat normalized output is byte-identical | P1 | minimal input with fixed providers |
| TC-P1-008 | Security | Diagnostics/stderr/debug redact full text, paths, credentials | P1 | `input/sensitive_strings_epub_result.json` |
| TC-P1-009 | Versioning | Future upstream `epub_content_extractor.v4.0` rejected | P1 | `input/future_upstream_schema_epub_result.json` |
| TC-P1-010 | Upstream failure | Failed upstream extractor result maps to stanza failed result | P1 | `input/upstream_failed_result.json` |
| TC-P1-011 | Selection | Custom selection with all booleans false fails `no_annotatable_text` | P1 | `input/minimal_success_epub_result.json` + `config/custom_selects_nothing.json` |
| TC-P1-012 | Limits | Serialized output larger than `max_output_json_bytes` fails `output_too_large` | P1 | minimal input + test-only tiny output-size limit harness |
| TC-P1-013 | Runtime | Unexpected implementation defect maps to `internal_error` when structured result is possible | P1 | fault-injection harness |
| TC-P1-014 | Runtime | Production model unavailable maps to `stanza_model_unavailable` | P1 | production-adapter fault-injection or adapter factory stub |

## 5. P0 exact test specifications

### TC-P0-001 user_config_empty_object_validates

Input: `docs/testing/fixtures/config/default_minimal.json` containing `{}`.

Steps: validate against `docs/architecture/schema/stanza_annotator_config.v2.0.schema.json`.

Expected: validation succeeds. Fails if root `language` or any defaulted field is required in user config.

### TC-P0-002 user_config_partial_batch_size_validates

Input: `docs/testing/fixtures/config/batch_size_2.json`.

Expected: validation succeeds and effective config materializes `language`, `processors`, `content_selection`, `logging`, and all defaults in `annotation.config`.

### TC-P0-003 output_schema_rejects_chapter_paragraphs

Input: start from `expected/minimal_success_output.normalized.json` and add:

```json
{"document": {"book": {"chapters": [{"paragraphs": [{"text": "x"}]}]}}}
```

Expected: validation against `stanza_annotator.v2.0.schema.json` fails under `/document/book/chapters/0`.

### TC-P0-004 output_schema_rejects_paragraph_annotation_fields

Input: create or mutate a success output with one front/back section paragraph and add any of:

```text
annotation_status
skipped_reason
annotation
text_annotation_status
text_skipped_reason
text_annotation
title_annotation_status
title_skipped_reason
title_annotation
```

Expected: validation against `stanza_annotator.v2.0.schema.json` fails under the paragraph object. Plain `{ "text": "..." }` still validates.

### TC-P0-005 fake_adapter_constructor_injection

Input: `input/minimal_success_epub_result.json`, config `{}`.

Expected:

```python
assert result["status"] == "succeeded"
assert fake_adapter.calls == [["Alice sees Bob."]]
chapter = result["document"]["book"]["chapters"][0]
assert "paragraphs" not in chapter
assert chapter["text_annotation_status"] == "annotated"
assert chapter["text_annotation"]["ref"]["kind"] == "chapter_text"
assert chapter["text_annotation"]["ref"]["text_unit_id"] == "chapter_001:text"
assert chapter["text_annotation"]["text"] == "Alice sees Bob."
```

The normalized result must equal `expected/minimal_success_output.normalized.json` and validate against output schema.

### TC-P0-006 empty_chapter_text_is_skipped

Input: `input/empty_chapter_text_epub_result.json`, config `{}`.

Expected normalized output: `expected/empty_chapter_text_skipped_output.normalized.json`.

Required assertions:

```python
assert fake_adapter.calls == []
chapter = result["document"]["book"]["chapters"][0]
assert chapter["text"] == ""
assert chapter["text_annotation_status"] == "skipped"
assert chapter["text_skipped_reason"] == "empty_text"
assert "text_annotation" not in chapter
assert result["diagnostics"][0]["code"] == "text_unit_empty"
assert result["diagnostics"][0]["entity_type"] == "text_unit"
assert result["diagnostics"][0]["entity_id"] == "chapter_001:text"
assert result["annotation"]["summary"]["text_unit_count"] == 1
assert result["annotation"]["summary"]["annotated_text_unit_count"] == 0
assert result["annotation"]["summary"]["skipped_text_unit_count"] == 1
```

### TC-P0-007 batch_size_2_five_chapters

Input: `input/complex_batch_epub_result.json`, config `config/batch_size_2.json`.

Expected:

```python
assert fake_adapter.calls == [
    ["Text 1.", "Text 2."],
    ["Text 3.", "Text 4."],
    ["Text 5."]
]
for index, chapter in enumerate(result["document"]["book"]["chapters"], start=1):
    assert chapter["text_annotation"]["text"] == f"Text {index}."
    assert chapter["text_annotation"]["text_unit_id"] == f"chapter_{index:03d}:text"
    assert "paragraphs" not in chapter
```

### TC-P0-008 chapter_paragraphs_rejected

Input: `input/invalid/chapter_paragraphs.invalid.json`.

Expected:

- consumed-boundary schema validation fails before adapter call; or API boundary returns `status = "failed"`, `error.code = "invalid_input"`;
- `fake_adapter.calls == []`;
- no production `document` is emitted.

### TC-P0-009 adapter_exception_fails_result

Fake adapter:

```python
class RaisingBatchAdapter:
    def annotate_batch(self, texts):
        raise RuntimeError("synthetic adapter failure: SECRET_TOKEN must not leak")
```

Expected:

- `status = "failed"`;
- `error.code = "stanza_runtime_failed"`;
- `document` absent;
- at least one diagnostic has `entity_type = "stanza_runtime"`;
- diagnostics and stderr do not contain `SECRET_TOKEN` or full submitted text.

### TC-P0-010 batch_length_mismatch_fails_result

Fake adapter:

```python
class BadBatchAdapter:
    def annotate_batch(self, texts):
        return []
```

Expected:

- `status = "failed"`;
- `error.code = "stanza_runtime_failed"`;
- `document` absent;
- diagnostic `entity_type = "stanza_runtime"`;
- no partial production annotations.

## 6. P1 exact test specifications

### TC-P1-001 CLI success stdout JSON

Command:

```bash
stanza-annotator annotate docs/testing/fixtures/input/minimal_success_epub_result.json --config docs/testing/fixtures/config/default_minimal.json
```

Expected: exit `0`; stdout is valid JSON `status = "succeeded"`; stderr empty by default.

### TC-P1-002 CLI invalid config

Command uses `config/invalid_unknown_field.json`.

Expected: exit `4`; selected output channel contains failed JSON with `error.code = "invalid_config"`; adapter not called.

### TC-P1-003 output write failure

Portable required command uses `--output` pointing to an existing directory, for example:

```bash
mkdir -p tmp/out_dir
stanza-annotator annotate docs/testing/fixtures/input/minimal_success_epub_result.json --output tmp/out_dir
```

Expected: exit `3`; stdout empty; no fallback JSON; stderr contains a concise redacted filesystem error category but not the full input text; the directory is not replaced; no partial JSON file is created; same-directory temp files created by the CLI are cleaned when possible.

Platform policy:

- Directory-as-output is the required cross-platform assertion.
- Symlink-output tests are optional security tests. They MUST be skipped on Windows or CI environments without symlink privileges.
- Unwritable-permission tests are optional and MUST be skipped or xfailed when the test process has elevated privileges that make permission denial unreliable.

### TC-P1-004 custom front matter section text

Input: `complex_batch_epub_result.json`, config `custom_front_matter_section_text.json`.

Expected:

```python
assert fake_adapter.calls == [["Before the story."]]
section = result["document"]["book"]["front_matter"][0]
assert section["text_annotation"]["ref"]["kind"] == "section_text"
assert section["text_annotation"]["text"] == "Before the story."
assert "annotation" not in section["paragraphs"][0]
for chapter in result["document"]["book"]["chapters"]:
    assert chapter["text_annotation_status"] == "skipped"
    assert chapter["text_skipped_reason"] == "excluded_by_config"
```

### TC-P1-005 max_text_unit_chars inclusive boundary

Input: `input/limit_boundary_10_exact_epub_result.json`, config `config/max_text_unit_chars_10.json`.

Exact fixture content requirement:

```json
{
  "book": {
    "chapters": [
      { "id": "chapter_001", "text": "abcdefghij" }
    ]
  }
}
```

Expected normalized output: `expected/limit_boundary_10_exact_output.normalized.json`.

Required assertions:

```python
assert len("abcdefghij") == 10
assert fake_adapter.calls == [["abcdefghij"]]
assert result["document"]["book"]["chapters"][0]["text_annotation_status"] == "annotated"
assert result["diagnostics"] == []
```

### TC-P1-006 max_text_unit_chars plus one skipped

Input: `input/limit_boundary_10_over_epub_result.json`, config `config/max_text_unit_chars_10.json`.

Exact fixture content requirement:

```json
{
  "book": {
    "chapters": [
      { "id": "chapter_001", "text": "abcdefghijk" }
    ]
  }
}
```

Expected normalized output: `expected/limit_boundary_10_over_skipped_output.normalized.json`.

Required assertions:

```python
assert len("abcdefghijk") == 11
assert fake_adapter.calls == []
chapter = result["document"]["book"]["chapters"][0]
assert chapter["text_annotation_status"] == "skipped"
assert chapter["text_skipped_reason"] == "too_large"
assert result["diagnostics"][0]["code"] == "text_unit_too_large"
assert result["diagnostics"][0]["entity_type"] == "text_unit"
assert result["diagnostics"][0]["entity_id"] == "chapter_001:text"
assert result["diagnostics"][0]["field"] == "text"
```

### TC-P1-007 determinism

Two runs with fixed fake adapter, fixed clock, fixed versions, and fixed fingerprint provider must produce byte-identical normalized JSON. `batch_size` changes call grouping only and MUST NOT change production annotations or fingerprints.

### TC-P1-008 privacy

Input: `input/sensitive_strings_epub_result.json`.

Exact sensitive strings in the fixture:

```text
alice@example.com
sk-SECRET123456789
C:\Users\Alice\secret.txt
```

Required assertions:

```python
serialized_result = json.dumps(result, ensure_ascii=False)
assert "alice@example.com" not in diagnostics_json
assert "sk-SECRET123456789" not in diagnostics_json
assert "C:\\Users\\Alice\\secret.txt" not in diagnostics_json
assert "alice@example.com" not in stderr
assert "sk-SECRET123456789" not in stderr
assert "C:\\Users\\Alice\\secret.txt" not in stderr
if "debug" in result:
    debug_json = json.dumps(result["debug"], ensure_ascii=False)
    assert "alice@example.com" not in debug_json
    assert "sk-SECRET123456789" not in debug_json
    assert "C:\\Users\\Alice\\secret.txt" not in debug_json
```

Allowed redaction placeholders include `[REDACTED_EMAIL]`, `[REDACTED_TOKEN]`, and `[REDACTED_PATH]`. Production annotation text may still contain the source text because the annotated document is the requested output; the no-leak assertion applies to diagnostics, stderr, logs, and debug previews.

### TC-P1-009 future upstream version rejected

Input: `input/future_upstream_schema_epub_result.json`, whose `schema_version` is exactly `epub_content_extractor.v4.0`.

Expected: failed `unsupported_upstream_schema`; adapter not called; CLI exit `1`.

### TC-P1-010 upstream failed input

Input: `input/upstream_failed_result.json`.

Expected normalized output: `expected/minimal_failed_upstream_failed.normalized.json`; adapter not called; CLI exit `1`; no production `document` is emitted.

### TC-P1-011 no annotatable text from custom selection

Input: `input/minimal_success_epub_result.json`, config `config/custom_selects_nothing.json`.

Expected: failed result with `error.code = "no_annotatable_text"`; adapter not called; CLI exit `1`; no production `document` is emitted.

### TC-P1-012 output too large

Use a test-only harness that sets `max_output_json_bytes` lower than the serialized result size after the effective config is built. Because the public user config schema has minimum `1024`, a unit test may use a schema-valid small output fixture that still exceeds `1024` bytes or may inject the output-size checker directly.

Expected: failed result with `error.code = "output_too_large"`; CLI exit `1` when the failed result can be written; no partial production annotations.

### TC-P1-013 internal error fault injection

Use an implementation fault-injection harness outside normal domain failures.

Expected: `error.code = "internal_error"`; CLI exit `99` if invoked through CLI and result construction is possible; diagnostics must not leak full text or local paths.

### TC-P1-014 production model unavailable

Use a production-adapter factory stub that simulates model load/download failure after config and input validation.

Expected: `error.code = "stanza_model_unavailable"`; adapter text units are not submitted; CLI exit `1`; diagnostics and stderr contain no full text.

## 7. Schema-validation tests

Generated tests MUST validate:

- all schemas parse as Draft 2020-12 schemas;
- `default_minimal.json`, `batch_size_2.json`, and `custom_front_matter_section_text.json` validate as user configs;
- `invalid_unknown_field.json` fails because of unknown field only;
- `invalid_batch_size_zero.json` fails because `batch_size < 1` only;
- effective config snapshots in expected outputs contain all defaults;
- successful and failed expected outputs validate against `stanza_annotator.v2.0.schema.json`;
- diagnostic objects validate against `stanza_annotator_diagnostics.v2.0.schema.json`;
- `stanza_annotator_errors.v2.0.json` contains every `StanzaAnnotationError.code` enum value exactly once;
- consumed upstream valid fixtures validate against `upstream/epub_content_extractor.v3.0.required-subset.schema.json`;
- `input/limit_boundary_10_exact_epub_result.json`, `input/limit_boundary_10_over_epub_result.json`, and `input/sensitive_strings_epub_result.json` validate as consumed upstream inputs;
- `input/future_upstream_schema_epub_result.json` is rejected by the schema-version gate before full consumed-boundary validation;
- `input/invalid/chapter_paragraphs.invalid.json` fails consumed-boundary validation;
- a success output mutated with `document.book.chapters[0].paragraphs` fails output-schema validation;
- a success output mutated with paragraph `annotation_status` or `annotation` fails output-schema validation.

## 8. Property-based tests

Property-based tests SHOULD generate random valid upstream v3.0 books with chapters and optional front/back matter.

Required properties:

```text
no chapter output contains a paragraphs field
no paragraph object contains annotation_status/skipped_reason/annotation/text_annotation/title_annotation
no TextUnitRef.kind equals paragraph
all default-selected text units come from chapters[].text
adapter call texts equal selected non-skipped source fields in order
batch call sizes are within 1..batch_size
all emitted TextUnitAnnotation.text values equal source text unit values
all sentence/token/entity offsets are inside the local TextUnitAnnotation.text
annotation summary counts equal emitted annotations and represented skipped units
include_debug does not change production output after removing top-level debug and timestamps
```

## 9. Release acceptance checklist

A documentation/schema release is invalid if any of the following is true:

- Any example or fixture requires `chapters[].paragraphs`.
- Any default-mode test expects paragraph-level annotation.
- Output schema allows `document.book.chapters[].paragraphs`.
- Output schema allows annotation fields inside paragraph objects.
- `TextUnitRef.kind` enum includes `paragraph`.
- User config schema rejects `{}` or `{"batch_size": 2}`.
- Batch behavior cannot be verified with `StanzaAnnotator(adapter=fake_adapter)`.
- `batch_size` is missing from the config schema or effective config snapshot.
- Upstream consumed-boundary schema still accepts `epub_content_extractor.v2.2` as the supported production input.
- Default config annotates titles, footnotes, front matter, or back matter instead of only `chapters[].text`.
- CLI `--output` behavior, invalid config exit `4`, or output write failure exit `3` is unspecified.

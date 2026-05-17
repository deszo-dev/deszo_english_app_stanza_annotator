# stanza_annotator — Architecture and Contract v2.0

`stanza_annotator` receives a structured result from `epub_content_extractor` and attaches Stanza annotations to selected **text units** while preserving the upstream EPUB book structure.

This contract is aligned with `epub_content_extractor.v3.0`. In that upstream contract, `chapters[].paragraphs` is not part of production output. The authoritative main-content field is `chapters[].text`. Therefore `stanza_annotator` MUST NOT depend on, generate, copy, or annotate `chapters[].paragraphs`.

## 1. Normative artifact set

The documentation package MUST contain these public contract artifacts:

```text
docs/architecture/stanza_annotator_architecture.md
docs/testing/stanza_annotator_testing.md
docs/architecture/schema/stanza_annotator.v2.0.schema.json
docs/architecture/schema/stanza_annotator_config.v2.0.schema.json
docs/architecture/schema/stanza_annotator_diagnostics.v2.0.schema.json
docs/architecture/schema/stanza_annotator_errors.v2.0.json
docs/architecture/schema/upstream/epub_content_extractor.v3.0.required-subset.schema.json
```

Schemas are normative for machine validation. This Markdown document is normative for behavior not fully expressible in JSON Schema, especially adapter injection, batching, source selection, provenance, filesystem behavior, failure precedence, and versioning.

The files under `docs/guidelines/**` are inherited only as non-normative engineering guidance. If a guideline conflicts with this module contract, this module contract wins.

## 2. Scope and non-goals

The module is a downstream NLP projection layer. It does not parse EPUB files and does not repair upstream extraction output.

In scope:

- validate a consumed subset of `epub_content_extractor.v3.0` output;
- select text units from `chapter.text`, optional titles, optional section text, and optional footnote text;
- run Stanza through a project-owned batch adapter;
- attach annotations back to the structured book without flattening the document;
- emit deterministic summaries, diagnostics, provenance, and fingerprints.

Out of scope:

- EPUB archive parsing, HTML parsing, cleanup, OCR, or chapter segmentation;
- reconstruction of `chapters[].paragraphs`;
- paragraph-level annotation for chapter body text;
- mutation of the upstream input object;
- per-text-unit runtime partial-failure output in v2.0;
- real model download or network access in tests.

The production adapter MAY download missing Stanza models only when `auto_download = true`. Unit and CLI contract tests MUST use an injected fake adapter and MUST NOT download models.

## 3. Supported upstream input

The only supported upstream production input is a JSON-compatible object that validates against `docs/architecture/schema/upstream/epub_content_extractor.v3.0.required-subset.schema.json`. The minimal shape below is intentionally schema-valid, not an abridged placeholder:

```json
{
  "schema_version": "epub_content_extractor.v3.0",
  "status": "succeeded",
  "book": {
    "title": null,
    "subtitle": null,
    "language": "en",
    "authors": [],
    "contributors": [],
    "metadata": {
      "source_file": {
        "file_name": "demo.epub",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "size_bytes": 1000,
        "epub_version": "3.0"
      }
    },
    "front_matter": [],
    "chapters": [
      {
        "id": "chapter_001",
        "chapter_number": 1,
        "type": "chapter",
        "text": "Alice sees Bob.",
        "footnotes": []
      }
    ],
    "back_matter": [],
    "footnotes": [],
    "table_of_contents": [],
    "assets": []
  },
  "diagnostics": [],
  "extraction": {
    "extractor_version": "3.0.0",
    "config": {
      "include_front_matter_in_canonical_text": false,
      "include_back_matter_in_canonical_text": false,
      "include_footnotes_in_canonical_text": false,
      "include_chapter_titles_in_canonical_text": true,
      "include_section_titles_in_canonical_text": false
    },
    "summary": {
      "chapter_count": 1,
      "front_matter_section_count": 0,
      "back_matter_section_count": 0,
      "paragraph_count": 0,
      "footnote_count": 0,
      "total_text_chars": 15,
      "canonical_text_chars": 28,
      "removed_section_count": 0,
      "warning_count": 0,
      "error_count": 0
    }
  }
}
```

`stanza_annotator` does not synthesize missing upstream structural fields such as `chapter_number`, `chapter.type`, `chapter.footnotes`, `section.type`, `section.footnotes`, or `section.included_in_canonical_text`. If those fields are absent, the input fails the consumed-boundary schema with `invalid_input`.

Rules:

- `schema_version` MUST be exactly `epub_content_extractor.v3.0`.
- `status = "failed"` maps to top-level `error.code = "upstream_epub_extraction_failed"`.
- Unsupported or missing upstream schema version maps to `error.code = "unsupported_upstream_schema"`.
- Upstream `book.language` MUST be `"en"`.
- `book.chapters[].text` is the only default annotation source for main content.
- Required upstream structural fields are copied through, not defaulted. Missing required upstream fields are `invalid_input`; the module MUST NOT infer `chapter_number`, default `type`, or synthesize `footnotes = []` for schema-invalid consumed input.
- `book.chapters[].paragraphs` MUST be rejected if present in production input because the upstream v3.0 production schema removed it.
- Front/back matter `section.paragraphs[]` may exist in upstream v3.0 and may be copied through for structural preservation, but paragraph objects are not annotation targets.
- The consumed-boundary schema intentionally accepts empty strings in selectable fields such as `chapter.text`, `section.text`, and `footnote.text`. Empty selected text units are skipped with diagnostic `text_unit_empty`; they are not `invalid_input`.
- Duplicate chapter, section, or footnote ids are `invalid_input` because deterministic text-unit ids and annotation refs would become ambiguous.
- `metadata.source_file.file_name`, when present in consumed input, MUST be a basename only. Absolute paths, parent traversal, slash/backslash separators, and control characters are `invalid_input` with diagnostic `invalid_source_file_name`.

Validation order:

1. Validate user config.
2. Apply defaults to create the effective config snapshot.
3. Check upstream `schema_version` and failed-upstream status.
4. Validate supported upstream shape against `docs/architecture/schema/upstream/epub_content_extractor.v3.0.required-subset.schema.json`.
5. Validate deterministic id uniqueness and source-file basename safety.
6. Select text units.
7. Skip empty/oversized selected units.
8. Call the adapter only for selected non-skipped units.

## 4. Public API

```python
from stanza_annotator import StanzaAnnotator

class StanzaAnnotator:
    def __init__(
        self,
        adapter: StanzaAdapterProtocol | None = None,
        *,
        clock: ClockProtocol | None = None,
        annotator_version: str | None = None,
    ) -> None: ...

    def annotate_epub_result(
        self,
        epub_result: dict,
        config: dict | None = None,
    ) -> dict: ...
```

Rules:

- If `adapter` is provided, all selected non-skipped text units MUST be submitted through that adapter's `annotate_batch()` method.
- If `adapter` is omitted, the production adapter MAY be created lazily only after config and upstream input validation succeed.
- The constructor MUST NOT download models, read input files, write files, inspect EPUB content, or run annotation.
- `clock` is optional and exists only to make `annotation.started_at`, `annotation.finished_at`, and `annotation.duration_ms` deterministic in tests.
- `annotator_version` is an optional test override for emitted metadata. Production code SHOULD default to the installed package version.
- The public method MUST NOT mutate `epub_result` or `config`.
- Returned results are caller-owned JSON-compatible dictionaries.
- Normal documented config, input, upstream, and Stanza runtime failures return structured failed `StanzaAnnotationResult` objects and MUST NOT raise.
- `TypeError` MAY be raised only for Python programmer misuse that cannot reasonably be represented as JSON-compatible input, such as a non-mapping `config` object.
- Instances are not guaranteed thread-safe unless the injected adapter is thread-safe. Concurrent callers SHOULD use separate annotator instances.

Tests MUST instantiate `StanzaAnnotator(adapter=fake_adapter)` and MUST NOT monkey-patch private globals to verify batching.

## 5. Failure policy and error registry

Top-level error codes are stable public contract within `stanza_annotator.v2.0`. The machine-readable registry is:

```text
docs/architecture/schema/stanza_annotator_errors.v2.0.json
```

| Condition | Error code | API result | CLI exit |
|---|---|---|---:|
| Config violates `stanza_annotator_config.v2.0.schema.json` | `invalid_config` | `failed` | 4 |
| Input is not a supported JSON-compatible upstream result | `invalid_input` | `failed` | 1 |
| Upstream schema is not `epub_content_extractor.v3.0` | `unsupported_upstream_schema` | `failed` | 1 |
| Upstream result has `status = "failed"` | `upstream_epub_extraction_failed` | `failed` | 1 |
| Effective selection selects zero text units before empty/size checks | `no_annotatable_text` | `failed` | 1 |
| Stanza model cannot be loaded or downloaded | `stanza_model_unavailable` | `failed` | 1 |
| Adapter raises, returns invalid documents, or returns wrong batch length | `stanza_runtime_failed` | `failed` | 1 |
| Serialized result exceeds `max_output_json_bytes` | `output_too_large` | `failed` | 1 |
| CLI selected output destination cannot be written | `output_write_failed` | normally not serialized | 3 |
| Unexpected implementation defect | `internal_error` | `failed` if possible | 99 |

Rules:

- `recoverable` MUST be `false` for every v2.0 top-level error.
- Failed results MUST include `annotation.summary` with zero production counts except `error_count`, unless a later stage accumulated diagnostics before failing.
- If selected text units exist but all are skipped only because they are empty or too large, the result is still `succeeded` with `annotated_text_unit_count = 0` and `skipped_text_unit_count > 0`.
- Adapter exception and batch length mismatch MUST emit a diagnostic with `entity_type = "stanza_runtime"` and MUST NOT include full text-unit text.

## 6. Configuration

The canonical user config schema is:

```text
docs/architecture/schema/stanza_annotator_config.v2.0.schema.json
```

### 6.1 User config versus effective config snapshot

The user-supplied config accepted by API and CLI is a **partial override object**. It MAY be `{}`. `stanza_annotator_config.v2.0.schema.json` validates this partial override object.

The emitted `annotation.config` is the fully materialized effective config snapshot. It MUST contain every defaulted field and MUST validate against `StanzaAnnotationResult.$defs.EffectiveStanzaAnnotatorConfigSnapshot` in `stanza_annotator.v2.0.schema.json`.

Processing order:

1. Treat missing config as `{}`.
2. Validate the user config override against `stanza_annotator_config.v2.0.schema.json`.
3. Reject unknown properties before running annotation.
4. Apply defaults to create the effective config snapshot.
5. Use only the effective config for selection, batching, limits, output metadata, and fingerprinting.

Default effective config:

```json
{
  "language": "en",
  "processors": "tokenize,mwt,pos,lemma,depparse,ner",
  "use_gpu": false,
  "tokenize_pretokenized": false,
  "auto_download": true,
  "content_selection": {
    "mode": "chapter_text_only",
    "include_chapters": false,
    "include_front_matter": false,
    "include_back_matter": false,
    "include_footnotes": false,
    "include_chapter_titles": false,
    "include_section_titles": false
  },
  "batch_size": 32,
  "max_text_unit_chars": 100000,
  "max_output_json_bytes": 1073741824,
  "include_debug": false,
  "logging": {
    "enabled": false,
    "level": "info"
  }
}
```

Rules:

- `language` is fixed to `"en"`.
- `tokenize_pretokenized` is fixed to `false` because the module passes raw text units to Stanza.
- `content_selection: {}` is valid user config and defaults to `mode = "chapter_text_only"`.
- For user config `content_selection.mode = "custom"`, all six include booleans MUST be present.
- `batch_size` controls the maximum number of selected text units passed to one adapter batch call.
- `include_debug` MUST NOT change production fields, annotations, counts, diagnostics, fingerprints, selection order, or batching behavior.
- CLI `--include-debug` overrides user config and sets effective `include_debug = true` for that invocation.
- `debug_dir` is CLI-only and MUST NOT appear in user config or `annotation.config`.

## 7. Deterministic content selection

A **text unit** is a whole source field selected for annotation. A text unit is never a chapter paragraph.

Supported text-unit kinds:

| Kind | Source field | Default selected? | Stable ID example |
|---|---|---:|---|
| `chapter_text` | `book.chapters[].text` | yes | `chapter_001:text` |
| `chapter_title` | `book.chapters[].title` | no | `chapter_001:title` |
| `section_text` | `front_matter[].text` / `back_matter[].text` | no | `front_001:text` |
| `section_title` | `front_matter[].title` / `back_matter[].title` | no | `front_001:title` |
| `footnote` | `footnotes[].text` at book/chapter/section level | no | `footnote_001` |

The annotator builds candidates in this deterministic order:

1. Front matter sections in array order:
   1. section title when selected;
   2. section text when selected;
   3. section footnotes in array order when footnotes are selected.
2. Chapters in array order:
   1. chapter title when selected;
   2. chapter text when selected;
   3. chapter footnotes in array order when footnotes are selected.
3. Back matter sections in array order using the same ordering as front matter.
4. Book-level footnotes in array order when footnotes are selected.

Selection by mode:

| Mode | Selected source fields | Config booleans used |
|---|---|---|
| `chapter_text_only` | `chapters[].text` only | none; include booleans ignored |
| `chapters_only` | `chapters[].text`; plus `chapters[].title` only if `include_chapter_titles = true` | `include_chapter_titles` |
| `canonical_from_epub_config` | `chapters[].text`; front/back section text and footnotes according to upstream `extraction.config`; titles according to upstream title flags | upstream canonical config only |
| `all_readable` | chapter text, front/back section text, selected titles, and all footnotes | `include_chapter_titles`, `include_section_titles`; other include booleans ignored |
| `custom` | exactly the fields enabled by explicit include booleans | all include booleans |

`canonical_from_epub_config` mapping:

| Upstream extractor config field | Selected stanza text units |
|---|---|
| always | `chapters[].text` |
| `include_front_matter_in_canonical_text = true` | `front_matter[].text` |
| `include_back_matter_in_canonical_text = true` | `back_matter[].text` |
| `include_footnotes_in_canonical_text = true` | all book/chapter/section footnotes |
| `include_chapter_titles_in_canonical_text = true` | `chapters[].title` |
| `include_section_titles_in_canonical_text = true` | selected front/back section titles |

Rules:

- Default annotation MUST annotate only `chapters[].text`.
- Front/back matter paragraphs are never individual text units.
- For front/back matter, annotation may target `section.text` as a whole only when selected by config.
- Footnotes may be annotated as footnote text units when selected.
- Titles may be annotated as title text units when selected.
- For `custom`, if all include booleans are `false`, selection produces zero text units and the result fails with `error.code = "no_annotatable_text"`.
- If no text units exist after applying selection rules but before empty/size checks, the result fails with `no_annotatable_text`.
- If a selected text unit is empty, it is represented as skipped when the owning output object has a status field for that unit, emits diagnostic `text_unit_empty`, and is not submitted to the adapter.
- If a selected text unit exceeds `max_text_unit_chars`, it is represented as skipped when possible, emits diagnostic `text_unit_too_large`, and is not submitted to the adapter.

## 8. Batch annotation requirement

The implementation MUST use batch annotation for selected text units.

Project-owned adapter protocol:

```python
from dataclasses import dataclass, field
from typing import Protocol, Sequence

@dataclass(frozen=True)
class RawStanzaWord:
    text: str
    lemma: str
    upos: str
    deprel: str
    head: int
    start_char: int
    end_char: int
    xpos: str | None = None
    feats: str | None = None

@dataclass(frozen=True)
class RawStanzaToken:
    text: str
    start_char: int
    end_char: int
    words: Sequence[RawStanzaWord]

@dataclass(frozen=True)
class RawStanzaSentence:
    text: str
    start_char: int
    end_char: int
    tokens: Sequence[RawStanzaToken]

@dataclass(frozen=True)
class RawStanzaEntity:
    text: str
    type: str
    start_char: int
    end_char: int

@dataclass(frozen=True)
class RawStanzaDocument:
    sentences: Sequence[RawStanzaSentence] = field(default_factory=list)
    entities: Sequence[RawStanzaEntity] = field(default_factory=list)

class StanzaAdapterProtocol(Protocol):
    def annotate_batch(self, texts: Sequence[str]) -> Sequence[RawStanzaDocument]:
        ...
```

Batch rules:

- The annotator MUST collect selected, non-skipped text units in deterministic reading order.
- The annotator MUST call `annotate_batch()` with chunks of size `1 <= len(texts) <= batch_size`.
- The real Stanza adapter SHOULD keep a single initialized `stanza.Pipeline` instance and process a list of texts/documents in one call when the installed Stanza version supports batch/list processing.
- If Stanza list processing is unavailable, the adapter may internally loop over the provided batch, but the public annotator still MUST use `annotate_batch()` so tests can verify batching behavior.
- The adapter MUST return exactly one `RawStanzaDocument` per input text, in the same order.
- A mismatched batch result length is a Stanza runtime failure and maps to `stanza_runtime_failed`.
- A runtime exception for any selected text unit in a batch fails the whole result with `stanza_runtime_failed`; v2.0 has no per-text-unit failed production status.
- Skipped text units are never sent to the adapter.

## 9. Output shape

Top-level result:

```typescript
type StanzaAnnotationStatus = "succeeded" | "failed";

interface StanzaAnnotationResult {
  schema_version: "stanza_annotator.v2.0";
  status: StanzaAnnotationStatus;
  document?: AnnotatedEpubDocument;
  error?: StanzaAnnotationError;
  diagnostics: StanzaAnnotationDiagnostic[];
  annotation: StanzaAnnotationInfo;
  debug?: StanzaDebugInfo;
}
```

Succeeded result rules:

- `document` is required.
- `error` is absent.
- `document.book.chapters[].paragraphs` MUST be absent and MUST be rejected by the output schema if present.
- `document.book.chapters[].text` is copied from upstream and may have `text_annotation` attached.
- Front/back `section.paragraphs[]` may be copied from upstream with documented structural fields, but those objects MUST NOT contain annotation fields such as `annotation_status`, `skipped_reason`, `annotation`, `text_annotation`, or `title_annotation`.
- There is no top-level flat `sentences[]` or `entities[]` array.

Failed result rules:

- `error` is required.
- `document` is absent.
- Partial production annotations are not emitted.
- Debug data may contain redacted troubleshooting details only when `include_debug = true`.

## 10. Annotated book model

```typescript
interface AnnotatedEpubDocument {
  source: StanzaAnnotationSource;
  book: AnnotatedEpubBook;
}

interface AnnotatedEpubChapter {
  id: string;
  chapter_number: number;
  type: string;
  title?: string;
  title_annotation_status?: "annotated" | "skipped";
  title_skipped_reason?: "excluded_by_config" | "empty_text" | "too_large";
  title_annotation?: TextUnitAnnotation;
  text: string;
  text_annotation_status: "annotated" | "skipped";
  text_skipped_reason?: "excluded_by_config" | "empty_text" | "too_large";
  text_annotation?: TextUnitAnnotation;
  footnotes: AnnotatedEpubFootnote[];
}

interface AnnotatedEpubSection {
  id: string;
  type: string;
  title?: string;
  title_annotation_status?: "annotated" | "skipped";
  title_skipped_reason?: "excluded_by_config" | "empty_text" | "too_large";
  title_annotation?: TextUnitAnnotation;
  text: string;
  text_annotation_status?: "annotated" | "skipped";
  text_skipped_reason?: "excluded_by_config" | "empty_text" | "too_large";
  text_annotation?: TextUnitAnnotation;
  paragraphs: EpubParagraph[];
  footnotes: AnnotatedEpubFootnote[];
  included_in_canonical_text: boolean;
}

interface EpubParagraph {
  id?: string;
  paragraph_number?: number;
  text: string;
}
```

Rules:

- `AnnotatedEpubChapter` has no `paragraphs` field.
- `text_annotation_status = "annotated"` requires `text_annotation` and forbids `text_skipped_reason`.
- `text_annotation_status = "skipped"` requires `text_skipped_reason` and forbids `text_annotation`.
- `title_annotation_status = "annotated"` requires `title_annotation` and forbids `title_skipped_reason`.
- `title_annotation_status = "skipped"` requires `title_skipped_reason` and forbids `title_annotation`.
- Section `text_annotation_status` is emitted only when section text is selected or explicitly represented as skipped.
- Section `paragraphs[]` are structural pass-through only and are never annotation targets.
- Unknown upstream fields in chapters and sections MAY be copied only if they do not conflict with the schema-level paragraph and annotation-field prohibitions.

## 11. Footnotes

```typescript
interface AnnotatedEpubFootnote {
  id: string;
  marker?: string;
  text: string;
  paragraph_number?: number;
  annotation_status: "annotated" | "skipped";
  skipped_reason?: "excluded_by_config" | "empty_text" | "too_large";
  annotation?: TextUnitAnnotation;
}
```

Rules:

- Footnotes keep upstream ownership.
- All emitted footnotes MUST carry `annotation_status`.
- Footnotes excluded by config are represented as `annotation_status = "skipped"` and `skipped_reason = "excluded_by_config"`.
- Selected empty/oversized footnotes are represented as skipped with `empty_text` or `too_large` respectively.
- `paragraph_number` may be copied when upstream provides an approximate owner link.
- `paragraph_number` is provenance only; it does not make paragraphs annotation targets.

## 12. Text unit annotation

```typescript
interface TextUnitAnnotation {
  text_unit_id: string;
  ref: TextUnitRef;
  text: string;
  sentences: AnnotatedSentence[];
  entities: AnnotatedEntity[];
  summary: TextUnitAnnotationSummary;
}

interface TextUnitRef {
  text_unit_id: string;
  kind: "chapter_text" | "section_text" | "chapter_title" | "section_title" | "footnote";
  owner_type: "chapter" | "front_matter" | "back_matter" | "book";
  owner_id: string;
  footnote_id?: string;
  source_field: "title" | "text";
}
```

Rules:

- `TextUnitAnnotation.text` MUST exactly equal the selected source field value after upstream text has been copied.
- Sentence/token/word/entity offsets are local to `TextUnitAnnotation.text`, not global book offsets.
- `TextUnitRef.kind = "paragraph"` is forbidden by schema and contract.
- Stable IDs MUST use `:text`, `:title`, or footnote ids; IDs like `chapter_001:p0001` are forbidden for chapter content.

## 13. Annotation summary

```typescript
interface StanzaAnnotationSummary {
  text_unit_count: number;
  annotated_text_unit_count: number;
  skipped_text_unit_count: number;
  chapter_count: number;
  front_matter_section_count: number;
  back_matter_section_count: number;
  paragraph_count: number;
  footnote_count: number;
  sentence_count: number;
  token_count: number;
  word_count: number;
  entity_count: number;
  warning_count: number;
  error_count: number;
}
```

Rules:

- `text_unit_count = annotated_text_unit_count + skipped_text_unit_count`.
- `text_unit_count` counts selected units plus represented skipped units. It does not count unrepresented section text/title fields excluded by config.
- `chapter.text` is always represented with `text_annotation_status`, so excluded chapter text counts as a skipped represented unit only when a mode explicitly excludes chapters while preserving chapters in output.
- All emitted footnotes are represented with annotation status and therefore count as annotated or skipped text units.
- `paragraph_count` counts only copied front/back matter paragraph objects. It is not an annotation count.
- `chapter_count`, `front_matter_section_count`, `back_matter_section_count`, and `footnote_count` describe preserved structure.
- Sentence/token/word/entity counts are sums over emitted `TextUnitAnnotation` objects only.
- Skipped text units do not contribute to sentence/token/word/entity counts.

## 14. Diagnostics

Diagnostic schema:

```text
docs/architecture/schema/stanza_annotator_diagnostics.v2.0.schema.json
```

Rules:

- Diagnostics are production-safe and concise.
- Diagnostics MUST NOT contain full book text, full text-unit text, raw HTML, absolute paths, usernames, secrets, or raw debug payloads.
- `entity_type = "paragraph"` is forbidden.
- Use `entity_type = "text_unit"` for selected, skipped, oversized, empty, or offset-related text-unit diagnostics.
- Use `entity_type = "stanza_runtime"` for adapter exceptions, invalid raw adapter output, and batch length mismatch.
- Diagnostic order is deterministic: validation/failure order first, then selection order, then text-unit id, then diagnostic code.

## 15. Limits and boundary behavior

Rules:

- `batch_size` is inclusive: a batch is valid when `1 <= len(batch) <= batch_size`.
- `max_text_unit_chars` is inclusive and measured in Unicode code points after copying the upstream string. A value is accepted when `len(text) <= max_text_unit_chars`; it is too large when `len(text) > max_text_unit_chars`.
- Empty strings are detected before size checks.
- `max_output_json_bytes` is measured as the exact number of UTF-8 bytes in the final JSON payload selected for output. In CLI mode, this includes pretty-print whitespace when `--pretty` is used because the limit protects the actual output channel.
- `output_too_large` is detected after production result construction but before writing to stdout or `--output`.

## 16. CLI

Canonical command:

```bash
stanza-annotator annotate INPUT.json [options]
```

Supported options:

```text
--output PATH
--config PATH
--pretty
--include-debug
--debug-dir PATH
--version
--help
```

Rules:

- `INPUT.json` is a local JSON file. `INPUT.json = -` is supported and reads the upstream result from stdin.
- If `--config PATH` is omitted, user config is `{}`.
- `--config -` is supported only when `INPUT.json` is not `-`; the CLI MUST NOT read both input and config from stdin in one invocation.
- `--output PATH` writes the JSON result to `PATH`; stdout is empty on success when `--output` is used.
- If `--output` is omitted or `--output -` is used, the JSON result is written to stdout.
- stdout is reserved for machine-readable JSON except `--version` and `--help`.
- Human-readable logs go to stderr and are disabled by default for successful annotation.
- `--include-debug` sets effective `include_debug = true` and may add top-level `debug`, but MUST NOT change production annotations.
- `--debug-dir` is CLI-only and MUST NOT appear in `annotation.config`; the directory MUST already exist and MUST be a directory.
- `--pretty` changes JSON whitespace only.
- Malformed UTF-8, invalid JSON, unreadable input, or unreadable config returns a structured failed result when the selected output channel is available. Invalid config exits `4`; invalid input exits `1`.
- Usage/parser errors exit `2` and emit no JSON result.

Output file rules:

- Parent directories for `--output PATH` MUST already exist.
- The CLI MUST NOT create parent directories implicitly.
- Existing regular files are overwritten atomically using a temporary file in the same directory followed by replace.
- If atomic replace is unavailable, the CLI MUST fail with exit `3` rather than risk a partial production JSON file.
- Output paths that are directories fail with exit `3`.
- Output symlinks MUST be rejected by default with exit `3` to avoid writing through unexpected targets.
- Temporary files MUST be cleaned up after success or failure when cleanup is possible.
- When `--output PATH` is requested and writing fails, the CLI MUST NOT fall back to stdout.

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Result status `succeeded` |
| 1 | Result status `failed` except invalid config |
| 2 | CLI usage error; no JSON result |
| 3 | Output write failure; no fallback JSON to stdout when `--output` was requested |
| 4 | Invalid config; JSON failed result emitted if output channel is available |
| 99 | Unexpected internal error |

## 17. Debug mode and privacy

Rules:

- Debug mode is disabled by default.
- Debug data is emitted only as top-level `debug` when effective `include_debug = true`.
- Debug data MUST NOT contain absolute local paths, full book text, raw HTML documents, binary assets, credentials, or secrets.
- Debug previews, if emitted, MUST be short and redacted before truncation.
- Debug mode MUST NOT alter production fields, diagnostics, counts, fingerprints, selection order, or Stanza adapter batch calls.
- `debug.redaction.applied` MUST be `true` if any preview was omitted or modified for privacy.

## 18. Fingerprints and determinism

Fingerprint algorithms are normative for emitted fingerprint fields.

```text
source_book_fingerprint = "sha256:" + sha256(canonical_json(upstream_book_without_debug))
annotation_input_fingerprint = "sha256:" + sha256(canonical_json({
  "supported_upstream_schema_version": "epub_content_extractor.v3.0",
  "source_book_fingerprint": source_book_fingerprint,
  "selected_text_units": [{"id", "kind", "owner_type", "owner_id", "source_field", "text"}],
  "effective_config_without_include_debug_and_logging": object,
  "stanza_version": string,
  "stanza_model_identity": string,
  "projection_contract_version": "stanza_annotator.v2.0"
}))
```

Canonical JSON rules:

- UTF-8 JSON, no insignificant whitespace, keys sorted lexicographically, arrays preserved in semantic order.
- Timestamps, durations, debug sidecars, output formatting, and CLI paths are excluded.
- `include_debug`, `logging`, and `debug_dir` are excluded from `annotation_input_fingerprint` because they must not change production annotations.
- `batch_size` is excluded from `annotation_input_fingerprint`; changing batch size alone MAY change adapter call grouping but MUST NOT change annotation semantics.

Determinism rules:

- Text-unit selection order is deterministic.
- Sentence ids use `<text_unit_id>:sNNNN`.
- Token ids use `<text_unit_id>:sNNNN:tNNNN`.
- Word ids use `<text_unit_id>:sNNNN:wNNNN`.
- Entity ids use `<text_unit_id>:eNNNN`.
- Reordering batch chunks is forbidden; text-unit order remains reading order.
- For the same upstream result, effective semantic config, Stanza adapter output, annotator version, and model identity, normalized outputs MUST be identical except timestamps and duration.

## 19. Versioning and compatibility

Rules:

- `schema_version` identifies the output contract and MUST be `stanza_annotator.v2.0` for this release.
- `annotator_version` MUST be SemVer-compatible without a leading `v`.
- Diagnostic codes, diagnostic severities, top-level error codes, CLI exit-code meanings, config field names, and output field shapes are stable public contract within v2.0.
- Removing, renaming, or changing the type/nullability/requiredness of production fields requires a new contract version.
- Adding optional debug fields is non-breaking only when `include_debug = true` and production fields are unchanged.
- Adding optional production fields requires at least a minor contract decision and schema update.
- Unknown upstream schema versions MUST be rejected with `unsupported_upstream_schema` until explicitly supported by a new consumed-boundary schema.
- Unknown user config fields are invalid in v2.0.
- Runtime improvements to batching/performance are non-breaking only if fixture outputs and adapter-call contract remain valid.

## 20. Glossary

| Term | Definition |
|---|---|
| User config | Partial override object accepted by API/CLI before defaults. |
| Effective config | Fully materialized config emitted under `annotation.config`. |
| Text unit | A whole selected source field such as `chapter.text`, `section.text`, title, or footnote text. |
| Selected text unit | A candidate included by content selection rules before empty/size skip checks. |
| Represented skipped unit | A selected or structurally represented unit emitted with annotation status `skipped`. |
| Excluded by config | A field not selected for annotation. It is represented as skipped only when the output model requires an annotation status for that object/field. |
| Annotation target | A text unit that may receive `TextUnitAnnotation`. Paragraph objects are never annotation targets. |

## 21. Implementation checklist

A conforming implementation MUST:

1. Validate config before validating upstream input.
2. Apply defaults and emit a fully materialized effective config snapshot.
3. Validate upstream input against the consumed `epub_content_extractor.v3.0` subset.
4. Reject `chapters[].paragraphs` in production input and output.
5. Select `chapters[].text` by default.
6. Build stable text-unit ids such as `chapter_001:text`.
7. Skip empty/oversized selected text units before batching.
8. Call `StanzaAdapterProtocol.annotate_batch()` with chunks bounded by `batch_size`.
9. Preserve one returned Stanza document per input text unit in order.
10. Attach annotations to `text_annotation`, `title_annotation`, or footnote `annotation` fields only.
11. Never attach annotations to paragraph objects.
12. Emit no top-level flat `sentences[]` / `entities[]` arrays.
13. Enforce output-size limit before writing output.
14. Validate representative outputs against `schema/stanza_annotator.v2.0.schema.json` in CI.
15. Validate all config, input, expected-output, diagnostic, and error-registry fixtures in CI.

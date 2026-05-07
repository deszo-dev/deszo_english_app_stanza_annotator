# stanza_annotator architecture

`stanza_annotator` — модуль получения лингвистических аннотаций текста с помощью Stanza, сконфигурированной под требования приложения.

Модуль:

- настраивает Stanza pipeline;
- выполняет аннотацию подготовленного текста;
- возвращает строго структурированные данные для дальнейшего анализа;
- служит checkpoint-слоем для отладки качества аннотаций;
- отделяет внешний Stanza runtime от чистого ядра и CLI-обвязки.

## 1. Граница ответственности

### Входит в ответственность модуля

- конфигурация Stanza pipeline;
- вызов Stanza через изолированный adapter;
- проекция результата Stanza в стабильную структуру `AnnotatedDocument`;
- валидация входных предусловий до передачи в core;
- логирование шагов pipeline без смешивания логов с результатом;
- debug-трассировка без изменения вычислений.

### Не входит в ответственность модуля

Модуль **не занимается preprocessing текста**.

Он ожидает полностью подготовленный UTF-8 текст. До вызова `stanza_annotator` должны быть выполнены, если они нужны приложению:

- очистка текста;
- нормализация кавычек;
- исправление OCR-ошибок;
- ручной sentence splitting;
- `ftfy` / unicode fixes;
- любые доменные нормализации.

Нарушение этого предусловия является ожидаемой ошибкой данных и должно завершать CLI с exit code `1`.

## 2. Слои архитектуры

```text
stdin / files / CLI args
        |
        v
+-----------------------------+
| CLI                         |
| - parse args                |
| - resolve config            |
| - validate input            |
| - call pipeline             |
| - write result to stdout    |
| - write logs/errors to stderr|
+-----------------------------+
        |
        v
+-----------------------------+
| Application pipeline        |
| - orchestrate adapters      |
| - call Stanza adapter       |
| - call pure core projection |
+-----------------------------+
        |
        v
+-----------------------------+
| Core                        |
| - no IO                     |
| - no environment access     |
| - no global state           |
| - deterministic projection  |
| - candidate for Coq spec    |
+-----------------------------+
        |
        v
AnnotatedDocument
```

### CLI

CLI — тонкий слой, который:

- парсит аргументы;
- читает вход из stdin или файла;
- разрешает конфигурацию в порядке `CLI args -> ENV -> defaults`;
- валидирует входные данные до вызова core;
- вызывает pipeline;
- пишет только результат в `stdout`;
- пишет только логи и ошибки в `stderr`;
- не меняет семантику core.

CLI не имеет права:

- неявно трансформировать входной текст;
- менять порядок вычислений;
- добавлять недетерминизм поверх core;
- смешивать результат и логи;
- выполнять preprocessing.

### Pipeline

Pipeline связывает CLI, adapter и core:

```text
PreparedText -> StanzaAdapter -> RawStanzaDocument -> CoreProjection -> AnnotatedDocument
```

Pipeline допускает IO только через adapter-границы. Формальные гарантии применяются к core и к контрактам границ, а не к внутренней реализации Stanza.

### Core

Core реализует чистую трансформацию:

```text
output = f(input, config, raw_stanza_document)
```

Свойства core:

- нет IO;
- нет `print`;
- нет чтения ENV;
- нет зависимости от времени;
- нет неконтролируемой случайности;
- нет скрытого глобального состояния;
- один и тот же `input`, `config` и `raw_stanza_document` дают один и тот же `output`;
- структура результата проверяется через инварианты `AnnotatedDocument`.

### Adapter

Stanza является внешней зависимостью и единственным источником лингвистических аннотаций.

Adapter:

- инкапсулирует создание и вызов Stanza pipeline;
- принимает только подготовленный UTF-8 текст;
- возвращает raw-результат Stanza;
- не выполняет preprocessing;
- не определяет публичный API модуля;
- обязан быть внедряемым через Dependency Injection для тестов.

## 3. Конфигурация Stanza pipeline

Базовый pipeline:

```text
processors = "tokenize,mwt,pos,lemma,depparse,ner"
```

Рекомендуемая конфигурация:

```typescript
interface StanzaAnnotatorConfig {
  language: "en";
  use_gpu?: boolean;
  processors?: "tokenize,mwt,pos,lemma,depparse,ner";
  tokenize_pretokenized?: boolean;
  auto_download?: boolean;
  debug?: boolean;
  debug_dir?: string;
  logging?: {
    enabled: boolean;
    level: "debug" | "info" | "warning" | "error";
  };
}
```

Defaults:

- `language = "en"`;
- `processors = "tokenize,mwt,pos,lemma,depparse,ner"`;
- `use_gpu = true`, если доступно и явно разрешено окружением приложения;
- `tokenize_pretokenized = false`;
- `auto_download = true`;
- `debug = false`.

Конфигурация должна разрешаться детерминированно. `processors` фиксирован строго как `"tokenize,mwt,pos,lemma,depparse,ner"`. Любое другое значение является ошибкой конфигурации и должно завершать CLI с exit code `1`.

## 4. Input contract

```typescript
type InputText = string; // valid UTF-8
```

Требования:

- валидный UTF-8;
- текст уже подготовлен upstream-компонентами;
- preprocessing завершён до вызова модуля;
- sentence boundaries уже корректны настолько, насколько это требуется приложению;
- input не содержит данных, которые запрещено логировать в открытом виде.

Валидация выполняется до передачи в core. Нарушение предусловий является expected data error.

Пустой или состоящий только из whitespace input является валидным подготовленным текстом и возвращает пустой `AnnotatedDocument` с exit code `0`.

## 5. Output contract

Модуль возвращает объект, совместимый со структурой Stanza, но зафиксированный как стабильный контракт приложения.

```typescript
interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}

interface Sentence {
  text: string;
  tokens: Token[];
  words: Word[];
}

interface Token {
  text: string;
  words: Word[];
}

interface Word {
  text: string;
  lemma: string;
  upos: string;
  xpos?: string;
  feats?: string;
  head: number;
  deprel: string;
  start_char: number;
  end_char: number;
}

interface Entity {
  text: string;
  type: string;
  start_char: number;
  end_char: number;
}
```

Инварианты результата:

- `start_char <= end_char` для `Word` и `Entity`;
- `text`, `upos`, `deprel` у `Word` не пустые;
- `text` и `type` у `Entity` не пустые;
- каждый `Token` содержит хотя бы один `Word`;
- логи и debug-данные не входят в `AnnotatedDocument`;
- формат вывода полностью воспроизводим.

## 6. Public Python API

Публичный API экспортируется только через `__init__.py`.

Минимальный публичный API:

```python
from stanza_annotator import (
    AnnotatedDocument,
    AnnotationError,
    ConfigurationError,
    InputValidationError,
    StanzaAnnotator,
    StanzaAnnotatorConfig,
)
```

Основной метод:

```python
class StanzaAnnotator:
    def annotate(self, text: str) -> AnnotatedDocument:
        """Annotate prepared UTF-8 text and return a deterministic document."""
```

Требования к Python-коду:

- полная типизация публичного API;
- `mypy --strict`;
- `ruff` с правилами `E`, `F`, `I`, `B`;
- `black`, max line length `88`;
- `Any` запрещён в публичном API;
- wildcard imports запрещены;
- все ошибки представлены кастомными исключениями;
- IO отделён от доменной логики;
- Dependency Injection обязателен для adapter/runtime зависимостей;
- `print` запрещён, используется только `logging`.

## 7. CLI contract

CLI должен поддерживать:

- вход из stdin;
- вход из файла;
- `--debug` / `-d`;
- `--output` для записи результата в файл вместо `stdout`;
- стабильные аргументы нового контракта без требования обратной совместимости со старым CLI.

Потоки вывода:

- `stdout` — только сериализованный `AnnotatedDocument`;
- `stderr` — только логи и ошибки.

Если указан `--output`, сериализованный `AnnotatedDocument` пишется в файл, а `stdout` остаётся пустым. Ошибки никогда не создают частичный результат ни в `stdout`, ни в output-файле.

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | success |
| `1` | expected data/configuration error |
| `2+` | system/runtime error |

CLI-контракт детерминирован и не изменяет семантику core.

## 8. Logging and debug

Логирование обязательно и выполняется через `logging`.

Логируются:

- разрешённые входные параметры без чувствительных данных;
- start/end каждого шага pipeline;
- факт успешного результата;
- ожидаемые ошибки данных;
- системные ошибки без раскрытия внутренних деталей.

Уровни:

- `DEBUG`;
- `INFO`;
- `WARNING`;
- `ERROR`.

Debug mode:

- включается через `--debug` / `-d` или config flag;
- увеличивает наблюдаемость;
- может логировать raw-аннотации, токены и зависимости;
- не меняет вычисления;
- не изменяет `AnnotatedDocument`;
- не смешивает debug output с `stdout`.

Пример debug-представления:

```json
{
  "text": "I am tired.",
  "words": [
    {"text": "I", "upos": "PRON", "feats": "Person=1|Number=Sing"},
    {"text": "am", "upos": "AUX", "feats": "Tense=Pres|VerbForm=Fin"},
    {"text": "tired", "upos": "ADJ"}
  ]
}
```

## 9. Formal Coq specification

Эта секция формализует проверяемую часть архитектуры: структуру результата, инварианты, детерминизм core, debug-observability-only и CLI exit-code mapping.

Stanza runtime моделируется как внешняя граница. Coq-спецификация не доказывает лингвистическую корректность Stanza; она фиксирует контракт проекции raw-результата Stanza в `AnnotatedDocument` и свойства, которые обязан сохранять Python-код.

```coq
From Coq Require Import Arith.Arith.
From Coq Require Import Lists.List.
From Coq Require Import micromega.Lia.
From Coq Require Import Strings.String.

Import ListNotations.
Open Scope string_scope.
Open Scope list_scope.
Open Scope nat_scope.

Module StanzaAnnotatorSpec.

Inductive Processor : Type :=
| Tokenize
| Mwt
| Pos
| LemmaProc
| Depparse
| Ner.

Definition default_processors : list Processor :=
  [Tokenize; Mwt; Pos; LemmaProc; Depparse; Ner].

Inductive LogLevel : Type :=
| LogDebug
| LogInfo
| LogWarning
| LogError.

Inductive ExitCode : Type :=
| Success
| ExpectedError
| SystemError.

Definition exit_code_value (c : ExitCode) : nat :=
  match c with
  | Success => 0
  | ExpectedError => 1
  | SystemError => 2
  end.

Theorem exit_code_contract :
  exit_code_value Success = 0 /\
  exit_code_value ExpectedError = 1 /\
  exit_code_value SystemError >= 2.
Proof.
  repeat split; simpl; lia.
Qed.

Record AnnotatorConfig : Type := {
  cfg_language : string;
  cfg_use_gpu : bool;
  cfg_processors : list Processor;
  cfg_tokenize_pretokenized : bool;
  cfg_auto_download : bool;
  cfg_debug : bool
}.

Definition valid_config (c : AnnotatorConfig) : Prop :=
  cfg_language c = "en" /\ cfg_processors c = default_processors.

Record PreparedInput : Type := {
  input_text : string;
  input_valid_utf8 : Prop;
  input_preprocessed : Prop
}.

Definition non_empty_string (s : string) : Prop := s <> "".
Definition valid_span (start finish : nat) : Prop := start <= finish.

Record Word : Type := {
  word_surface : string;
  word_lemma : string;
  word_upos : string;
  word_xpos : option string;
  word_feats : option string;
  word_head : nat;
  word_deprel : string;
  word_start_char : nat;
  word_end_char : nat
}.

Definition valid_word (w : Word) : Prop :=
  valid_span (word_start_char w) (word_end_char w) /\
  non_empty_string (word_surface w) /\
  non_empty_string (word_upos w) /\
  non_empty_string (word_deprel w).

Record Token : Type := {
  token_surface : string;
  token_words : list Word
}.

Definition valid_token (t : Token) : Prop :=
  non_empty_string (token_surface t) /\
  token_words t <> [] /\
  Forall valid_word (token_words t).

Record Sentence : Type := {
  sentence_surface : string;
  sentence_tokens : list Token;
  sentence_words : list Word
}.

Definition valid_sentence (s : Sentence) : Prop :=
  non_empty_string (sentence_surface s) /\
  Forall valid_token (sentence_tokens s) /\
  Forall valid_word (sentence_words s).

Record Entity : Type := {
  entity_surface : string;
  entity_type : string;
  entity_start_char : nat;
  entity_end_char : nat
}.

Definition valid_entity (e : Entity) : Prop :=
  non_empty_string (entity_surface e) /\
  non_empty_string (entity_type e) /\
  valid_span (entity_start_char e) (entity_end_char e).

Record AnnotatedDocument : Type := {
  doc_sentences : list Sentence;
  doc_entities : list Entity
}.

Definition valid_document (d : AnnotatedDocument) : Prop :=
  Forall valid_sentence (doc_sentences d) /\
  Forall valid_entity (doc_entities d).

(* External Stanza boundary. This is an explicit implementation obligation,
   not a theorem about Stanza internals. The Python adapter and tests must
   discharge this contract for supported Stanza versions and configurations. *)
Parameter RawStanzaDocument : Type.
Parameter project_stanza_document : RawStanzaDocument -> AnnotatedDocument.
Parameter project_stanza_document_preserves_schema :
  forall raw : RawStanzaDocument,
    valid_document (project_stanza_document raw).

Definition annotate_core
  (_input : PreparedInput)
  (_config : AnnotatorConfig)
  (raw : RawStanzaDocument) : AnnotatedDocument :=
  project_stanza_document raw.

Theorem annotate_core_deterministic :
  forall input config raw,
    annotate_core input config raw = annotate_core input config raw.
Proof.
  reflexivity.
Qed.

Theorem annotate_core_preserves_schema :
  forall input config raw,
    valid_document (annotate_core input config raw).
Proof.
  intros input config raw.
  unfold annotate_core.
  apply project_stanza_document_preserves_schema.
Qed.

Definition DebugTrace : Type := list string.

Definition observe_debug
  (doc : AnnotatedDocument)
  (_trace : DebugTrace) : AnnotatedDocument :=
  doc.

Theorem debug_does_not_change_result :
  forall doc trace,
    observe_debug doc trace = doc.
Proof.
  reflexivity.
Qed.

Inductive CliStatus : Type :=
| CliOk (doc : AnnotatedDocument)
| CliExpectedDataError
| CliSystemFailure.

Definition cli_exit_code (r : CliStatus) : ExitCode :=
  match r with
  | CliOk _ => Success
  | CliExpectedDataError => ExpectedError
  | CliSystemFailure => SystemError
  end.

Theorem cli_exit_code_mapping :
  forall d,
    cli_exit_code (CliOk d) = Success /\
    cli_exit_code CliExpectedDataError = ExpectedError /\
    cli_exit_code CliSystemFailure = SystemError.
Proof.
  intro d.
  repeat split; reflexivity.
Qed.

Record CliObservation : Type := {
  obs_stdout : option AnnotatedDocument;
  obs_stderr : list string;
  obs_exit : ExitCode
}.

Definition valid_cli_observation (o : CliObservation) : Prop :=
  match obs_exit o with
  | Success => exists d, obs_stdout o = Some d
  | ExpectedError => obs_stdout o = None
  | SystemError => obs_stdout o = None
  end.

Theorem non_success_has_no_stdout_payload :
  forall o,
    valid_cli_observation o ->
    obs_exit o <> Success ->
    obs_stdout o = None.
Proof.
  intros o Hvalid Hnot_success.
  destruct o as [out err exit].
  simpl in *.
  destruct exit; try contradiction; exact Hvalid.
Qed.

End StanzaAnnotatorSpec.
```

### Coq ↔ Python mapping

| Coq symbol | Python responsibility |
| --- | --- |
| `PreparedInput` | validated prepared UTF-8 input passed after CLI validation |
| `AnnotatorConfig` | immutable resolved config object |
| `RawStanzaDocument` | adapter-owned raw Stanza result |
| `project_stanza_document` | pure projection from raw Stanza result to `AnnotatedDocument` |
| `annotate_core` | pure core function, no IO and no environment access |
| `valid_document` | schema and invariant checks covered by unit/property tests |
| `debug_does_not_change_result` | debug mode changes observability only |
| `cli_exit_code_mapping` | CLI exit-code contract |
| `non_success_has_no_stdout_payload` | stderr-only errors and no partial stdout result |

## 10. Testing obligations

Unit tests:

- validate config resolution;
- validate input preconditions;
- verify that preprocessing is not performed by this module;
- verify `AnnotatedDocument` invariants;
- verify that debug mode does not change returned `AnnotatedDocument`;
- verify stdout/stderr separation;
- verify exit code mapping.

Property-based tests are recommended for:

- span invariants;
- deterministic projection of raw Stanza structures;
- stability of serialization;
- equivalence between debug and non-debug result payloads.

Coq-related checks:

- maintain `StanzaAnnotatorSpec.v` as the checked Coq specification;
- run `coqc StanzaAnnotatorSpec.v`;
- fail CI if the specification no longer compiles;
- fail CI if a theorem is removed, weakened, or replaced by an unmarked assumption.

## 11. Error model

Only custom exceptions are allowed in the Python API.

Suggested hierarchy:

```python
class AnnotationError(Exception):
    """Base exception for stanza_annotator."""

class InputValidationError(AnnotationError):
    """Prepared input contract was violated."""

class ConfigurationError(AnnotationError):
    """Configuration is invalid or unsupported."""

class StanzaRuntimeError(AnnotationError):
    """External Stanza runtime failed."""
```

Mapping:

| Error | CLI exit code | Stream |
| --- | ---: | --- |
| `InputValidationError` | `1` | `stderr` |
| `ConfigurationError` | `1` | `stderr` |
| `StanzaRuntimeError` | `2+` | `stderr` |
| Unexpected system error | `2+` | `stderr` |

Expected errors must not produce partial `stdout`.

## 12. Security

- sensitive input data must not be logged in full;
- debug logs must be safe by default or explicitly gated;
- errors must not expose internal paths, secrets, model cache paths or stack traces unless explicitly enabled for local debugging;
- input must be validated and sanitized before adapter/core usage;
- logs must never alter the result.

## 13. Evolution rules

A breaking change is any change that:

- changes the public Python API;
- changes the CLI contract;
- changes output schema or serialization semantics;
- weakens or invalidates a proved Coq property;
- changes assumptions behind `project_stanza_document_preserves_schema`;
- changes default processors or config resolution semantics.

Every such change requires:

- architecture update;
- tests update;
- Coq specification update or explicit declaration that the previous proof no longer applies;
- changelog entry.

## 14. Definition of Done

The module is ready when:

- public API is minimal and exported only via `__init__.py`;
- public API is fully typed;
- `mypy --strict` passes;
- `ruff` and `black` pass;
- unit tests are deterministic and isolated from external IO;
- adapter dependencies are injected;
- core contains no IO and no global state;
- CLI keeps stdout/stderr separated;
- CLI supports `--debug` / `-d`;
- debug mode does not change result payload;
- input validation happens before core;
- all expected errors map to exit code `1`;
- system errors map to exit code `2+`;
- no partial results are emitted unless explicitly specified;
- Coq specification compiles in CI;
- Coq theorem ↔ Python function mapping is maintained;
- implementation tests check the documented invariants.

## 15. Integration addition for grammar_extractor

For cleaner end-to-end debug collection, the CLI SHOULD support optional `--debug-dir` in addition to `--debug` / `-d`.

```text
stanza-annotator \
  --input clean_text.txt \
  --output annotated_document.json \
  --debug \
  --debug-dir debug/stanza_annotator
```

Rules:

- `--debug-dir` writes side-car debug artifacts only;
- debug side files may include raw Stanza projection snapshots, token/dependency traces and adapter diagnostics;
- `AnnotatedDocument` must remain unchanged compared with non-debug mode;
- no debug payload is written to `stdout`;
- if `--output` is set, `stdout` remains empty;
- debug artifacts must be safe-by-default and gated by explicit debug mode.

This addition is backward-compatible with the existing CLI contract and exists mainly so `grammar_extractor` can collect all dependency debug data into one debug bundle.

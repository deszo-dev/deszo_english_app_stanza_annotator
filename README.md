# stanza_annotator

## English

`stanza_annotator` is a focused module for producing linguistic annotations for prepared English text with [Stanza](https://stanfordnlp.github.io/stanza/).

The module configures a Stanza pipeline, runs annotation, and returns structured data that can be used by downstream analysis tools in the Deszo English App ecosystem.

### Scope

`stanza_annotator` is responsible for:

- configuring the Stanza pipeline;
- annotating prepared UTF-8 text;
- returning a structured document representation;
- acting as a debug checkpoint for annotation quality.

It is not responsible for text preprocessing. Input text must already be cleaned and prepared before it is passed to this module.

Out of scope:

- text cleanup;
- quote normalization;
- OCR error correction;
- manual sentence splitting;
- `ftfy` or other Unicode repair steps.

### Default Pipeline

The default Stanza processor configuration is:

```text
tokenize,mwt,pos,lemma,depparse,ner
```

### Installation

```bash
pip install -e ".[dev]"
```

The module automatically downloads the required Stanza English models on first use unless `auto_download` is disabled.

### Python Usage

```python
from stanza_annotator import StanzaAnnotator

annotator = StanzaAnnotator()
doc = annotator.annotate("I am tired.")

for sentence in doc.sentences:
    for word in sentence.words:
        print(word.text, word.lemma, word.upos)
```

### CLI Usage

Without installing the package, run the CLI through Python from the repository root:

```bash
python -m stanza_annotator alice.txt --output alice.annotations.json --debug --debug-dir debug
```

After editable installation, the console command is available:

```bash
stanza-annotate alice.txt --output alice.annotations.json --debug --debug-dir debug
```

The module is designed for English text:

```ts
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

### Input And Output

Input:

```ts
type InputText = string; // UTF-8
```

Output:

```ts
interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}
```

The output follows the structure of a Stanza document and includes sentences, tokens, words, lemmas, POS tags, dependency information, character offsets, and named entities.

Empty or whitespace-only input is valid and returns an empty document.

### Debugging

The module supports a debug mode that writes JSON traces to `debug_dir` and helps inspect:

- raw annotations;
- tokens and dependency relations;
- POS and morphology quality;
- output differences between configurations;
- reproducible annotation bugs.

### Documentation

- Russian architecture document: [docs/architecture.md](docs/architecture.md)
- English architecture document: [docs/architecture.en.md](docs/architecture.en.md)

### Usage Policy

This project is published for non-commercial use. Commercial use is not permitted without explicit permission from the project owner.

See [LICENSE](LICENSE) for the exact terms. A non-commercial restriction usually means the project is source-available rather than open source under the OSI definition.

## Русский

`stanza_annotator` - это специализированный модуль для получения лингвистических аннотаций подготовленного английского текста с помощью [Stanza](https://stanfordnlp.github.io/stanza/).

Модуль настраивает pipeline Stanza, выполняет аннотирование и возвращает структурированные данные для дальнейшего анализа в экосистеме Deszo English App.

### Область ответственности

`stanza_annotator` отвечает за:

- настройку Stanza pipeline;
- аннотирование подготовленного UTF-8 текста;
- возврат структурированного представления документа;
- роль контрольной точки для отладки качества аннотаций.

Модуль не занимается preprocessing текста. Входной текст должен быть очищен и подготовлен до вызова `stanza_annotator`.

Не входит в область ответственности:

- очистка текста;
- нормализация кавычек;
- исправление OCR-ошибок;
- ручное разбиение на предложения;
- `ftfy` или другие Unicode-исправления.

### Pipeline По Умолчанию

Базовая конфигурация Stanza processors:

```text
tokenize,mwt,pos,lemma,depparse,ner
```

### Установка

```bash
pip install -e ".[dev]"
```

Модуль автоматически скачивает нужные Stanza-модели для английского языка при первом использовании, если `auto_download` не отключен.

### Использование В Python

```python
from stanza_annotator import StanzaAnnotator

annotator = StanzaAnnotator()
doc = annotator.annotate("I am tired.")

for sentence in doc.sentences:
    for word in sentence.words:
        print(word.text, word.lemma, word.upos)
```

### Использование CLI

Без установки пакета CLI можно запускать через Python из корня репозитория:

```bash
python -m stanza_annotator alice.txt --output alice.annotations.json --debug --debug-dir debug
```

После editable-установки становится доступна console-команда:

```bash
stanza-annotate alice.txt --output alice.annotations.json --debug --debug-dir debug
```

Модуль рассчитан на английский язык:

```ts
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

### Вход И Выход

Вход:

```ts
type InputText = string; // UTF-8
```

Выход:

```ts
interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}
```

Выходная структура совместима с представлением Stanza document и включает предложения, токены, слова, леммы, POS-теги, dependency-информацию, символьные offsets и именованные сущности.

Пустой или состоящий только из whitespace input валиден и возвращает пустой документ.

### Отладка

Модуль поддерживает debug-режим, который пишет JSON-трассы в `debug_dir` и помогает проверять:

- raw-аннотации;
- токены и dependency-связи;
- качество POS и morphology;
- различия output между конфигурациями;
- воспроизводимые ошибки аннотирования.

### Документация

- Русский документ архитектуры: [docs/architecture.md](docs/architecture.md)
- Английский документ архитектуры: [docs/architecture.en.md](docs/architecture.en.md)

### Условия Использования

Проект публикуется для некоммерческого использования. Коммерческое использование запрещено без явного разрешения владельца проекта.

Точные условия описаны в [LICENSE](LICENSE). Ограничение на коммерческое использование обычно означает, что проект является source-available, а не open source в смысле OSI.

# stanza_annotator Architecture

`stanza_annotator` is a module responsible for producing linguistic text annotations with Stanza, configured for the needs of the application.

The module:

- configures the Stanza pipeline;
- annotates text;
- returns structured data for downstream analysis;
- serves as a checkpoint for debugging annotation quality.

## Important Limitation

The module does not perform text preprocessing.

It expects fully prepared UTF-8 text as input.

The following tasks are outside the module boundary:

- text cleanup;
- quote normalization;
- OCR error correction;
- manual sentence splitting;
- `ftfy` or other Unicode fixes.

All preprocessing must happen before `stanza_annotator` is called.

## 1. Stanza Pipeline Configuration

The module encapsulates pipeline setup.

Default processors:

```text
tokenize
mwt
pos
lemma
depparse
ner
```

Equivalent processor string:

```text
tokenize,mwt,pos,lemma,depparse,ner
```

## 2. Text Annotation

Input:

```ts
type InputText = string; // UTF-8
```

Output:

A structured representation of the annotated text as a document object.

```ts
interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}
```

## 3. Debug Checkpoint

The module is used as a quality checkpoint for annotations.

It should make it possible to:

- verify POS correctness;
- inspect morphology;
- inspect dependency structure;
- compare output from different configurations;
- reproduce annotation bugs.

## Input Requirements

Input must be:

- valid UTF-8;
- cleaned text;
- text with correct sentence boundaries when possible.

```ts
type InputText = string; // UTF-8
```

## Output Structure

The module returns an object compatible with the Stanza document structure.

```ts
interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}
```

### Sentence

```ts
interface Sentence {
  text: string;
  tokens: Token[];
  words: Word[];
}
```

### Token

Surface-level token.

```ts
interface Token {
  text: string;
  words: Word[];
}
```

### Word

The main annotation unit.

```ts
interface Word {
  text: string;
  lemma: string;
  upos: string;
  xpos?: string;
  feats?: string;

  head: number;     // dependency head index
  deprel: string;   // dependency relation

  start_char: number;
  end_char: number;
}
```

### Entity

Named entity recognition output.

```ts
interface Entity {
  text: string;
  type: string;
  start_char: number;
  end_char: number;
}
```

## Configuration

Base pipeline configuration:

```text
processors = "tokenize,mwt,pos,lemma,depparse,ner"
```

Configuration shape:

```ts
interface StanzaAnnotatorConfig {
  language: "en";

  use_gpu?: boolean;

  processors?: string; // override default

  tokenize_pretokenized?: boolean;

  logging?: {
    enabled: boolean;
    level: "info" | "debug";
  };
}
```

Recommended settings:

- `language = "en"`;
- `processors = "tokenize,mwt,pos,lemma,depparse,ner"`;
- `use_gpu = true` by default when available.

## Debug Mode

The module should support:

```ts
debug = true
```

In this mode:

- raw annotations are emitted;
- tokens and dependency relations are logged;
- intermediate results are saved.

Example debug output:

```json
{
  "text": "I am tired.",
  "words": [
    { "text": "I", "upos": "PRON", "feats": "Person=1|Number=Sing" },
    { "text": "am", "upos": "AUX", "feats": "Tense=Pres|VerbForm=Fin" },
    { "text": "tired", "upos": "ADJ" }
  ]
}
```

## API

### annotate

```ts
function annotate(text: string): AnnotatedDocument
```

Example usage:

```python
annotator = StanzaAnnotator()

doc = annotator.annotate("I am tired.")

for sentence in doc.sentences:
    for word in sentence.words:
        print(word.text, word.lemma, word.upos)
```

## Design Principles

### 1. Single Source Of Truth

Stanza is the only source of annotations.

### 2. No Preprocessing

The module has a clean responsibility boundary and receives already prepared text.

### 3. Deterministic Output

The same input should produce the same output.

### 4. Debug-First

The module should be convenient for analyzing annotation errors.

## Summary

`stanza_annotator` is a stable, reproducible layer for producing syntactic and linguistic annotations.

It:

- configures Stanza;
- annotates text;
- returns structured output;
- serves as a debugging checkpoint.

stanza_annotator

stanza_annotator — это модуль, отвечающий за получение лингвистических аннотаций текста с помощью Stanza, сконфигурированных под требования приложения.

Модуль:

настраивает pipeline Stanza
выполняет аннотацию текста
возвращает структурированные данные для дальнейшего анализа
служит контрольной точкой (checkpoint) для отладки качества аннотаций

❗ Важное ограничение
Модуль НЕ занимается preprocessing текста.

Он ожидает:

полностью подготовленный UTF-8 текст

Примеры того, что НЕ входит в его ответственность:

❌ очистка текста
❌ нормализация кавычек
❌ исправление OCR ошибок
❌ sentence splitting (вручную)
❌ ftfy / unicode fixes

👉 Всё это должно происходить до вызова stanza_annotator

1. Конфигурация Stanza pipeline

Модуль инкапсулирует настройку pipeline:

tokenize
mwt
pos
lemma
depparse
ner

2. Аннотирование текста

На вход:

UTF-8 string

На выход:

структурированное представление текста (doc)

3. Debug checkpoint

Модуль используется как:

точка контроля качества аннотаций

Позволяет:

✔ проверить корректность POS
✔ проверить morphology
✔ проверить dependency structure
✔ сравнить output разных конфигураций
✔ воспроизводить баги

📥 Input
type InputText = string; // UTF-8

Требования:

✔ валидный UTF-8
✔ очищенный текст
✔ корректные sentence boundaries (по возможности)
📤 Output

Модуль возвращает объект, совместимый со структурой Stanza:

interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}
Sentence
interface Sentence {
  text: string;
  tokens: Token[];
  words: Word[];
}
Token (surface level)
interface Token {
  text: string;
  words: Word[];
}
Word (основная единица)
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
Entity (NER)
interface Entity {
  text: string;
  type: string;
  start_char: number;
  end_char: number;
}

⚙️ Конфигурация
Базовая конфигурация pipeline
processors = "tokenize,mwt,pos,lemma,depparse,ner"
Настройки
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
Рекомендуемые настройки
✔ language = en
✔ processors = tokenize,mwt,pos,lemma,depparse,ner
✔ use_gpu = true (по умолчанию)

Debugging режим

Модуль должен поддерживать режим:

debug = true

В котором:

✔ выводятся raw аннотации
✔ логируются токены и зависимости
✔ сохраняется промежуточный результат
Пример debug output
{
  "text": "I am tired.",
  "words": [
    { "text": "I", "upos": "PRON", "feats": "Person=1|Number=Sing" },
    { "text": "am", "upos": "AUX", "feats": "Tense=Pres|VerbForm=Fin" },
    { "text": "tired", "upos": "ADJ" }
  ]
}

API
annotate
function annotate(text: string): AnnotatedDocument
Пример использования
annotator = StanzaAnnotator()

doc = annotator.annotate("I am tired.")

for sentence in doc.sentences:
    for word in sentence.words:
        print(word.text, word.lemma, word.upos)
🧠 Дизайн-принципы
1. Single source of truth
Stanza = единственный источник аннотаций
2. No preprocessing
чистая граница ответственности
3. Deterministic output
один и тот же input → один и тот же output
4. Debug-first
модуль должен быть удобен для анализа ошибок
🚀 Итог
stanza_annotator = стабильный, воспроизводимый слой
получения синтаксических аннотаций

Он:

✔ конфигурирует Stanza
✔ аннотирует текст
✔ возвращает структуру
✔ служит checkpoint для отладки
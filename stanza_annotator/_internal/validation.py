from __future__ import annotations

from stanza_annotator.errors import InputValidationError
from stanza_annotator.models import AnnotatedDocument, Entity, Sentence, Token, Word


def validate_prepared_text(text: str) -> None:
    if not isinstance(text, str):
        raise InputValidationError("input text must be a string")


def validate_document(document: AnnotatedDocument) -> None:
    for sentence in document.sentences:
        _validate_sentence(sentence)
    for entity in document.entities:
        _validate_entity(entity)


def _validate_sentence(sentence: Sentence) -> None:
    for token in sentence.tokens:
        _validate_token(token)
    for word in sentence.words:
        _validate_word(word)


def _validate_token(token: Token) -> None:
    if not token.words:
        raise InputValidationError("annotated token must contain at least one word")
    for word in token.words:
        _validate_word(word)


def _validate_word(word: Word) -> None:
    if not word.text:
        raise InputValidationError("annotated word text must not be empty")
    if not word.upos:
        raise InputValidationError("annotated word upos must not be empty")
    if not word.deprel:
        raise InputValidationError("annotated word deprel must not be empty")
    if word.start_char > word.end_char:
        raise InputValidationError("annotated word span is invalid")


def _validate_entity(entity: Entity) -> None:
    if not entity.text:
        raise InputValidationError("annotated entity text must not be empty")
    if not entity.type:
        raise InputValidationError("annotated entity type must not be empty")
    if entity.start_char > entity.end_char:
        raise InputValidationError("annotated entity span is invalid")

from collections.abc import Iterable
from typing import Any

from stanza_annotator.models import AnnotatedDocument, Entity, Sentence, Token, Word


def document_to_annotated_document(document: Any) -> AnnotatedDocument:
    sentences = [
        _convert_sentence(sentence)
        for sentence in _get_list_attr(document, "sentences")
    ]
    entities = [
        _convert_entity(entity)
        for entity in _get_list_attr(document, "entities")
    ]
    return AnnotatedDocument(sentences=sentences, entities=entities)


def document_to_raw_dict(document: Any) -> dict[str, Any] | None:
    if hasattr(document, "to_dict"):
        raw = document.to_dict()
        return raw if isinstance(raw, dict) else {"document": raw}
    if hasattr(document, "to_json"):
        return {"json": document.to_json()}
    return None


def _convert_sentence(sentence: Any) -> Sentence:
    return Sentence(
        text=_string_attr(sentence, "text"),
        tokens=[_convert_token(token) for token in _get_list_attr(sentence, "tokens")],
        words=[_convert_word(word) for word in _get_list_attr(sentence, "words")],
    )


def _convert_token(token: Any) -> Token:
    return Token(
        text=_string_attr(token, "text"),
        words=[_convert_word(word) for word in _get_list_attr(token, "words")],
    )


def _convert_word(word: Any) -> Word:
    return Word(
        text=_string_attr(word, "text"),
        lemma=_string_attr(word, "lemma"),
        upos=_string_attr(word, "upos"),
        xpos=_optional_string_attr(word, "xpos"),
        feats=_optional_string_attr(word, "feats"),
        head=_int_attr(word, "head"),
        deprel=_string_attr(word, "deprel"),
        start_char=_optional_int_attr(word, "start_char"),
        end_char=_optional_int_attr(word, "end_char"),
    )


def _convert_entity(entity: Any) -> Entity:
    entity_type = _optional_string_attr(entity, "type")
    if entity_type is None:
        entity_type = _string_attr(entity, "ner")
    return Entity(
        text=_string_attr(entity, "text"),
        type=entity_type,
        start_char=_optional_int_attr(entity, "start_char"),
        end_char=_optional_int_attr(entity, "end_char"),
    )


def _get_list_attr(obj: Any, name: str) -> list[Any]:
    value = getattr(obj, name, None)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return list(value)
    return []


def _string_attr(obj: Any, name: str) -> str:
    value = getattr(obj, name, None)
    return "" if value is None else str(value)


def _optional_string_attr(obj: Any, name: str) -> str | None:
    value = getattr(obj, name, None)
    return None if value is None else str(value)


def _int_attr(obj: Any, name: str) -> int:
    value = getattr(obj, name, 0)
    return 0 if value is None else int(value)


def _optional_int_attr(obj: Any, name: str) -> int | None:
    value = getattr(obj, name, None)
    return None if value is None else int(value)

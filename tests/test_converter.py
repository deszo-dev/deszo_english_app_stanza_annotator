from types import SimpleNamespace

import pytest

from stanza_annotator.converter import document_to_annotated_document
from stanza_annotator.errors import InputValidationError


def test_document_to_annotated_document_converts_stanza_like_objects() -> None:
    word = SimpleNamespace(
        text="Alice",
        lemma="Alice",
        upos="PROPN",
        xpos="NNP",
        feats="Number=Sing",
        head=2,
        deprel="nsubj",
        start_char=0,
        end_char=5,
    )
    token = SimpleNamespace(text="Alice", words=[word])
    sentence = SimpleNamespace(text="Alice slept.", tokens=[token], words=[word])
    entity = SimpleNamespace(text="Alice", type="PERSON", start_char=0, end_char=5)
    document = SimpleNamespace(sentences=[sentence], entities=[entity])

    result = document_to_annotated_document(document)

    assert result.sentences[0].text == "Alice slept."
    assert result.sentences[0].words[0].lemma == "Alice"
    assert result.sentences[0].words[0].deprel == "nsubj"
    assert result.entities[0].type == "PERSON"


def test_document_to_annotated_document_rejects_invalid_token() -> None:
    token = SimpleNamespace(text="Alice", words=[])
    sentence = SimpleNamespace(text="Alice slept.", tokens=[token], words=[])
    document = SimpleNamespace(sentences=[sentence], entities=[])

    with pytest.raises(InputValidationError):
        document_to_annotated_document(document)

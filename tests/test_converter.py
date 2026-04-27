from types import SimpleNamespace

from stanza_annotator.converter import document_to_annotated_document


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

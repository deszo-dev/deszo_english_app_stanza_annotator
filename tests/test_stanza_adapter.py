from types import SimpleNamespace

from stanza_annotator._internal.stanza_adapter import DefaultStanzaAdapter
from stanza_annotator.config import StanzaAnnotatorConfig


class _ListRejectingPipeline:
    def __call__(self, value: object) -> object:
        if isinstance(value, list):
            raise ValueError(
                "If neither 'pretokenized' or 'no_ssplit' option is enabled, "
                "the input to the TokenizerProcessor must be a string or a "
                "Document object.  Got <class 'list'>"
            )
        word = SimpleNamespace(
            text=str(value),
            lemma=str(value).lower(),
            upos="X",
            deprel="root",
            head=0,
            start_char=0,
            end_char=len(str(value)),
            xpos=None,
            feats=None,
        )
        token = SimpleNamespace(
            text=str(value),
            start_char=0,
            end_char=len(str(value)),
            words=[word],
        )
        sentence = SimpleNamespace(
            text=str(value),
            start_char=0,
            end_char=len(str(value)),
            tokens=[token],
        )
        return SimpleNamespace(sentences=[sentence], entities=[])


def test_default_stanza_adapter_falls_back_when_pipeline_rejects_list_input() -> None:
    adapter = DefaultStanzaAdapter(StanzaAnnotatorConfig())
    adapter._pipeline = _ListRejectingPipeline()

    result = adapter.annotate_batch(["alpha", "beta"])

    assert len(result) == 2
    assert result[0].sentences[0].text == "alpha"
    assert result[1].sentences[0].text == "beta"

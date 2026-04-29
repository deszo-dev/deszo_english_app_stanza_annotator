import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from stanza_annotator import ConfigurationError
from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator.config import StanzaAnnotatorConfig


class FakeAdapter:
    gpu_decision = None

    def __init__(self, document: object) -> None:
        self.document = document
        self.calls: list[str] = []

    def annotate(self, text: str) -> object:
        self.calls.append(text)
        return self.document


def test_empty_input_returns_empty_document_without_loading_stanza() -> None:
    annotator = StanzaAnnotator()

    result = annotator.annotate("   \n\t")

    assert result.sentences == []
    assert result.entities == []


def test_debug_file_records_empty_input(tmp_path: Path) -> None:
    annotator = StanzaAnnotator(
        StanzaAnnotatorConfig(debug=True, debug_dir=tmp_path, use_gpu=True)
    )

    annotator.annotate("")

    debug_files = list(tmp_path.glob("annotation-*.json"))
    assert len(debug_files) == 1
    payload = json.loads(debug_files[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["empty_input"] is True
    assert payload["metadata"]["gpu_requested"] is True
    assert payload["metadata"]["gpu_effective"] is False


def test_annotate_uses_adapter_and_writes_debug(tmp_path: Path) -> None:
    word = SimpleNamespace(
        text="I",
        lemma="I",
        upos="PRON",
        xpos=None,
        feats="Person=1|Number=Sing",
        head=2,
        deprel="nsubj",
        start_char=0,
        end_char=1,
    )
    token = SimpleNamespace(text="I", words=[word])
    sentence = SimpleNamespace(text="I am tired.", tokens=[token], words=[word])
    document = SimpleNamespace(
        sentences=[sentence],
        entities=[],
        to_dict=lambda: {"sentences": [{"text": "I am tired."}]},
    )
    adapter = FakeAdapter(document)

    annotator = StanzaAnnotator(
        {
            "debug": True,
            "debug_dir": tmp_path,
            "use_gpu": False,
            "auto_download": True,
        },
        adapter=adapter,
    )

    result = annotator.annotate("I am tired.")

    assert adapter.calls == ["I am tired."]
    assert result.sentences[0].words[0].upos == "PRON"
    assert len(list(tmp_path.glob("annotation-*.json"))) == 1


def test_unsupported_processors_raise_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        StanzaAnnotator({"processors": "tokenize,pos"})

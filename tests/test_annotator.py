import json
from types import SimpleNamespace

from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator.config import StanzaAnnotatorConfig


def test_empty_input_returns_empty_document_without_loading_stanza() -> None:
    annotator = StanzaAnnotator()

    result = annotator.annotate("   \n\t")

    assert result.sentences == []
    assert result.entities == []


def test_debug_file_records_empty_input_and_gpu_fallback(tmp_path) -> None:
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
    assert "gpu_fallback_reason" in payload["metadata"]


def test_annotate_uses_pipeline_and_writes_debug(monkeypatch, tmp_path) -> None:
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

    class FakePipeline:
        def __call__(self, text: str):
            assert text == "I am tired."
            return document

    class FakeStanza:
        @staticmethod
        def download(*args, **kwargs) -> None:
            return None

        @staticmethod
        def Pipeline(*args, **kwargs):
            assert kwargs["use_gpu"] is False
            return FakePipeline()

    monkeypatch.setattr(StanzaAnnotator, "_import_stanza", staticmethod(lambda: FakeStanza))

    annotator = StanzaAnnotator(
        {
            "debug": True,
            "debug_dir": tmp_path,
            "use_gpu": False,
            "auto_download": True,
        }
    )

    result = annotator.annotate("I am tired.")

    assert result.sentences[0].words[0].upos == "PRON"
    assert len(list(tmp_path.glob("annotation-*.json"))) == 1

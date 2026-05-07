from pathlib import Path

from stanza_annotator.annotator import StanzaAnnotator
from stanza_annotator.runtime_metadata import (
    canonical_json,
    directory_source_fingerprint,
    stage_fingerprint,
)


def test_stanza_annotator_exposes_runtime_metadata() -> None:
    metadata = StanzaAnnotator({"use_gpu": False}).runtime_metadata()

    assert metadata.pipeline_name == "stanza_annotator"
    assert metadata.pipeline_contract_version
    assert metadata.stages

    for stage_name, stage_metadata in metadata.stages.items():
        assert stage_metadata.stage_name == stage_name
        assert stage_metadata.stage_contract_version
        assert stage_metadata.output_schema_version
        assert stage_metadata.config_contract_version
        assert stage_metadata.module_version


def test_local_stage_source_fingerprint_is_present() -> None:
    metadata = StanzaAnnotator({"use_gpu": False}).stage_runtime_metadata()

    assert metadata.source_fingerprint is not None
    assert metadata.source_fingerprint.startswith("tree-sha256:")


def test_runtime_metadata_is_deterministic() -> None:
    annotator = StanzaAnnotator({"use_gpu": False})

    first = canonical_json(annotator.runtime_metadata())
    second = canonical_json(annotator.runtime_metadata())

    assert first == second


def test_stage_fingerprint_includes_config_and_inputs() -> None:
    metadata = StanzaAnnotator({"use_gpu": False}).stage_runtime_metadata()

    base = stage_fingerprint(
        metadata,
        normalized_stage_config={"use_gpu": False},
        input_artifact_hashes={"input.txt": "sha256:aaa"},
    )
    changed_config = stage_fingerprint(
        metadata,
        normalized_stage_config={"use_gpu": True},
        input_artifact_hashes={"input.txt": "sha256:aaa"},
    )
    changed_input = stage_fingerprint(
        metadata,
        normalized_stage_config={"use_gpu": False},
        input_artifact_hashes={"input.txt": "sha256:bbb"},
    )

    assert base != changed_config
    assert base != changed_input


def test_directory_source_fingerprint_changes_when_source_changes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    first = directory_source_fingerprint(tmp_path)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    second = directory_source_fingerprint(tmp_path)

    assert first.startswith("tree-sha256:")
    assert second.startswith("tree-sha256:")
    assert first != second

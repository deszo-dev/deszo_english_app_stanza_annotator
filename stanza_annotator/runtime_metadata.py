from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field, is_dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

CompatibilityMode = Literal[
    "exact",
    "semver_compatible",
    "schema_compatible",
    "hash_exact",
]

STAGE_NAME = "stanza_annotation"
STAGE_CONTRACT_VERSION = "1"
OUTPUT_SCHEMA_VERSION = "stanza-annotator-output.v1"
CONFIG_CONTRACT_VERSION = "stanza-annotator-config.v1"
PIPELINE_NAME = "stanza_annotator"
PIPELINE_CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class RuntimeDependency:
    name: str
    version: str
    source: str
    compatibility: CompatibilityMode = "exact"
    source_fingerprint: str | None = None


@dataclass(frozen=True)
class RuntimeAsset:
    name: str
    kind: str
    sha256: str
    compatibility: CompatibilityMode = "hash_exact"


@dataclass(frozen=True)
class StageRuntimeMetadata:
    stage_name: str
    stage_contract_version: str
    output_schema_version: str
    config_contract_version: str
    module_version: str
    source_fingerprint: str | None = None
    dependencies: list[RuntimeDependency] = field(default_factory=list)
    assets: list[RuntimeAsset] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineRuntimeMetadata:
    pipeline_name: str
    pipeline_version: str
    pipeline_contract_version: str
    stages: dict[str, StageRuntimeMetadata]


def stanza_annotation_runtime_metadata() -> StageRuntimeMetadata:
    return StageRuntimeMetadata(
        stage_name=STAGE_NAME,
        stage_contract_version=STAGE_CONTRACT_VERSION,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        config_contract_version=CONFIG_CONTRACT_VERSION,
        module_version=get_module_version("stanza-annotator"),
        source_fingerprint=source_fingerprint_for_package(),
        dependencies=[
            RuntimeDependency(
                name="stanza",
                version=get_dependency_version("stanza"),
                source="package",
                compatibility="exact",
            ),
            RuntimeDependency(
                name="pydantic",
                version=get_dependency_version("pydantic"),
                source="package",
                compatibility="exact",
            ),
            RuntimeDependency(
                name="torch",
                version=get_dependency_version("torch"),
                source="package",
                compatibility="exact",
            ),
        ],
        assets=[],
    )


def pipeline_runtime_metadata() -> PipelineRuntimeMetadata:
    stage_metadata = stanza_annotation_runtime_metadata()
    return PipelineRuntimeMetadata(
        pipeline_name=PIPELINE_NAME,
        pipeline_version=stage_metadata.module_version,
        pipeline_contract_version=PIPELINE_CONTRACT_VERSION,
        stages={stage_metadata.stage_name: stage_metadata},
    )


def canonical_json(value: object) -> str:
    return json.dumps(
        _to_jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def stage_fingerprint(
    metadata: StageRuntimeMetadata,
    *,
    normalized_stage_config: object | None = None,
    input_artifact_hashes: dict[str, str] | None = None,
    pipeline_contract_version: str = PIPELINE_CONTRACT_VERSION,
) -> str:
    payload = {
        "metadata": metadata,
        "normalized_stage_config_hash": _hash_jsonable(
            normalized_stage_config if normalized_stage_config is not None else {}
        ),
        "input_artifact_hashes": input_artifact_hashes or {},
        "pipeline_contract_version": pipeline_contract_version,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def source_fingerprint_for_package() -> str:
    package_root = Path(__file__).resolve().parent
    return directory_source_fingerprint(package_root)


def directory_source_fingerprint(root: Path) -> str:
    relevant_suffixes = {
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".sql",
        ".txt",
    }
    ignored_dirs = {
        "__pycache__",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".venv",
        "node_modules",
    }
    digest = hashlib.sha256()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in relevant_suffixes:
            continue
        if any(part in ignored_dirs for part in path.relative_to(root).parts):
            continue

        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    return f"tree-sha256:{digest.hexdigest()}"


def git_source_fingerprint(root: Path) -> str | None:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None

    if not commit:
        return None
    return f"git:{commit}-dirty" if dirty else f"git:{commit}"


def get_dependency_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "unknown"


def get_module_version(package_name: str) -> str:
    installed = get_dependency_version(package_name)
    if installed != "unknown":
        return installed

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject.exists():
        return "unknown"

    in_project_section = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project_section = True
            continue
        if in_project_section and stripped.startswith("["):
            break
        if in_project_section and stripped.startswith("version"):
            _, _, raw_value = stripped.partition("=")
            return raw_value.strip().strip('"') or "unknown"
    return "unknown"


def _hash_jsonable(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _to_jsonable(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value

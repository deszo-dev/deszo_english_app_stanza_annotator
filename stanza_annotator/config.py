from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_PROCESSORS: Final[Literal["tokenize,mwt,pos,lemma,depparse,ner"]] = (
    "tokenize,mwt,pos,lemma,depparse,ner"
)
LogLevel = Literal["debug", "info", "warning", "error"]
ContentSelectionMode = Literal[
    "chapter_text_only",
    "canonical_from_epub_config",
    "all_readable",
    "chapters_only",
    "custom",
]


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    level: LogLevel = "info"


class ContentSelectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ContentSelectionMode = "chapter_text_only"
    include_chapters: bool = False
    include_front_matter: bool = False
    include_back_matter: bool = False
    include_footnotes: bool = False
    include_chapter_titles: bool = False
    include_section_titles: bool = False

    @model_validator(mode="after")
    def validate_custom_mode(self) -> "ContentSelectionConfig":
        if self.mode != "custom":
            return self
        return self


class StanzaAnnotatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: Literal["en"] = "en"
    processors: Literal["tokenize,mwt,pos,lemma,depparse,ner"] = DEFAULT_PROCESSORS
    use_gpu: bool = False
    tokenize_pretokenized: Literal[False] = False
    auto_download: bool = True
    content_selection: ContentSelectionConfig = Field(
        default_factory=ContentSelectionConfig
    )
    batch_size: int = Field(default=32, ge=1, le=1024)
    max_text_unit_chars: int = Field(default=100000, ge=1, le=1000000)
    max_output_json_bytes: int = Field(default=1073741824, ge=1024, le=1073741824)
    include_debug: bool = False
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

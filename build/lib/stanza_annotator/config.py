from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_PROCESSORS: Final[Literal["tokenize,mwt,pos,lemma,depparse,ner"]] = (
    "tokenize,mwt,pos,lemma,depparse,ner"
)
LogLevel = Literal["debug", "info", "warning", "error"]


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    level: LogLevel = "info"


class StanzaAnnotatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, frozen=True)

    language: Literal["en"] = "en"
    use_gpu: bool = True
    processors: Literal["tokenize,mwt,pos,lemma,depparse,ner"] = DEFAULT_PROCESSORS
    tokenize_pretokenized: bool = False
    auto_download: bool = True
    debug: bool = False
    debug_dir: Path = Field(default_factory=lambda: Path("debug"))
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("processors")
    @classmethod
    def validate_processors(cls, value: str) -> str:
        if value != DEFAULT_PROCESSORS:
            raise ValueError(f"processors must be exactly {DEFAULT_PROCESSORS!r}")
        return value

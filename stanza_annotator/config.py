from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_PROCESSORS = "tokenize,mwt,pos,lemma,depparse,ner"


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    level: str = "info"


class StanzaAnnotatorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    language: str = "en"
    use_gpu: bool = True
    processors: str = DEFAULT_PROCESSORS
    tokenize_pretokenized: bool = False
    auto_download: bool = True
    debug: bool = False
    debug_dir: Path = Field(default_factory=lambda: Path("debug"))
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

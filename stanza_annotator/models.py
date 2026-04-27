from pydantic import BaseModel, ConfigDict, Field


class Word(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    lemma: str
    upos: str
    xpos: str | None = None
    feats: str | None = None
    head: int
    deprel: str
    start_char: int | None = None
    end_char: int | None = None


class Token(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    words: list[Word] = Field(default_factory=list)


class Sentence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    tokens: list[Token] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    type: str
    start_char: int | None = None
    end_char: int | None = None


class AnnotatedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentences: list[Sentence] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)

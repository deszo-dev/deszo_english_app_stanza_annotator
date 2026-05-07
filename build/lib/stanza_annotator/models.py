from pydantic import BaseModel, ConfigDict, Field, model_validator


class Word(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    lemma: str
    upos: str
    xpos: str | None = None
    feats: str | None = None
    head: int
    deprel: str
    start_char: int
    end_char: int

    @model_validator(mode="after")
    def validate_invariants(self) -> "Word":
        if not self.text:
            raise ValueError("word text must not be empty")
        if not self.upos:
            raise ValueError("word upos must not be empty")
        if not self.deprel:
            raise ValueError("word deprel must not be empty")
        if self.start_char > self.end_char:
            raise ValueError("word start_char must be <= end_char")
        return self


class Token(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_invariants(self) -> "Token":
        if not self.words:
            raise ValueError("token must contain at least one word")
        return self


class Sentence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    tokens: list[Token] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    type: str
    start_char: int
    end_char: int

    @model_validator(mode="after")
    def validate_invariants(self) -> "Entity":
        if not self.text:
            raise ValueError("entity text must not be empty")
        if not self.type:
            raise ValueError("entity type must not be empty")
        if self.start_char > self.end_char:
            raise ValueError("entity start_char must be <= end_char")
        return self


class AnnotatedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sentences: list[Sentence] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)

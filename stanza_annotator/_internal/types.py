from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RawStanzaWord:
    text: str
    lemma: str
    upos: str
    deprel: str
    head: int
    start_char: int
    end_char: int
    xpos: str | None = None
    feats: str | None = None


@dataclass(frozen=True)
class RawStanzaToken:
    text: str
    start_char: int
    end_char: int
    words: Sequence[RawStanzaWord] = field(default_factory=list)


@dataclass(frozen=True)
class RawStanzaSentence:
    text: str
    start_char: int
    end_char: int
    tokens: Sequence[RawStanzaToken] = field(default_factory=list)


@dataclass(frozen=True)
class RawStanzaEntity:
    text: str
    type: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class RawStanzaDocument:
    sentences: Sequence[RawStanzaSentence] = field(default_factory=list)
    entities: Sequence[RawStanzaEntity] = field(default_factory=list)


class StanzaAdapter(Protocol):
    def annotate_batch(
        self, texts: Sequence[str]
    ) -> Sequence[RawStanzaDocument]:  # pragma: no cover - protocol
        """Return one raw Stanza document per input text, preserving order."""

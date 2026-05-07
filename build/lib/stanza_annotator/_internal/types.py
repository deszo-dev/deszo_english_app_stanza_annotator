from __future__ import annotations

from typing import Any, Protocol


class StanzaAdapter(Protocol):
    def annotate(self, text: str) -> Any:
        """Return an adapter-owned raw Stanza document."""

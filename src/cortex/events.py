"""Presentation-independent sync progress events."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyncEvent:
    phase: str
    completed: int = 0
    total: int = 0
    source: str = ""
    status: str = ""
    examples: int = 0
    message: str = ""

    @property
    def fraction(self) -> float:
        """Overall work progress, with publication reserved for the final step."""
        portion = min(1.0, max(0.0, self.completed / self.total)) if self.total else 0.0
        if self.phase in {"sources", "source"}:
            return 0.30 * portion
        if self.phase == "filter":
            return 0.30 + 0.55 * portion
        if self.phase == "merge":
            return 0.85
        if self.phase == "publish":
            return 0.85 + 0.14 * portion
        if self.phase == "done":
            return 1.0
        return 0.0

"""Typed row models for the SQLite layer."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ScrapeSession:
    session_id: str
    url: str
    domain: str
    created_at: str
    records_count: int
    pages_processed: int
    status: str
    duration_seconds: float
    template: str = "generic"
    dataset_file: str | None = None
    message: str = ""

    @classmethod
    def from_row(cls, row) -> "ScrapeSession":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)

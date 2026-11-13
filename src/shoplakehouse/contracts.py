"""Versioned data contracts shared by extraction, Spark, loaders and catalog."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Table:
    name: str
    source: str
    columns: dict[str, str]
    required: tuple[str, ...]
    checks: dict[str, str]
    pii: tuple[str, ...] = ()
    drop: tuple[str, ...] = ()
    key: str = "id"

    @property
    def silver_columns(self) -> dict[str, str]:
        return {
            k: ("string" if k in self.pii else v)
            for k, v in self.columns.items()
            if k not in self.drop
        }


def load(path: Path) -> dict[str, Table]:
    raw = yaml.safe_load(path.read_text())
    result = {}
    for name, item in raw["tables"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"Unsafe entity name: {name}")
        result[name] = Table(
            name=name,
            source=item["source"],
            columns=item["columns"],
            required=tuple(item["required"]),
            checks=item.get("checks", {}),
            pii=tuple(item.get("pii", [])),
            drop=tuple(item.get("drop", [])),
            key=item.get("key", "id"),
        )
    return result


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

"""Loads SAP catalogs from YAML and provides classification lookups.

Used by:
  - the parser (during ingestion, to populate operation_category and
    entity_classification on each LogEvent)
  - the scope filter engine (when use case YAMLs reference categories)
  - prompt builders (to inject customer-specific overrides)
"""

from __future__ import annotations

import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from config import SAP_CONFIG_DIR


class TcodeCatalog:
    def __init__(self, raw: dict[str, Any]):
        self._raw = raw
        # Build reverse index: tcode -> category
        self._tcode_to_category: dict[str, str] = {}
        for category, tcodes in (raw.get("categories") or {}).items():
            for tc in tcodes or []:
                self._tcode_to_category[tc] = category
        self._patterns: list[dict[str, Any]] = raw.get("custom_pattern_rules") or []

    def category_for(self, tcode: str | None) -> str | None:
        if not tcode:
            return None
        # Exact match first
        if tcode in self._tcode_to_category:
            return self._tcode_to_category[tcode]
        # Then patterns
        for rule in self._patterns:
            if fnmatch.fnmatch(tcode, rule["matches"]):
                return rule.get("category")
        return None

    def all_tcodes_in_categories(self, categories: list[str]) -> set[str]:
        return {
            tc
            for tc, cat in self._tcode_to_category.items()
            if cat in categories
        }

    def custom_overrides(self) -> list[dict[str, Any]]:
        """Returned to prompt builder as customer-specific overrides."""
        return self._patterns


class TableCatalog:
    def __init__(self, raw: dict[str, Any]):
        self._raw = raw
        # Build reverse index: table -> (classification, sensitivity)
        self._table_to_classification: dict[str, tuple[str, str]] = {}
        for classification, info in (raw.get("classifications") or {}).items():
            sensitivity = info.get("sensitivity", "medium")
            for tbl in info.get("tables") or []:
                self._table_to_classification[tbl] = (classification, sensitivity)
        self._patterns: list[dict[str, Any]] = raw.get("custom_pattern_rules") or []

    def classification_for(self, table: str | None) -> str | None:
        if not table:
            return None
        if table in self._table_to_classification:
            return self._table_to_classification[table][0]
        for rule in self._patterns:
            if fnmatch.fnmatch(table, rule["matches"]):
                return rule.get("classification")
        return None

    def sensitivity_for(self, table: str | None) -> str | None:
        if not table:
            return None
        if table in self._table_to_classification:
            return self._table_to_classification[table][1]
        for rule in self._patterns:
            if fnmatch.fnmatch(table, rule["matches"]):
                return rule.get("sensitivity")
        return None

    def custom_overrides(self) -> list[dict[str, Any]]:
        return self._patterns


@lru_cache(maxsize=1)
def load_tcode_catalog() -> TcodeCatalog:
    path = SAP_CONFIG_DIR / "tcode_catalog.yaml"
    with open(path) as f:
        return TcodeCatalog(yaml.safe_load(f))


@lru_cache(maxsize=1)
def load_table_catalog() -> TableCatalog:
    path = SAP_CONFIG_DIR / "table_catalog.yaml"
    with open(path) as f:
        return TableCatalog(yaml.safe_load(f))


@lru_cache(maxsize=8)
def load_use_case(use_case_name: str) -> dict[str, Any]:
    path = SAP_CONFIG_DIR / "use_cases" / f"{use_case_name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def list_use_cases() -> list[str]:
    """All use case names registered for SAP."""
    use_cases_dir: Path = SAP_CONFIG_DIR / "use_cases"
    return sorted(p.stem for p in use_cases_dir.glob("*.yaml"))

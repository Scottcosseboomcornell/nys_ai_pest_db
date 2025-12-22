from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set, Tuple


@dataclass(frozen=True)
class TargetInfo:
    simplified: str
    target_type: str


class TargetLookupCsv:
    """Lightweight lookup using the old app's CSV mapping.

    This is a stopgap (per your request) until we build a NYS-specific target
    normalization pipeline + precomputed indices.
    """

    def __init__(self, csv_path: Optional[Path] = None) -> None:
        self.csv_path = csv_path or self._default_csv_path()
        self._loaded: bool = False
        self._by_original: Dict[str, TargetInfo] = {}
        self._target_types: Set[str] = set()

    @staticmethod
    def _default_csv_path() -> Path:
        # web_application_nys/app -> web_application_nys -> .. -> web_application_old/<csv>
        here = Path(__file__).resolve()
        root = here.parents[1]
        return (root / ".." / "web_application_old" / "target_analysis_with_suggestions.csv").resolve()

    def _load(self) -> None:
        if self._loaded:
            return

        if not self.csv_path.exists():
            # Fail "soft": we still want the app to run; everything becomes Other.
            self._loaded = True
            return

        by_original: Dict[str, TargetInfo] = {}
        target_types: Set[str] = set()

        with self.csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            # Expected columns (from old app output):
            # - Original_Target
            # - Suggested_Simplified_Target and Disease Common Name
            # - Target_Type
            for row in reader:
                orig = (row.get("Original_Target") or "").strip()
                if not orig:
                    continue

                simplified = (row.get("Suggested_Simplified_Target and Disease Common Name") or "").strip()
                target_type = (row.get("Target_Type") or "").strip()

                if not simplified:
                    simplified = orig
                if not target_type:
                    target_type = "Other"

                by_original[orig.lower()] = TargetInfo(simplified=simplified, target_type=target_type)
                target_types.add(target_type)

        self._by_original = by_original
        self._target_types = target_types
        self._loaded = True

    def lookup(self, original_target: str) -> TargetInfo:
        self._load()
        key = (original_target or "").strip().lower()
        if not key:
            return TargetInfo(simplified="", target_type="Other")
        return self._by_original.get(key, TargetInfo(simplified=original_target.strip(), target_type="Other"))

    def get_target_types(self) -> Tuple[str, ...]:
        self._load()
        if not self._target_types:
            return ("Other",)
        return tuple(sorted(self._target_types))



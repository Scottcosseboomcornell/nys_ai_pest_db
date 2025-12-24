from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class DatasetStats:
    total_files: int
    total_records: int
    last_updated_ts: Optional[float]


def normalize_crop_key(name: str) -> str:
    """Normalize crop names to a stable, singular, lowercase key.

    This is used for:
    - de-duplicating crops (Apple/Apples, Grape/Grapes, etc.)
    - matching user-selected crop filters against raw JSON crop names
    """

    s = str(name or "").strip()
    if not s:
        return ""

    # Remove parenthetical content (e.g. "Onion (green)")
    if "(" in s:
        s = s.split("(")[0].strip()

    # Normalize whitespace
    s = " ".join(s.split())

    # Special phrase-level plural fixes
    phrase_map = {
        "dry bulb onions": "dry bulb onion",
        "green onions": "green onion",
    }
    low = s.lower()
    if low in phrase_map:
        return phrase_map[low]

    # Normalize last token to singular (handles "Apples", "Strawberries", "Potatoes", etc.)
    parts = low.split(" ")
    last = parts[-1]

    irregular = {
        "strawberries": "strawberry",
        "blueberries": "blueberry",
        "raspberries": "raspberry",
        "blackberries": "blackberry",
        "cranberries": "cranberry",
        "cherries": "cherry",
        "potatoes": "potato",
        "tomatoes": "tomato",
        "grapes": "grape",
        "apples": "apple",
        "onions": "onion",
        "soybeans": "soybean",
        "pumpkins": "pumpkin",
        "beans": "bean",
    }

    if last in irregular:
        last = irregular[last]
    elif last.endswith("ies") and len(last) > 3:
        # berries -> berry
        last = last[:-3] + "y"
    elif last.endswith("oes") and len(last) > 3:
        # potatoes -> potato, tomatoes -> tomato
        last = last[:-2]
    elif last.endswith("s") and len(last) > 3 and not last.endswith(("ss", "us", "is")):
        # grapes -> grape, apples -> apple
        last = last[:-1]

    parts[-1] = last
    return " ".join(parts).strip()


def crop_display_name(name: str) -> str:
    """Convert normalized crop key to display form."""

    key = normalize_crop_key(name)
    if not key:
        return ""
    return key.title()


def _default_json_dir() -> Path:
    # web_application_nys/app/data.py -> web_application_nys -> ../altered_json
    here = Path(__file__).resolve()
    app_dir = here.parents[1]
    return (app_dir / ".." / "altered_json").resolve()


def get_json_dir() -> Path:
    override = os.environ.get("NYS_OUTPUT_JSON_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return _default_json_dir()


class JsonPesticideStore:
    """Loads NYS pesticide JSON files and provides simple indexed lookups."""

    def __init__(self, json_dir: Optional[Path] = None, cache_seconds: int = 0):
        self.json_dir = json_dir or get_json_dir()
        self.cache_seconds = cache_seconds

        self._loaded_at: float = 0
        self._records: List[Dict[str, Any]] = []
        self._epa_index: Dict[str, Dict[str, Any]] = {}
        self._file_index: Dict[str, Dict[str, Any]] = {}
        self._trade_index: Dict[str, List[Dict[str, Any]]] = {}
        self._company_index: Dict[str, List[Dict[str, Any]]] = {}
        self._ingredient_index: Dict[str, List[Dict[str, Any]]] = {}
        # Derived caches (computed lazily)
        self._crops_cache: Optional[List[str]] = None

    def _needs_reload(self) -> bool:
        if not self._records:
            return True
        if self.cache_seconds <= 0:
            return False
        return (time.time() - self._loaded_at) > self.cache_seconds

    def load(self, force: bool = False) -> None:
        if not force and not self._needs_reload():
            return

        if not self.json_dir.exists() or not self.json_dir.is_dir():
            raise FileNotFoundError(f"JSON directory not found: {self.json_dir}")

        records: List[Dict[str, Any]] = []
        epa_index: Dict[str, Dict[str, Any]] = {}
        file_index: Dict[str, Dict[str, Any]] = {}
        trade_index: Dict[str, List[Dict[str, Any]]] = {}
        company_index: Dict[str, List[Dict[str, Any]]] = {}
        ingredient_index: Dict[str, List[Dict[str, Any]]] = {}

        for p in sorted(self.json_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue

            # Expect the same overall shape as the existing pipeline output
            pesticide = data.get("pesticide") if isinstance(data, dict) else None
            if not isinstance(pesticide, dict):
                continue

            # Normalize company field: prefer altered_json's `company_name`
            # but keep backwards-compat with older keys.
            if "company_name" not in pesticide or not str(pesticide.get("company_name") or "").strip():
                if str(pesticide.get("COMPANY_NAME") or "").strip():
                    pesticide["company_name"] = pesticide.get("COMPANY_NAME")
            if "COMPANY_NAME" not in pesticide or not str(pesticide.get("COMPANY_NAME") or "").strip():
                if str(pesticide.get("company_name") or "").strip():
                    pesticide["COMPANY_NAME"] = pesticide.get("company_name")

            # Add filename so the UI/debugging can reference the source
            pesticide = {**pesticide, "_source_file": p.name}
            records.append(pesticide)

            epa = str(pesticide.get("epa_reg_no") or "").strip()
            if epa:
                epa_index[epa.lower()] = pesticide

            # Exact lookup by source filename (unique per JSON/PDF)
            file_index[p.name] = pesticide

            trade = str(pesticide.get("trade_Name") or "").strip().lower()
            if trade:
                trade_index.setdefault(trade, []).append(pesticide)

            # Index by normalized company name (use `company_name`)
            company = str(pesticide.get("company_name") or pesticide.get("COMPANY_NAME") or "").strip().lower()
            if company:
                company_index.setdefault(company, []).append(pesticide)

            for ing in pesticide.get("Active_Ingredients", []) or []:
                if not isinstance(ing, dict):
                    continue
                name = str(ing.get("name") or "").strip().lower()
                if name:
                    ingredient_index.setdefault(name, []).append(pesticide)

        # Stable sort by trade name for consistent pagination
        records.sort(key=lambda r: str(r.get("trade_Name") or "").lower())

        self._records = records
        self._epa_index = epa_index
        self._file_index = file_index
        self._trade_index = trade_index
        self._company_index = company_index
        self._ingredient_index = ingredient_index
        self._loaded_at = time.time()
        self._crops_cache = None

    def all_records(self) -> List[Dict[str, Any]]:
        self.load()
        return self._records

    def iter_applications(self) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Yield (pesticide, application_info_entry)."""

        self.load()
        for p in self._records:
            for app in p.get("Application_Info", []) or []:
                if isinstance(app, dict):
                    yield p, app

    def list_crops(self) -> List[str]:
        """Return unique crop names (title-cased) from Application_Info.Target_Crop."""

        self.load()
        if self._crops_cache is not None:
            return self._crops_cache

        # norm_key -> display
        crops: Dict[str, str] = {}
        for _, app in self.iter_applications():
            for crop in app.get("Target_Crop", []) or []:
                if not isinstance(crop, dict):
                    continue
                raw = str(crop.get("name") or "").strip()
                norm = normalize_crop_key(raw)
                if not norm:
                    continue
                # Preserve a consistent display name (singular + title case)
                crops.setdefault(norm, crop_display_name(raw))

        self._crops_cache = sorted(crops.values(), key=lambda x: x.lower())
        return self._crops_cache

    def stats(self) -> DatasetStats:
        self.load()
        json_files = list(self.json_dir.glob("*.json"))
        last_updated = None
        if json_files:
            last_updated = max((f.stat().st_mtime for f in json_files), default=None)
        return DatasetStats(
            total_files=len(json_files),
            total_records=len(self._records),
            last_updated_ts=last_updated,
        )

    def list_page(self, page: int, per_page: int) -> Tuple[List[Dict[str, Any]], int]:
        self.load()
        if per_page <= 0:
            per_page = 50
        per_page = min(per_page, 500)
        page = max(page, 1)

        total = len(self._records)
        start = (page - 1) * per_page
        end = start + per_page
        return self._records[start:end], total

    def get_by_epa(self, epa_reg_no: str) -> Optional[Dict[str, Any]]:
        self.load()
        key = (epa_reg_no or "").strip().lower()
        if not key:
            return None
        return self._epa_index.get(key)

    def get_by_source_file(self, source_file: str) -> Optional[Dict[str, Any]]:
        """Lookup a pesticide by its JSON filename (exact match)."""
        self.load()
        key = (source_file or "").strip()
        if not key:
            return None
        return self._file_index.get(key)

    def search(self, query: str, search_type: str = "both", limit: int = 200) -> List[Dict[str, Any]]:
        self.load()
        q = (query or "").strip().lower()
        if not q:
            return []

        limit = min(max(int(limit), 1), 500)

        def contains(text: Any) -> bool:
            return q in str(text or "").lower()

        results: List[Dict[str, Any]] = []
        seen: set[int] = set()

        def add_many(items: List[Dict[str, Any]]) -> None:
            for item in items:
                if len(results) >= limit:
                    return
                oid = id(item)
                if oid in seen:
                    continue
                seen.add(oid)
                results.append(item)

        # Exact-key indices
        if search_type == "epa_reg_no":
            hit = self._epa_index.get(q)
            if hit:
                return [hit]
            # fallback partial scan
            for r in self._records:
                if contains(r.get("epa_reg_no")):
                    add_many([r])
            return results

        if search_type == "trade_Name":
            add_many(self._trade_index.get(q, []))
            if results:
                return results

        if search_type == "company":
            add_many(self._company_index.get(q, []))
            if results:
                return results

        if search_type == "active_ingredient":
            add_many(self._ingredient_index.get(q, []))
            if results:
                return results

        # "both" (and any unknown type) => partial scan with lightweight ranking
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in self._records:
            score = 0.0
            trade = r.get("trade_Name")
            epa = r.get("epa_reg_no")
            company = r.get("company_name") or r.get("COMPANY_NAME")

            tl = str(trade or "").lower()
            if tl == q:
                score += 10
            elif tl.startswith(q):
                score += 6
            elif q in tl:
                score += 4

            el = str(epa or "").lower()
            if el == q:
                score += 8
            elif q in el:
                score += 3

            if q in str(company or "").lower():
                score += 1

            if score == 0:
                # Try ingredients
                for ing in r.get("Active_Ingredients", []) or []:
                    if isinstance(ing, dict) and q in str(ing.get("name") or "").lower():
                        score += 2
                        break

            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda t: t[0], reverse=True)
        return [r for _, r in scored[:limit]]

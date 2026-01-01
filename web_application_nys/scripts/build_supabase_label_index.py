#!/usr/bin/env python3
"""
Build Supabase-backed indexes for fast search + guided filter.

This script reads `../altered_json/*.json` (relative to web_application_nys/)
and upserts into:
  - public.label_index
  - public.label_crop_target

Requires environment variables:
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY   (recommended; write access)

Optional:
  - NYS_OUTPUT_JSON_DIR         (override JSON dir)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from supabase import create_client
except Exception as e:  # pragma: no cover
    create_client = None  # type: ignore


# Ensure we can import app helpers (normalize_crop_key)
WEB_APP_DIR = Path(__file__).resolve().parents[1]  # web_application_nys/
if str(WEB_APP_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_APP_DIR))

from app.data import get_json_dir, normalize_crop_key  # noqa: E402


def _env(name: str) -> str:
    v = os.environ.get(name, "")
    return v.strip()


def _require_env(name: str) -> str:
    v = _env(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def _chunks(seq: Sequence[dict], size: int) -> Iterable[List[dict]]:
    if size <= 0:
        size = 500
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


def normalize_moa_code(code: str) -> str:
    raw = str(code or "").strip()
    if not raw or raw == "?":
        return ""
    s = raw.upper().replace("\t", " ")
    s = " ".join(s.split())

    import re

    m = re.search(r"\b(FRAC|IRAC|HRAC)\s*([0-9]+[A-Z]?)\b", s)
    if m:
        return f"{m.group(1)} {m.group(2)}".strip()
    return s


def split_moa_tokens(raw_moa: str) -> List[str]:
    s = str(raw_moa or "").strip()
    if not s or s == "?" or s.upper() == "N/A":
        return []
    out: List[str] = []
    seen: set[str] = set()
    for part in s.replace("/", ",").replace(";", ",").split(","):
        norm = normalize_moa_code(part)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


@dataclass
class CropMaps:
    unified_by_original_norm: dict[str, str]
    deployed_by_original_norm: dict[str, bool]


@dataclass
class TargetMapEntry:
    refined_target_l: str
    display_target_type_l: str
    deployed: bool
    main_target_list: bool


def load_crop_maps(nyspad_root: Path) -> CropMaps:
    import csv

    path = nyspad_root / "crop_names_unified.csv"
    unified: dict[str, str] = {}
    deployed: dict[str, bool] = {}
    if not path.exists():
        return CropMaps(unified_by_original_norm=unified, deployed_by_original_norm=deployed)

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original = str(row.get("original_crop_name") or "").strip()
            if not original or original.lower() == "nan":
                continue
            edited = str(row.get("edited_crop_name") or "").strip()
            if edited.lower() == "nan":
                edited = ""

            deployed_raw = row.get("deployed", "true")
            deployed_val = True
            if isinstance(deployed_raw, str):
                deployed_val = deployed_raw.strip().lower() in ("true", "1", "yes", "y")
            elif deployed_raw is not None:
                deployed_val = bool(deployed_raw)

            orig_norm = normalize_crop_key(original)
            if not orig_norm:
                continue
            unified_norm = normalize_crop_key(edited) if edited else orig_norm
            unified[orig_norm] = unified_norm or orig_norm
            deployed[orig_norm] = deployed_val

    return CropMaps(unified_by_original_norm=unified, deployed_by_original_norm=deployed)


def load_target_mapping(nyspad_root: Path) -> dict[tuple[str, str], TargetMapEntry]:
    """
    Build mapping keyed by (orig_crop_norm, orig_target_norm) matching current Flask guided-filter logic.
    """
    import csv

    path = nyspad_root / "target_names_unified.csv"
    mapping: dict[tuple[str, str], TargetMapEntry] = {}
    if not path.exists():
        return mapping

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original_target = str(row.get("original_target_name") or "").strip()
            original_crop = str(row.get("original_crop") or "").strip()
            original_target_type = str(row.get("original_target_type") or "").strip() or "Other"
            source_target_type = str(row.get("source_target_type") or "").strip()
            new_target = str(row.get("new_target_name") or "").strip()

            if not original_target or not original_crop:
                continue
            if new_target.lower() == "nan":
                new_target = ""
            if source_target_type.lower() == "nan":
                source_target_type = ""

            # deployed defaults True
            deployed_raw = row.get("deployed", "true")
            deployed_val = True
            if isinstance(deployed_raw, str):
                deployed_val = deployed_raw.strip().lower() in ("true", "1", "yes", "y")
            elif deployed_raw is not None:
                deployed_val = bool(deployed_raw)

            # main_target_list defaults False
            main_raw = row.get("main_target_list", "false")
            main_val = False
            if isinstance(main_raw, str):
                main_val = main_raw.strip().lower() in ("true", "1", "yes", "y")
            elif main_raw is not None:
                main_val = bool(main_raw)

            orig_crop_norm = normalize_crop_key(original_crop)
            orig_target_norm = normalize_crop_key(original_target)
            if not orig_crop_norm or not orig_target_norm:
                continue

            refined_target = (new_target if new_target else original_target).strip()
            refined_l = str(refined_target).strip().lower()
            display_type = (source_target_type if source_target_type else original_target_type).strip() or "Other"
            display_type_l = display_type.lower().strip()

            mapping[(orig_crop_norm, orig_target_norm)] = TargetMapEntry(
                refined_target_l=refined_l,
                display_target_type_l=display_type_l,
                deployed=deployed_val,
                main_target_list=main_val,
            )

    return mapping


def build_label_index_row(source_file: str, pesticide: dict) -> dict:
    epa = str(pesticide.get("epa_reg_no") or "").strip()
    trade = str(pesticide.get("trade_Name") or "").strip()
    company = str(pesticide.get("company_name") or pesticide.get("COMPANY_NAME") or "").strip()
    product_type = str(pesticide.get("product_type") or "").strip()

    ingredient_objs = pesticide.get("Active_Ingredients", []) or []
    if not isinstance(ingredient_objs, list):
        ingredient_objs = []

    active_names: List[str] = []
    active_json: List[dict] = []
    moa_codes: List[str] = []
    moa_seen: set[str] = set()

    for ing in ingredient_objs:
        if not isinstance(ing, dict):
            continue
        name = str(ing.get("name") or ing.get("active_ingredient") or "").strip()
        moa_raw = str(ing.get("mode_Of_Action") or ing.get("mode_of_action") or "").strip()
        if name:
            active_names.append(name)
        if name or moa_raw:
            active_json.append({k: v for k, v in {"name": name, "mode_Of_Action": moa_raw}.items() if v})

        for tok in split_moa_tokens(moa_raw):
            if tok and tok not in moa_seen:
                moa_seen.add(tok)
                moa_codes.append(tok)

    parts = [
        epa,
        trade,
        company,
        product_type,
        " ".join(active_names),
        " ".join(moa_codes),
        source_file,
    ]
    search_text = " ".join([p for p in parts if p]).lower()

    return {
        "source_file": source_file,
        "epa_reg_no": epa or None,
        "trade_name": trade or None,
        "company_name": company or None,
        "product_type": product_type or None,
        "active_ingredients": active_names,
        "active_ingredients_json": active_json,
        "moa_codes": moa_codes,
        "search_text": search_text or None,
        "updated_at": "now()",
    }


def build_crop_target_rows(
    source_file: str,
    pesticide: dict,
    crop_maps: CropMaps,
    target_mapping: dict[tuple[str, str], TargetMapEntry],
) -> List[dict]:
    rows: List[dict] = []

    apps = pesticide.get("Application_Info", []) or []
    if not isinstance(apps, list):
        return rows

    for app in apps:
        if not isinstance(app, dict):
            continue
        crops = app.get("Target_Crop", []) or []
        targets = app.get("Target_Disease_Pest", []) or []
        if not isinstance(crops, list) or not isinstance(targets, list):
            continue

        # Collect crop norms for this app entry (orig + unified)
        crop_pairs: List[Tuple[str, str]] = []
        for c in crops:
            if not isinstance(c, dict):
                continue
            raw_crop = str(c.get("name") or "").strip()
            if not raw_crop:
                continue
            orig_crop_norm = normalize_crop_key(raw_crop)
            if not orig_crop_norm:
                continue
            if crop_maps.deployed_by_original_norm.get(orig_crop_norm, True) is False:
                continue
            unified_norm = crop_maps.unified_by_original_norm.get(orig_crop_norm, orig_crop_norm)
            unified_norm = normalize_crop_key(unified_norm) or orig_crop_norm
            crop_pairs.append((orig_crop_norm, unified_norm))

        if not crop_pairs:
            continue

        for t in targets:
            if not isinstance(t, dict):
                continue
            raw_target = str(t.get("name") or "").strip()
            if not raw_target:
                continue
            orig_target_norm = normalize_crop_key(raw_target)
            if not orig_target_norm:
                continue

            # Try mapping for any crop variant from this entry; first hit wins
            hit: Optional[TargetMapEntry] = None
            crop_unified: Optional[str] = None
            for orig_crop_norm, unified_norm in crop_pairs:
                info = target_mapping.get((orig_crop_norm, orig_target_norm))
                if info:
                    hit = info
                    crop_unified = unified_norm
                    break
            if not hit:
                continue
            if not hit.deployed:
                continue
            if not crop_unified:
                continue

            rows.append(
                {
                    "source_file": source_file,
                    "crop_norm": crop_unified,
                    "target_type_norm": hit.display_target_type_l or "other",
                    "target_norm": hit.refined_target_l,
                    "main_target_list": bool(hit.main_target_list),
                    "updated_at": "now()",
                }
            )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Supabase label indexes from altered_json.")
    parser.add_argument("--json-dir", default="", help="Override JSON directory (defaults to NYS_OUTPUT_JSON_DIR or app default)")
    parser.add_argument("--batch-size", type=int, default=500, help="Upsert batch size")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report counts but do not write to Supabase")
    args = parser.parse_args()

    json_dir = Path(args.json_dir).expanduser().resolve() if args.json_dir else get_json_dir()
    if not json_dir.exists() or not json_dir.is_dir():
        raise SystemExit(f"JSON directory not found: {json_dir}")

    nyspad_root = Path(__file__).resolve().parents[2]
    crop_maps = load_crop_maps(nyspad_root)
    target_mapping = load_target_mapping(nyspad_root)

    json_files = sorted(json_dir.glob("*.json"))
    print(f"[build] JSON dir: {json_dir} ({len(json_files)} files)")
    print(f"[build] Crop maps: {len(crop_maps.unified_by_original_norm)} entries")
    print(f"[build] Target mapping: {len(target_mapping)} entries")

    label_rows: List[dict] = []
    crosstab_rows: List[dict] = []

    skipped = 0
    for p in json_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue
        pesticide = data.get("pesticide") if isinstance(data, dict) else None
        if not isinstance(pesticide, dict):
            skipped += 1
            continue

        source_file = p.name
        label_rows.append(build_label_index_row(source_file, pesticide))
        crosstab_rows.extend(build_crop_target_rows(source_file, pesticide, crop_maps, target_mapping))

    print(f"[build] Parsed label_index rows: {len(label_rows)} (skipped {skipped})")
    print(f"[build] Parsed label_crop_target rows: {len(crosstab_rows)}")

    if args.dry_run:
        print("[build] Dry run; not writing to Supabase.")
        return

    if create_client is None:
        raise SystemExit("supabase client not installed. Install `supabase` in your venv.")

    url = _require_env("SUPABASE_URL")
    service_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    client = create_client(url, service_key)

    # Upsert label_index
    for batch in _chunks(label_rows, args.batch_size):
        client.table("label_index").upsert(batch, on_conflict="source_file").execute()

    # Upsert label_crop_target (composite key)
    for batch in _chunks(crosstab_rows, args.batch_size):
        client.table("label_crop_target").upsert(
            batch,
            on_conflict="source_file,crop_norm,target_type_norm,target_norm",
        ).execute()

    print("[build] Done.")


if __name__ == "__main__":
    main()



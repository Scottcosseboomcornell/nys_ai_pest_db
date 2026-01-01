#!/usr/bin/env python3
"""
NYSPAD altered JSON builder

Reads base JSONs from `output_json/`, enriches them with:
- DEC Active Ingredients (latest Dec_ProductData_ActiveIngredients-*.csv)
- Product metadata from `current_products_edited_txt_OCR_ag_rei_gpt_query.csv`
  (PRODUCT TYPE, LONG ISLAND USE RESTRICTION, Formulation, TOXICITY, PRODUCT USE, PRODUCT ID)
- Mode of Action lookup from `mode_of_action.xlsx` (optional)

Writes enriched JSONs to `altered_json/` with the same filenames.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

try:
    from rapidfuzz import fuzz, process  # type: ignore
except Exception:  # pragma: no cover
    fuzz = None  # type: ignore
    process = None  # type: ignore


def _norm_alnum(s: str) -> str:
    return "".join(ch.lower() for ch in str(s).strip() if ch.isalnum())


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    return s


def _clean_id_str(val: Any) -> str:
    """
    Normalize IDs that frequently arrive as floats in CSVs (e.g. "186580.0").
    """
    s = _safe_str(val)
    if s.endswith(".0"):
        return s[:-2]
    return s


def _singularize_token(token: str) -> str:
    """Very conservative singularization for a single token."""
    t = token
    if len(t) < 4:
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    # Avoid turning "glass" -> "glas"
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _normalize_target_name_conservative(raw: str) -> str:
    """
    Conservative normalization for target synonym dedupe:
    - lowercase
    - strip
    - remove spaces and hyphens
    - lightly singularize last token (e.g., aphids -> aphid)
    - keep alphanumerics only
    """
    s = _safe_str(raw).lower().strip()
    if not s:
        return ""

    # Normalize unicode-ish punctuation to spaces, then collapse.
    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212\-]+", " ", s)  # hyphen variants -> space
    s = re.sub(r"\s+", " ", s).strip()

    # Singularize last token only (conservative).
    parts = s.split(" ")
    if parts:
        parts[-1] = _singularize_token(parts[-1])
    s = " ".join(parts)

    # Remove separators and non-alnum
    s = s.replace(" ", "").replace("-", "")
    s = "".join(ch for ch in s if ch.isalnum())
    return s


def _fuzzy_canonicalize_in_crop(
    crop_key: str,
    raw_target: str,
    *,
    crop_bucket_index: dict[str, dict[str, list[str]]],
    canonical_to_rep: dict[tuple[str, str], str],
    threshold: int = 97,
    bucket_len: int = 8,
) -> str:
    """
    Return a canonical target key for a crop using conservative normalization and
    optional bucketed fuzzy matching (only within same prefix bucket).
    """
    norm = _normalize_target_name_conservative(raw_target)
    if not norm:
        return ""

    # Fast path: exact normalized match already known
    if (crop_key, norm) in canonical_to_rep:
        return norm

    # Bucket by prefix to keep fuzzy matching small
    bucket = norm[:bucket_len]
    crop_buckets = crop_bucket_index.setdefault(crop_key, {})
    candidates = crop_buckets.get(bucket, [])

    best = None
    if process is not None and candidates:
        # compare normalized keys only; very strict threshold
        best = process.extractOne(norm, candidates, scorer=fuzz.ratio) if fuzz is not None else None

    if best and best[1] >= threshold:
        chosen = str(best[0])
        canonical_to_rep[(crop_key, chosen)] = canonical_to_rep.get((crop_key, chosen), _safe_str(raw_target).strip())
        return chosen

    # No fuzzy match; register new canonical
    crop_buckets.setdefault(bucket, []).append(norm)
    canonical_to_rep[(crop_key, norm)] = canonical_to_rep.get((crop_key, norm), _safe_str(raw_target).strip())
    return norm


def _info_txt_path_from_pdf_filename(pdf_filename: str) -> Optional[str]:
    """
    Convert a PDF filename like:
      BANNER_MAXX_II_100-1326_PRIMARY_LABEL_543062.pdf
    into:
      BANNER_MAXX_II_100-1326_PRIMARY_LABEL_Info.txt
    """
    name = _safe_str(pdf_filename)
    if not name:
        return None
    # Replace trailing _<6digits>.pdf with _Info.txt
    new_name = re.sub(r"_[0-9]{6}\.pdf$", "_Info.txt", name, flags=re.IGNORECASE)
    if new_name == name:
        # fallback: any digits before .pdf
        new_name = re.sub(r"_[0-9]+\.pdf$", "_Info.txt", name, flags=re.IGNORECASE)
    if new_name == name:
        # fallback: just replace extension
        new_name = re.sub(r"\.pdf$", "_Info.txt", name, flags=re.IGNORECASE)
    return new_name


def _extract_company_name_from_info_txt(info_txt_path: Path) -> str:
    """
    Rules:
    - Find 'Manufacturer' line; take the next non-empty line as manufacturer name.
    - If that next line is 'Distributor' (meaning manufacturer name missing),
      then find 'Registrant' and take the next non-empty line as company_name.
    """
    try:
        lines = info_txt_path.read_text(errors="ignore").splitlines()
    except Exception:
        return ""

    def next_nonempty(start_idx: int) -> str:
        for j in range(start_idx, len(lines)):
            s = lines[j].strip()
            if s:
                return s
        return ""

    manufacturer_idx = None
    registrant_idx = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        # tolerate formats like "Manufacturer" or "Manufacturer:"
        if s.lower().rstrip(":") == "manufacturer":
            manufacturer_idx = i
        if s.lower().rstrip(":") == "registrant":
            registrant_idx = i

    manufacturer_val = ""
    if manufacturer_idx is not None:
        manufacturer_val = next_nonempty(manufacturer_idx + 1)

    if manufacturer_val and manufacturer_val.lower() != "distributor":
        return manufacturer_val

    # manufacturer missing → fallback to registrant
    if registrant_idx is not None:
        registrant_val = next_nonempty(registrant_idx + 1)
        if registrant_val:
            return registrant_val

    return ""


def _load_products_csv(products_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(products_csv, low_memory=False)
    if "Product No." not in df.columns:
        raise ValueError(f"Expected 'Product No.' column in {products_csv}")
    return df


def _merge_products_enrichment(
    base_df: pd.DataFrame,
    enrichment_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge enrichment fields (PRODUCT ID, LI restriction, etc.) from `current_products_edited.csv`
    into the downstream products CSV (e.g., *_gpt_query.csv) which often lacks those columns.
    """
    if "Product No." not in enrichment_df.columns or "Product No." not in base_df.columns:
        return base_df

    # Normalize join keys to avoid formatting issues like hyphens/spaces
    base = base_df.copy()
    enrich = enrichment_df.copy()

    base["_epa_key"] = base["Product No."].map(_norm_alnum)
    enrich["_epa_key"] = enrich["Product No."].map(_norm_alnum)

    cols_wanted = [
        "PRODUCT ID",
        "LONG ISLAND USE RESTRICTION",
        "Formulation",
        "TOXICITY",
        "PRODUCT USE",
        "PRODUCT TYPE",
    ]
    cols_present = [c for c in cols_wanted if c in enrich.columns]
    if not cols_present:
        return base_df

    enrich_small = enrich[["_epa_key", *cols_present]].drop_duplicates(subset=["_epa_key"], keep="last")

    merged = base.merge(enrich_small, how="left", on="_epa_key", suffixes=("", "_enrich"))
    merged = merged.drop(columns=["_epa_key"])

    # If base already has PRODUCT TYPE, prefer it; otherwise use enriched
    if "PRODUCT TYPE" in base_df.columns and "PRODUCT TYPE_enrich" in merged.columns:
        merged = merged.drop(columns=["PRODUCT TYPE_enrich"])
    elif "PRODUCT TYPE_enrich" in merged.columns:
        merged = merged.rename(columns={"PRODUCT TYPE_enrich": "PRODUCT TYPE"})

    return merged


def _build_products_lookup(products_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """
    Map normalized epa_reg_no -> row dict (last occurrence wins).
    """
    lookup: dict[str, dict[str, Any]] = {}
    for _, row in products_df.iterrows():
        epa = _safe_str(row.get("Product No.", ""))
        if not epa:
            continue
        lookup[_norm_alnum(epa)] = row.to_dict()
    return lookup


def _load_active_ingredients_csv(active_ingredients_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(active_ingredients_csv, low_memory=False)
    required = {"PRODUCT ID", "ACTIVE INGREDIENT ID", "PC CODE", "PC NAME", "ACTIVE INGREDIENT PERCENTAGE"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Active ingredients CSV missing columns {sorted(missing)}: {active_ingredients_csv}")
    return df


def _build_active_ingredients_lookup(active_df: pd.DataFrame) -> dict[str, list[dict[str, str]]]:
    """
    Map PRODUCT ID -> list of active ingredient dicts with renamed keys:
    - active_ingredient
    - pc_code
    - active_ingredient_percentage
    - nys_active_ingredient_id
    """
    out: dict[str, list[dict[str, str]]] = {}

    for _, row in active_df.iterrows():
        product_id = _clean_id_str(row.get("PRODUCT ID", ""))
        if not product_id:
            continue

        item = {
            "active_ingredient": _safe_str(row.get("PC NAME", "")),
            "pc_code": _clean_id_str(row.get("PC CODE", "")),
            "active_ingredient_percentage": _safe_str(row.get("ACTIVE INGREDIENT PERCENTAGE", "")),
            "nys_active_ingredient_id": _clean_id_str(row.get("ACTIVE INGREDIENT ID", "")),
        }

        out.setdefault(product_id, []).append(item)

    # de-dupe within each product_id (stable)
    for pid, items in out.items():
        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[dict[str, str]] = []
        for it in items:
            key = (it["active_ingredient"], it["pc_code"], it["active_ingredient_percentage"], it["nys_active_ingredient_id"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(it)
        out[pid] = deduped

    return out


def _load_mode_of_action_lookup(mode_of_action_xlsx: Path) -> dict[str, str]:
    """
    Returns mapping: normalized active ingredient name -> mode of action code/name.
    """
    df = pd.read_excel(mode_of_action_xlsx)
    # common column names used in the older pipeline
    ai_col = None
    moa_col = None
    for c in df.columns:
        if str(c).strip().lower() == "active ingredient":
            ai_col = c
        if str(c).strip().lower() == "mode of action":
            moa_col = c
    if ai_col is None or moa_col is None:
        raise ValueError(f"mode_of_action.xlsx must have 'Active ingredient' and 'Mode of Action' columns: {mode_of_action_xlsx}")

    lookup: dict[str, str] = {}
    for _, row in df.iterrows():
        name = _safe_str(row.get(ai_col, ""))
        moa = _safe_str(row.get(moa_col, ""))
        if not name:
            continue
        lookup[name.strip().lower()] = moa
    return lookup


def _lookup_mode_of_action(ai_name: str, moa_lookup: dict[str, str]) -> str:
    if not ai_name or not moa_lookup:
        return ""
    key = ai_name.strip().lower()
    if key in moa_lookup:
        return moa_lookup[key]

    # optional fuzzy fallback
    if process is None or fuzz is None:
        return ""
    best = process.extractOne(key, moa_lookup.keys(), scorer=fuzz.token_sort_ratio)  # type: ignore
    if best and best[1] >= 85:
        return moa_lookup.get(best[0], "")
    return ""


def _load_units_lookup(units_csv: Path) -> dict[str, str]:
    """
    Load units_unified.csv and return a mapping from original unit -> unified unit.
    Only includes entries where Unified column is not blank.
    """
    try:
        df = pd.read_csv(units_csv, low_memory=False)
    except Exception as e:
        raise ValueError(f"Could not read units_unified.csv: {e}")

    # Find the columns (first column is Unit, third column is Unified)
    unit_col = None
    unified_col = None
    
    for c in df.columns:
        col_lower = str(c).strip().lower()
        if col_lower == "unit":
            unit_col = c
        elif col_lower == "unified":
            unified_col = c
    
    if unit_col is None or unified_col is None:
        raise ValueError(f"units_unified.csv must have 'Unit' and 'Unified' columns: {units_csv}")

    lookup: dict[str, str] = {}
    for _, row in df.iterrows():
        original = _safe_str(row.get(unit_col, ""))
        unified = _safe_str(row.get(unified_col, ""))
        
        if original and unified:  # Only add if both are non-blank
            lookup[original] = unified
    
    return lookup


def _standardize_units(units_value: str, units_lookup: dict[str, str]) -> str:
    """
    Look up units_value in units_lookup. If found and unified value is non-blank,
    return the unified value. Otherwise return the original units_value.
    """
    if not units_value or not units_lookup:
        return units_value
    
    unified = units_lookup.get(units_value)
    if unified:
        return unified
    
    return units_value


def _extract_unique_crops_from_json(json_dir: Path) -> set[str]:
    """
    Extract unique crop names from all JSON files in the directory.
    Returns a set of crop names (title-cased).
    """
    crops: set[str] = set()
    
    json_files = sorted(json_dir.glob("*.json"))
    for jf in json_files:
        try:
            with open(jf, "r") as f:
                data = json.load(f)
            
            pesticide = data.get("pesticide") if isinstance(data.get("pesticide"), dict) else {}
            application_info = pesticide.get("Application_Info", [])
            
            if not isinstance(application_info, list):
                continue
            
            for app in application_info:
                if not isinstance(app, dict):
                    continue
                
                target_crops = app.get("Target_Crop", [])
                if not isinstance(target_crops, list):
                    continue
                
                for crop in target_crops:
                    if not isinstance(crop, dict):
                        continue
                    raw = str(crop.get("name") or "").strip()
                    if raw:
                        # Use title case for consistency
                        crops.add(raw.title())
        except Exception as e:
            # Skip files that can't be read
            continue
    
    return crops


def _get_product_type_mapping() -> dict[str, str]:
    """Return the exact mapping table from PRODUCT TYPE to TARGET TYPE."""
    return {
        'RODENTICIDE': 'Vertebrate',
        'GROWTH REGULATOR': 'Growth Regulation',
        'NEMATICIDE': 'Disease',
        'MITICIDE': 'Insects',
        'AVICIDE': 'Vertebrate',
        'DEFOLIANT': 'Weeds',
        'MILDEWSTATIC': 'Disease',
        'TERMITICIDE': 'Insects',
        'INSECTICIDE, TERMITICIDE': 'Insects',
        'INSECTICIDE, MITICIDE': 'Insects',
        'ANTIMICROBIAL, DISINFECTANT, SANITIZER': 'Disease',
        'INSECTICIDE, MOSQUITO ADULTICIDE': 'Insects',
        'FUNGICIDE, NEMATICIDE': 'Disease',
        'INSECTICIDE, MOSQUITO ADULTICIDE, TERMITICIDE': 'Insects',
        'ALGAECIDE, FUNGICIDE': 'Disease',
        'INSECTICIDE, MITICIDE, REPELLENT': 'Insects',
        'ANTIMICROBIAL, FUNGICIDE': 'Disease',
        'INSECTICIDE, REPELLENT': 'Insects',
        'INSECTICIDE, MITICIDE, NEMATICIDE, REPELLENT': 'Insects',
        'REPELLENT': 'Insects',
        'ALGAECIDE, ANTIMICROBIAL, FUNGICIDE, MILDEWSTATIC': 'Disease',
        'ANTIMICROBIAL, DISINFECTANT, FUNGICIDE': 'Disease',
        'ALGAECIDE, ANTIMICROBIAL, FUNGICIDE': 'Disease',
        'ANTIMICROBIAL, DISINFECTANT, FUNGICIDE, SANITIZER': 'Disease',
        'INSECTICIDE, SANITIZER': 'Insects',
        'DEFOLIANT, HERBICIDE': 'Weeds',
        'ALGAECIDE, FUNGICIDE, NEMATICIDE': 'Disease',
        'INSECTICIDE, PIP (PLANT INCORPORATED PROTECTANT)': 'Insects',
        'DISINFECTANT, MILDEWSTATIC': 'Disease',
        'DISINFECTANT, FUNGICIDE, INSECTICIDE, MILDEWSTATIC, SANITIZER': 'Disease',
        'INSECTICIDE, MITICIDE, TERMITICIDE': 'Insects',
        'INSECTICIDE, MOSQUITO LARVICIDE': 'Insects',
        'ALGAECIDE, ANTIMICROBIAL, FUNGICIDE, SANITIZER': 'Disease',
        'ANTIMICROBIAL, MILDEWSTATIC': 'Disease',
        'INSECTICIDE, TERMITICIDE, WOOD PRESERVATIVE': 'Insects',
        'ALGAECIDE, DISINFECTANT, FUNGICIDE, SANITIZER': 'Disease',
        'FUNGICIDE, WOOD PRESERVATIVE': 'Disease',
        'ALGAECIDE, DISINFECTANT, FUNGICIDE': 'Disease',
        'ALGAECIDE, ANTIMICROBIAL, DISINFECTANT, FUNGICIDE': 'Disease',
        'DISINFECTANT, FUNGICIDE': 'Disease',
        'ALGAECIDE, MILDEWSTATIC': 'Disease',
        'FUNGICIDE, PIP (PLANT INCORPORATED PROTECTANT)': 'Disease',
        'GROWTH REGULATOR, INSECTICIDE, MITICIDE, MOSQUITO LARVICIDE': 'Insects',
        'ALGAECIDE, ANTIMICROBIAL, DISINFECTANT, FUNGICIDE, SANITIZER': 'Disease',
        'INSECTICIDE': 'Insects',
        'HERBICIDE': 'Weeds',
        'FUNGICIDE': 'Disease',
    }




def _load_target_lookup_for_extraction(script_dir: Path) -> dict[str, str]:
    """Load target lookup CSV to determine target types during extraction."""
    lookup: dict[str, str] = {}
    
    # Try to find the target lookup CSV
    csv_paths = [
        script_dir / "web_application_old" / "target_analysis_with_suggestions.csv",
        script_dir / ".." / "web_application_old" / "target_analysis_with_suggestions.csv",
    ]
    
    csv_path = None
    for p in csv_paths:
        if p.exists():
            csv_path = p
            break
    
    if not csv_path:
        return lookup
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        target_col = None
        type_col = None
        
        for col in df.columns:
            col_lower = str(col).strip().lower()
            if "original" in col_lower and "target" in col_lower:
                target_col = col
            if "target_type" in col_lower or "targtype" in col_lower:
                type_col = col
        
        if target_col and type_col:
            for _, row in df.iterrows():
                target = str(row.get(target_col, "")).strip()
                target_type = str(row.get(type_col, "")).strip()
                if target and target_type:
                    lookup[target.lower()] = target_type
    except Exception:
        pass
    
    return lookup


def _extract_unique_targets_from_json(json_dir: Path) -> list[dict[str, str]]:
    """
    Extract unique target names with their associated crops and target types.
    Returns a list of dicts with keys: original_target_name, original_crop, original_target_type
    """
    # First pass: collect product type strings for each target
    target_to_product_type_strings: dict[str, set[str]] = {}
    
    json_files = sorted(json_dir.glob("*.json"))
    for jf in json_files:
        try:
            with open(jf, "r") as f:
                data = json.load(f)
            
            pesticide = data.get("pesticide") if isinstance(data.get("pesticide"), dict) else {}
            product_type_raw = pesticide.get("product_type", "").strip()
            
            # Normalize the product type string (uppercase, strip whitespace)
            if product_type_raw:
                # Normalize: split by comma, strip each part, sort, and rejoin for consistent matching
                parts = [pt.strip() for pt in product_type_raw.split(',') if pt.strip()]
                normalized_product_type = ', '.join(sorted([pt.upper() for pt in parts]))
            else:
                normalized_product_type = ""
            
            if not normalized_product_type:
                continue
            
            application_info = pesticide.get("Application_Info", [])
            
            if not isinstance(application_info, list):
                continue
            
            for app in application_info:
                if not isinstance(app, dict):
                    continue
                
                target_disease_pest = app.get("Target_Disease_Pest", [])
                if not isinstance(target_disease_pest, list):
                    continue
                
                # Collect product type strings for each target
                for target in target_disease_pest:
                    if not isinstance(target, dict):
                        continue
                    target_name = str(target.get("name") or "").strip()
                    if not target_name:
                        continue
                    
                    target_key = target_name.lower()
                    if target_key not in target_to_product_type_strings:
                        target_to_product_type_strings[target_key] = set()
                    
                    # Add the normalized product type string for this target
                    target_to_product_type_strings[target_key].add(normalized_product_type)
        except Exception as e:
            # Skip files that can't be read
            continue
    
    # Second pass: extract targets with determined target types
    # Deduplicate to one row per (crop, canonical_target) with conservative synonym handling.
    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()  # (canonical_target, crop) tuples
    crop_bucket_index: dict[str, dict[str, list[str]]] = {}
    canonical_to_rep: dict[tuple[str, str], str] = {}  # (crop_key, canonical) -> representative original target string
    
    for jf in json_files:
        try:
            with open(jf, "r") as f:
                data = json.load(f)
            
            pesticide = data.get("pesticide") if isinstance(data.get("pesticide"), dict) else {}
            application_info = pesticide.get("Application_Info", [])
            
            if not isinstance(application_info, list):
                continue
            
            for app in application_info:
                if not isinstance(app, dict):
                    continue
                
                target_crops = app.get("Target_Crop", [])
                if not isinstance(target_crops, list):
                    continue
                
                target_disease_pest = app.get("Target_Disease_Pest", [])
                if not isinstance(target_disease_pest, list):
                    continue
                
                # Get all crop names for this application
                crop_names = []
                for crop in target_crops:
                    if isinstance(crop, dict):
                        crop_name = str(crop.get("name") or "").strip()
                        if crop_name:
                            crop_names.append(crop_name.title())
                
                # Get all targets for this application
                for target in target_disease_pest:
                    if not isinstance(target, dict):
                        continue
                    target_name = str(target.get("name") or "").strip()
                    if not target_name:
                        continue
                    
                    # Determine target type: use exact lookup table, return "Other" if not found
                    target_key = target_name.lower()
                    product_type_strings = target_to_product_type_strings.get(target_key, set())
                    
                    # Try to find a match in the lookup table
                    target_type = "Other"
                    mapping = _get_product_type_mapping()
                    for product_type_str in product_type_strings:
                        if product_type_str in mapping:
                            target_type = mapping[product_type_str]
                            break
                    
                    # If not in the table, target_type remains "Other"
                    
                    # For each crop-target combination, add an entry (deduped by crop+canonical target)
                    for crop_name in crop_names:
                        crop_key = crop_name.lower().strip()
                        canonical = _fuzzy_canonicalize_in_crop(
                            crop_key,
                            target_name,
                            crop_bucket_index=crop_bucket_index,
                            canonical_to_rep=canonical_to_rep,
                        )
                        if not canonical:
                            continue

                        key = (canonical, crop_key)
                        if key in seen:
                            continue

                        seen.add(key)
                        rep = canonical_to_rep.get((crop_key, canonical), target_name)
                        targets.append({
                            "original_target_name": rep,
                            "original_crop": crop_name,
                            "original_target_type": target_type
                        })
        except Exception as e:
            # Skip files that can't be read
            continue
    
    return targets


def _load_unified_crop_mapping(script_dir: Path) -> dict[str, str]:
    """
    Load crop_names_unified.csv and return a mapping from normalized_original_crop_name -> unified_crop_name.
    Unified crop name is edited_crop_name if not blank, otherwise original_crop_name.
    Uses lowercase keys for case-insensitive matching.
    """
    crop_names_csv = script_dir / "crop_names_unified.csv"
    mapping: dict[str, str] = {}
    
    if not crop_names_csv.exists():
        return mapping
    
    try:
        df = pd.read_csv(crop_names_csv, low_memory=False)
        if "original_crop_name" not in df.columns:
            return mapping
        
        for _, row in df.iterrows():
            original = _safe_str(row.get("original_crop_name", ""))
            edited = _safe_str(row.get("edited_crop_name", ""))
            
            if not original:
                continue
            
            # Unified name: use edited if provided and not empty, otherwise use original
            unified = edited if edited else original
            
            # Store mapping using normalized (lowercase) key for case-insensitive lookup
            original_normalized = original.lower().strip()
            mapping[original_normalized] = unified
            
            # Also store exact case match for exact lookups
            mapping[original] = unified
    except Exception as e:
        print(f"Warning: Could not load crop_names_unified.csv: {e}")
    
    return mapping


def _update_target_names_csv(csv_path: Path, new_targets: list[dict[str, str]], script_dir: Path) -> None:
    """
    Update target_names_unified.csv with new unique target names.
    Rewrites into one row per (unified_crop, canonical_target) and only adds new crop-targets.
    Uses unified crop names from crop_names_unified.csv for consolidation.
    """
    # Load unified crop name mapping
    unified_crop_mapping = _load_unified_crop_mapping(script_dir)
    
    # Dedupe key is (unified_crop, canonical_target) — NOT including target type.
    existing_keys: set[tuple[str, str]] = set()  # (canonical_target, unified_crop) tuples
    # Store one merged row per key.
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    crop_bucket_index: dict[str, dict[str, list[str]]] = {}
    canonical_to_rep: dict[tuple[str, str], str] = {}
    
    def get_unified_crop(crop: str) -> str:
        """Get unified crop name, falling back to original if not in mapping."""
        if not crop:
            return crop
        # Try exact match first
        if crop in unified_crop_mapping:
            return unified_crop_mapping[crop]
        # Try case-insensitive match (normalized key)
        crop_normalized = crop.lower().strip()
        if crop_normalized in unified_crop_mapping:
            return unified_crop_mapping[crop_normalized]
        # Fallback to original
        return crop
    
    # Load existing CSV if it exists
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, low_memory=False)
            required_cols = ["original_target_name", "original_crop", "original_target_type"]
            if all(col in df.columns for col in required_cols):
                for _, row in df.iterrows():
                    target = _safe_str(row.get("original_target_name", ""))
                    crop = _safe_str(row.get("original_crop", ""))
                    target_type = _safe_str(row.get("original_target_type", ""))
                    
                    if target and crop:
                        # Map to unified crop name
                        unified_crop = get_unified_crop(crop)
                        crop_key = unified_crop.lower().strip()
                        canonical = _fuzzy_canonicalize_in_crop(
                            crop_key,
                            target,
                            crop_bucket_index=crop_bucket_index,
                            canonical_to_rep=canonical_to_rep,
                        )
                        if not canonical:
                            continue
                        key = (canonical, crop_key)
                        existing_keys.add(key)
                        
                        new_target = _safe_str(row.get("new_target_name", ""))
                        new_target_type = _safe_str(row.get("new_target_type", ""))
                        new_target_species = _safe_str(row.get("new_target_species", ""))
                        source_target_type = _safe_str(row.get("source_target_type", ""))  # Preserve if exists, empty if not
                        source_refined = _safe_str(row.get("source_refined", ""))  # Preserve if exists, empty if not
                        
                        # Handle deployed (default True)
                        deployed = True
                        if "deployed" in df.columns:
                            deployed_raw = row.get("deployed", True)
                            if pd.notna(deployed_raw):
                                if isinstance(deployed_raw, bool):
                                    deployed = deployed_raw
                                elif isinstance(deployed_raw, str):
                                    deployed = deployed_raw.lower() in ("true", "1", "yes", "y")
                                elif isinstance(deployed_raw, (int, float)):
                                    deployed = bool(deployed_raw)
                        
                        # Handle main_target_list (default False)
                        main_target_list = False
                        if "main_target_list" in df.columns:
                            main_raw = row.get("main_target_list", False)
                            if pd.notna(main_raw):
                                if isinstance(main_raw, bool):
                                    main_target_list = main_raw
                                elif isinstance(main_raw, str):
                                    main_target_list = main_raw.lower() in ("true", "1", "yes", "y")
                                elif isinstance(main_raw, (int, float)):
                                    main_target_list = bool(main_raw)

                        # Merge duplicates: prefer non-empty new_target/new_type, OR-merge booleans.
                        rep = canonical_to_rep.get((crop_key, canonical), target)
                        incoming = {
                            "original_target_name": rep,
                            "original_crop": unified_crop,  # Use unified crop name
                            "original_target_type": target_type or "Other",
                            "source_target_type": source_target_type,  # Preserve existing LLM classification marker
                            "new_target_name": new_target,
                            "new_target_type": new_target_type,
                            "new_target_species": new_target_species,
                            "source_refined": source_refined,  # Preserve existing LLM refinement marker
                            "deployed": deployed,
                            "main_target_list": main_target_list,
                        }

                        prev = rows_by_key.get(key)
                        if not prev:
                            rows_by_key[key] = incoming
                        else:
                            # Keep representative name if existing is blank
                            if not _safe_str(prev.get("original_target_name", "")):
                                prev["original_target_name"] = incoming["original_target_name"]
                            # Prefer non-empty original_target_type if existing is blank/Other
                            prev_type = _safe_str(prev.get("original_target_type", "")) or "Other"
                            inc_type = _safe_str(incoming.get("original_target_type", "")) or "Other"
                            if prev_type == "Other" and inc_type != "Other":
                                prev["original_target_type"] = inc_type
                            # Prefer non-empty new target fields
                            if not _safe_str(prev.get("new_target_name", "")) and _safe_str(incoming.get("new_target_name", "")):
                                prev["new_target_name"] = incoming["new_target_name"]
                            if not _safe_str(prev.get("new_target_type", "")) and _safe_str(incoming.get("new_target_type", "")):
                                prev["new_target_type"] = incoming["new_target_type"]
                            if not _safe_str(prev.get("new_target_species", "")) and _safe_str(incoming.get("new_target_species", "")):
                                prev["new_target_species"] = incoming["new_target_species"]
                            # Preserve source_target_type if it exists (marks LLM classification)
                            if not _safe_str(prev.get("source_target_type", "")) and _safe_str(incoming.get("source_target_type", "")):
                                prev["source_target_type"] = incoming["source_target_type"]
                            # Preserve source_refined if it exists (marks LLM refinement)
                            if not _safe_str(prev.get("source_refined", "")) and _safe_str(incoming.get("source_refined", "")):
                                prev["source_refined"] = incoming["source_refined"]
                            # OR merge flags
                            prev["deployed"] = bool(prev.get("deployed", True)) or bool(incoming.get("deployed", True))
                            prev["main_target_list"] = bool(prev.get("main_target_list", False)) or bool(incoming.get("main_target_list", False))
        except Exception as e:
            print(f"Warning: Could not read existing {csv_path}: {e}")
    
    # Add new targets that aren't already in the file
    added_count = 0
    for target_dict in new_targets:
        target = target_dict.get("original_target_name", "").strip()
        crop = target_dict.get("original_crop", "").strip()
        target_type = target_dict.get("original_target_type", "Other").strip()
        
        if not target or not crop:
            continue

        # Map to unified crop name
        unified_crop = get_unified_crop(crop)
        crop_key = unified_crop.lower().strip()
        canonical = _fuzzy_canonicalize_in_crop(
            crop_key,
            target,
            crop_bucket_index=crop_bucket_index,
            canonical_to_rep=canonical_to_rep,
        )
        if not canonical:
            continue

        key = (canonical, crop_key)
        if key not in existing_keys:
            rows_by_key[key] = {
                "original_target_name": canonical_to_rep.get((crop_key, canonical), target),
                "original_crop": unified_crop,  # Use unified crop name
                "original_target_type": target_type or "Other",
                "source_target_type": "",  # Empty - will be filled by LLM classification
                "new_target_name": "",
                "new_target_type": "",
                "new_target_species": "",
                "source_refined": "",  # Empty - will be filled by LLM refinement
                "deployed": True,  # New targets are deployed by default
                "main_target_list": False,  # New targets are not in main list by default
            }
            existing_keys.add(key)
            added_count += 1
    
    # Write updated CSV
    if rows_by_key:
        df_out = pd.DataFrame(list(rows_by_key.values()))
        # Sort by crop, then target_type, then target_name
        df_out = df_out.sort_values(["original_crop", "original_target_type", "original_target_name"])
        # Ensure source_target_type and source_refined columns exist (empty if not present)
        if "source_target_type" not in df_out.columns:
            df_out["source_target_type"] = ""
        if "source_refined" not in df_out.columns:
            df_out["source_refined"] = ""
        
        # Ensure columns are in the right order
        df_out = df_out[["original_target_name", "original_crop", "original_target_type", "source_target_type",
                         "new_target_name", "new_target_type", "new_target_species", "source_refined", "deployed", "main_target_list"]]
        df_out.to_csv(csv_path, index=False)
        if added_count > 0:
            print(f"Added {added_count} new target entries to {csv_path}")
        print(f"Rewrote {csv_path} with {len(df_out)} deduped target-crop rows")
    else:
        # Create empty CSV with headers if no data
        df_out = pd.DataFrame(columns=["original_target_name", "original_crop", "original_target_type", "source_target_type",
                                      "new_target_name", "new_target_type", "new_target_species", "source_refined", "deployed", "main_target_list"])
        df_out.to_csv(csv_path, index=False)
        print(f"Created empty {csv_path}")


def _update_crop_names_csv(csv_path: Path, new_crops: set[str]) -> None:
    """
    Update crop_names_unified.csv with new unique crop names.
    Preserves existing rows and only adds new crops.
    """
    existing_crops: set[str] = set()
    existing_data: list[dict[str, Any]] = []
    
    # Load existing CSV if it exists
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path, low_memory=False)
            if "original_crop_name" in df.columns:
                for _, row in df.iterrows():
                    original = _safe_str(row.get("original_crop_name", ""))
                    edited = _safe_str(row.get("edited_crop_name", ""))
                    # Preserve deployed status if it exists, default to True for new crops
                    deployed = True
                    if "deployed" in df.columns:
                        deployed_raw = row.get("deployed", True)
                        if pd.notna(deployed_raw):
                            if isinstance(deployed_raw, bool):
                                deployed = deployed_raw
                            elif isinstance(deployed_raw, str):
                                deployed = deployed_raw.lower() in ("true", "1", "yes", "y")
                            elif isinstance(deployed_raw, (int, float)):
                                deployed = bool(deployed_raw)
                    if original:
                        existing_crops.add(original)
                        existing_data.append({
                            "original_crop_name": original,
                            "edited_crop_name": edited,
                            "deployed": deployed
                        })
        except Exception as e:
            print(f"Warning: Could not read existing {csv_path}: {e}")
    
    # Add new crops that aren't already in the file
    added_count = 0
    for crop in sorted(new_crops):
        if crop not in existing_crops:
            existing_data.append({
                "original_crop_name": crop,
                "edited_crop_name": "",
                "deployed": True  # New crops are deployed by default
            })
            added_count += 1
    
    # Write updated CSV
    if existing_data:
        df_out = pd.DataFrame(existing_data)
        df_out = df_out.sort_values("original_crop_name")
        # Ensure columns are in the right order
        df_out = df_out[["original_crop_name", "edited_crop_name", "deployed"]]
        df_out.to_csv(csv_path, index=False)
        if added_count > 0:
            print(f"Added {added_count} new crop names to {csv_path}")
    else:
        # Create empty CSV with headers if no data
        df_out = pd.DataFrame(columns=["original_crop_name", "edited_crop_name", "deployed"])
        df_out.to_csv(csv_path, index=False)
        print(f"Created empty {csv_path}")


def _enrich_one_json(
    data: dict[str, Any],
    products_lookup: dict[str, dict[str, Any]],
    active_lookup: dict[str, list[dict[str, str]]],
    moa_lookup: dict[str, str],
    units_lookup: dict[str, str],
    pdf_dir: Path,
    info_cache: dict[str, str],
) -> dict[str, Any]:
    pesticide = data.get("pesticide") if isinstance(data.get("pesticide"), dict) else {}
    if not pesticide:
        return data

    epa_reg_no = _safe_str(pesticide.get("epa_reg_no", ""))
    key = _norm_alnum(epa_reg_no)
    prod_row = products_lookup.get(key, {})

    product_id = _clean_id_str(prod_row.get("PRODUCT ID", ""))
    pdf_filename = _safe_str(prod_row.get("pdf_filename", ""))

    # Remove previous wrapper if it exists; we now write these fields directly under pesticide
    if "nys_metadata" in pesticide:
        pesticide.pop("nys_metadata", None)

    # Add fields from products CSV (directly under pesticide)
    pesticide["product_id"] = product_id
    pesticide["product_type"] = _safe_str(prod_row.get("PRODUCT TYPE", ""))
    pesticide["long_island_use_restriction"] = _safe_str(prod_row.get("LONG ISLAND USE RESTRICTION", ""))
    pesticide["formulation"] = _safe_str(prod_row.get("Formulation", ""))
    pesticide["toxicity"] = _safe_str(prod_row.get("TOXICITY", ""))
    pesticide["product_use"] = _safe_str(prod_row.get("PRODUCT USE", ""))

    # Company name from PDFs/*_Info.txt based on pdf_filename
    company_name = ""
    info_name = _info_txt_path_from_pdf_filename(pdf_filename) if pdf_filename else None
    if info_name:
        if info_name in info_cache:
            company_name = info_cache[info_name]
        else:
            info_path = pdf_dir / info_name
            company_name = _extract_company_name_from_info_txt(info_path) if info_path.exists() else ""
            info_cache[info_name] = company_name
    pesticide["company_name"] = company_name

    # Replace base Active_Ingredients with NYS/DEC active ingredients (and overwrite mode of action)
    dec_ais = active_lookup.get(product_id, []) if product_id else []
    if dec_ais and moa_lookup:
        for it in dec_ais:
            it["mode_of_action"] = _lookup_mode_of_action(it.get("active_ingredient", ""), moa_lookup)

    pesticide["Active_Ingredients"] = [
        {
            # Backwards-compatible keys:
            "name": it.get("active_ingredient", ""),
            "mode_Of_Action": it.get("mode_of_action", "") or "",
            # NYS/DEC fields (requested in README):
            "pc_code": it.get("pc_code", ""),
            "active_ingredient_percentage": it.get("active_ingredient_percentage", ""),
            "nys_active_ingredient_id": it.get("nys_active_ingredient_id", ""),
        }
        for it in dec_ais
        if it.get("active_ingredient")
    ]

    # Standardize units in Application_Info
    if "Application_Info" in pesticide and isinstance(pesticide["Application_Info"], list):
        for app_info in pesticide["Application_Info"]:
            if isinstance(app_info, dict) and "units" in app_info:
                original_units = _safe_str(app_info.get("units", ""))
                if original_units:
                    standardized = _standardize_units(original_units, units_lookup)
                    app_info["units"] = standardized

    # Re-order keys so the NYS fields appear right after trade_Name (before Active_Ingredients)
    insert_fields = [
        "company_name",
        "product_id",
        "product_type",
        "long_island_use_restriction",
        "formulation",
        "toxicity",
        "product_use",
    ]

    anchor = "trade_Name" if "trade_Name" in pesticide else ("epa_reg_no" if "epa_reg_no" in pesticide else None)
    ordered: dict[str, Any] = {}
    inserted = False

    for k, v in pesticide.items():
        # skip fields we'll re-insert in the desired location
        if k in insert_fields:
            continue

        ordered[k] = v

        if (not inserted) and anchor and k == anchor:
            for f in insert_fields:
                if f in pesticide:
                    ordered[f] = pesticide[f]
            inserted = True

    # If the anchor wasn't found for some reason, append the fields at the end
    if not inserted:
        for f in insert_fields:
            if f in pesticide and f not in ordered:
                ordered[f] = pesticide[f]

    data["pesticide"] = ordered
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich NYSPAD output_json into altered_json")
    parser.add_argument("--input-dir", default="output_json", help="Directory containing base JSON files")
    parser.add_argument("--output-dir", default="altered_json", help="Directory to write enriched JSON files")
    parser.add_argument(
        "--downloads-dir",
        default="nyspad_csv_downloads",
        help="Directory containing downloaded/derived NYSPAD CSVs (default: nyspad_csv_downloads)",
    )
    parser.add_argument(
        "--products-csv",
        default=None,
        help="Path to current_products_edited_txt_OCR_ag_rei_gpt_query.csv (default: auto-detect)",
    )
    parser.add_argument(
        "--active-ingredients-csv",
        default=None,
        help="Path to Dec_ProductData_ActiveIngredients-*.csv (default: newest in downloads-dir)",
    )
    parser.add_argument(
        "--mode-of-action-xlsx",
        default=None,
        help="Optional path to mode_of_action.xlsx (if omitted or missing, mode of action is skipped)",
    )
    parser.add_argument(
        "--units-csv",
        default=None,
        help="Path to units_unified.csv (default: auto-detect in script directory)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_dir = (script_dir / args.input_dir).resolve()
    output_dir = (script_dir / args.output_dir).resolve()
    downloads_dir = (script_dir / args.downloads_dir).resolve()
    pdf_dir = (script_dir / "PDFs").resolve()
    info_cache: dict[str, str] = {}

    output_dir.mkdir(parents=True, exist_ok=True)

    # products CSV auto-detect (this is often the downstream *_gpt_query.csv)
    if args.products_csv:
        products_csv = (script_dir / args.products_csv).resolve() if not os.path.isabs(args.products_csv) else Path(args.products_csv)
    else:
        candidates = [
            downloads_dir / "current_products_edited_txt_OCR_ag_rei_gpt_query.csv",
            script_dir / "current_products_edited_txt_OCR_ag_rei_gpt_query.csv",
            script_dir / "old" / "current_products_edited_txt_OCR_ag_rei_gpt_query.csv",
        ]
        products_csv = next((p for p in candidates if p.exists()), None)
        if products_csv is None:
            raise FileNotFoundError("Could not find current_products_edited_txt_OCR_ag_rei_gpt_query.csv (provide --products-csv)")

    # enrichment CSV auto-detect (this should contain PRODUCT ID + other DEC-derived columns)
    enrichment_candidates = [
        downloads_dir / "current_products_edited.csv",
        script_dir / "current_products_edited.csv",
        script_dir / "old" / "current_products_edited.csv",
    ]
    enrichment_csv = next((p for p in enrichment_candidates if p.exists()), None)

    # active ingredients CSV auto-detect (newest in downloads_dir, else newest in old/)
    if args.active_ingredients_csv:
        ai_csv = (script_dir / args.active_ingredients_csv).resolve() if not os.path.isabs(args.active_ingredients_csv) else Path(args.active_ingredients_csv)
    else:
        glob1 = sorted(downloads_dir.glob("Dec_ProductData_ActiveIngredients-*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        glob2 = sorted((script_dir / "old").glob("Dec_ProductData_ActiveIngredients-*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        ai_csv = (glob1[0] if glob1 else (glob2[0] if glob2 else None))
        if ai_csv is None:
            raise FileNotFoundError("Could not find Dec_ProductData_ActiveIngredients-*.csv (provide --active-ingredients-csv)")

    moa_lookup: dict[str, str] = {}
    if args.mode_of_action_xlsx:
        moa_path = (script_dir / args.mode_of_action_xlsx).resolve() if not os.path.isabs(args.mode_of_action_xlsx) else Path(args.mode_of_action_xlsx)
        if moa_path.exists():
            moa_lookup = _load_mode_of_action_lookup(moa_path)
            print(f"Loaded mode of action lookup: {len(moa_lookup)} entries from {moa_path}")
        else:
            print(f"Warning: mode_of_action.xlsx not found at {moa_path}; skipping mode of action enrichment.")
    else:
        # common default locations
        for p in [
            script_dir / "mode_of_action.xlsx",
            script_dir / "pipeline_critical_docs" / "mode_of_action.xlsx",
            script_dir / "pipeline_critical_docs" / "mode_of_action" / "mode_of_action.xlsx",
        ]:
            if p.exists():
                moa_lookup = _load_mode_of_action_lookup(p)
                print(f"Loaded mode of action lookup: {len(moa_lookup)} entries from {p}")
                break
        if not moa_lookup:
            print("Mode of action lookup not found; skipping mode of action enrichment.")

    # units CSV auto-detect
    units_lookup: dict[str, str] = {}
    if args.units_csv:
        units_csv_path = (script_dir / args.units_csv).resolve() if not os.path.isabs(args.units_csv) else Path(args.units_csv)
        if units_csv_path.exists():
            units_lookup = _load_units_lookup(units_csv_path)
            print(f"Loaded units lookup: {len(units_lookup)} entries from {units_csv_path}")
        else:
            print(f"Warning: units_unified.csv not found at {units_csv_path}; skipping units standardization.")
    else:
        # common default locations
        units_csv_path = script_dir / "units_unified.csv"
        if units_csv_path.exists():
            units_lookup = _load_units_lookup(units_csv_path)
            print(f"Loaded units lookup: {len(units_lookup)} entries from {units_csv_path}")
        else:
            print("Warning: units_unified.csv not found; skipping units standardization.")

    print(f"Using products CSV: {products_csv}")
    if enrichment_csv:
        print(f"Using enrichment CSV: {enrichment_csv}")
    else:
        print("Warning: could not find current_products_edited.csv for enrichment; PRODUCT ID / Formulation / LI / TOXICITY / PRODUCT USE may be blank.")
    print(f"Using active ingredients CSV: {ai_csv}")
    print(f"Reading JSONs from: {input_dir}")
    print(f"Writing altered JSONs to: {output_dir}")

    products_df = _load_products_csv(products_csv)
    if enrichment_csv:
        enrich_df = _load_products_csv(enrichment_csv)
        products_df = _merge_products_enrichment(products_df, enrich_df)
    products_lookup = _build_products_lookup(products_df)

    active_df = _load_active_ingredients_csv(ai_csv)
    active_lookup = _build_active_ingredients_lookup(active_df)

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {input_dir}")

    written = 0
    missing_product_row = 0
    missing_product_id = 0

    for jf in json_files:
        with open(jf, "r") as f:
            data = json.load(f)

        pesticide = data.get("pesticide") if isinstance(data.get("pesticide"), dict) else {}
        epa_reg_no = _safe_str(pesticide.get("epa_reg_no", "")) if pesticide else ""

        prod_row = products_lookup.get(_norm_alnum(epa_reg_no), {})
        if not prod_row:
            missing_product_row += 1
        if not _safe_str(prod_row.get("PRODUCT ID", "")):
            missing_product_id += 1

        enriched = _enrich_one_json(data, products_lookup, active_lookup, moa_lookup, units_lookup, pdf_dir, info_cache)

        out_path = output_dir / jf.name
        with open(out_path, "w") as f:
            json.dump(enriched, f, indent=4)
        written += 1

    print(f"\nDone. Wrote {written} files.")
    print(f"Missing product row matches (by epa_reg_no): {missing_product_row}")
    print(f"Missing PRODUCT ID (from products CSV): {missing_product_id}")
    
    # Extract unique crop names from enriched JSONs and update crop_names_unified.csv
    print("\nExtracting unique crop names from enriched JSON files...")
    unique_crops = _extract_unique_crops_from_json(output_dir)
    crop_names_csv = script_dir / "crop_names_unified.csv"
    _update_crop_names_csv(crop_names_csv, unique_crops)
    print(f"Found {len(unique_crops)} unique crop names")
    
    # Extract unique target names from enriched JSONs and update target_names_unified.csv
    print("\nExtracting unique target names from enriched JSON files...")
    unique_targets = _extract_unique_targets_from_json(output_dir)
    target_names_csv = script_dir / "target_names_unified.csv"
    _update_target_names_csv(target_names_csv, unique_targets, script_dir)
    print(f"Found {len(unique_targets)} unique target-crop combinations")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
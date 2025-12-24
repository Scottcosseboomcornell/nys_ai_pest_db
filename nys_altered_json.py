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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
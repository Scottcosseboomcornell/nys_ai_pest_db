#!/usr/bin/env python3
"""
LLM-powered target type classification + JSON annotation.

Workflow:
1) Read `target_names_unified.csv` (one row per crop+target).
2) For each crop, batch targets (100-300) and ask an LLM to classify each into:
   Disease, Insects, Weeds, Other, Growth Regulation
3) Write results back into `target_names_unified.csv` (overwriting `original_target_type`,
   while preserving the prior value in `source_target_type`).
4) Optionally annotate enriched JSONs in `altered_json/` and write to
   `altered_json_target_classificaiton/` adding `target_type` to each Target_Disease_Pest item.

Notes:
- This script is safe to run incrementally: it only re-queries rows whose
  `original_target_type` is blank or "Other" unless --all is passed.
- Network access and an API key are required to call the LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

ALLOWED_TYPES = {"Disease", "Insects", "Weeds", "Other", "Growth Regulation", "Vertebrate", "Mollusks"}


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def _normalize_crop_key(crop: str) -> str:
    return re.sub(r"\s+", " ", _safe_str(crop).lower()).strip()


def _normalize_target_key(target: str) -> str:
    # Keep aligned with nys_altered_json.py conservative normalization intent.
    s = _safe_str(target).lower().strip()
    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" ", "").replace("-", "")
    s = "".join(ch for ch in s if ch.isalnum())
    return s


def _chunk(lst: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


@dataclass
class LlmConfig:
    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1/responses"
    timeout_s: int = 120
    max_retries: int = 5
    batch_size: int = 200


def _build_prompt(crop: str, targets: List[str], hard_examples: Optional[List[str]] = None) -> str:
    examples_block = ""
    if hard_examples:
        examples_block = (
            "\n\nSome challenging/ambiguous examples (use as calibration; do not hallucinate):\n"
            + "\n".join(hard_examples[:40])
        )

    return (
        f"Classify each pesticide target for crop: {crop}.\n\n"
        "VALID TARGET TYPES (use EXACTLY these strings, case-sensitive):\n"
        "- Disease\n"
        "- Insects\n"
        "- Weeds\n"
        "- Growth Regulation\n"
        "- Vertebrate\n"
        "- Mollusks\n"
        "- Other\n\n"
        "Classification rules:\n"
        "- Disease: fungal/bacterial/viral/nematodal diseases, NEMATODES, pathogens, rot, blight, spot, scab, rust, mildew, etc.\n"
        "- Insects: insects, mites, larvae, borers, beetles, aphids, leafminers, termites etc.\n"
        "- Weeds: weeds, grasses, broadleaf weeds, sedges, etc. (including weed species names like 'Anoda', 'Pigweed', etc.)\n"
        "- Growth Regulation: growth regulators of the crop, ripening, thinning, dormancy, etc.\n"
        "- Vertebrates: mammals, deer, rodents, birds, reptiles, amphibians, etc.\n"
        "- Mollusks: mollusks, snails, slugs, etc.\n"
        "- Other: anything else, unclear, or if you are unsure\n\n"
        "CRITICAL: Output format MUST be TSV (Tab-Separated Values) with EXACT header: target\ttarget_type\n"
        "CRITICAL: target_type column MUST contain ONLY one of these exact strings: Disease, Insects, Weeds, Growth Regulation, Vertebrate, Mollusks, Other\n"
        "CRITICAL: Do NOT use descriptive text, synonyms, or variations. Use ONLY the exact strings listed above.\n"
        "CRITICAL: If a target is a weed species (e.g., 'Anoda', 'Pigweed', 'Lambsquarters'), classify it as 'Weeds', not a description.\n"
        "CRITICAL: Fields MUST be separated by TAB characters, not commas or spaces.\n\n"
        "Example output format:\n"
        "target\ttarget_type\n"
        "Apple Scab\tDisease\n"
        "Aphids\tInsects\n"
        "Anoda\tWeeds\n"
        "Anoda, spurred\tWeeds\n"
        "Armyworms including beet armyworm, fall armyworm, southern armyworm\tInsects\n"
        "Pigweed\tWeeds\n"
        "Thinning\tGrowth Regulation\n"
        "Unknown Target\tOther\n\n"
        f"{examples_block}\n\n"
        "Now classify these targets:\n"
        + "\n".join(targets)
    )


def _build_refine_prompt(
    crop: str,
    source_target_type: str,
    *,
    all_targets_in_group: List[str],
    targets_to_return: List[str],
    hard_examples: Optional[List[str]] = None,
) -> str:
    examples_block = ""
    if hard_examples:
        examples_block = (
            "\n\nSome challenging/ambiguous examples (use as calibration; do not hallucinate):\n"
            + "\n".join(hard_examples[:40])
        )

    return (
        f"You are refining pesticide target names from pesticide labels for UI consolidation.\n\n"
        f"CONTEXT: These are pesticide label targets for {source_target_type} affecting {crop}.\n"
        f"All targets listed below are {source_target_type} targets found on pesticide labels for {crop}.\n"
        f"This grouping helps you identify synonyms and consolidate them to a single canonical name.\n\n"
        "For each target, return:\n"
        "- refined_target_name: the most commonly and officially used common name (Title Case preferred)\n"
        "- refined_target_species: If the target is a biological disease/pest caused by organisms in ONE genus, provide 'Genus spp.' (e.g., 'Venturia spp.' for Apple Scab, 'Aphanomyces spp.' for Aphanomyces root rot)\n\n"
        "CRITICAL - Synonym consolidation:\n"
        "- These targets are grouped together because they are all {source_target_type} for {crop}.\n"
        "- If multiple targets are synonyms (e.g., 'Aphanomyces', 'Aphanomyces spp.', 'Aphanomyces Root Rot'), output the SAME refined_target_name and refined_target_species for ALL of them.\n"
        "- Use the most commonly and officially used common name as the refined_target_name.\n"
        "- Seeing all targets together helps you identify which ones refer to the same biological entity.\n\n"
        "Species examples:\n"
        "- 'Apple Scab' → refined_target_name: 'Apple Scab', refined_target_species: 'Venturia spp.'\n"
        "- 'Aphanomyces' or 'Aphanomyces Root Rot' → refined_target_name: 'Aphanomyces Root Rot', refined_target_species: 'Aphanomyces spp.'\n"
        "- 'Armillaria Root Rot' → refined_target_name: 'Armillaria Root Rot', refined_target_species: 'Armillaria spp.'\n"
        "- 'Aphids' (general) → refined_target_name: 'Aphids', refined_target_species: (blank - multiple genera)\n"
        "- 'Weeds' (general) → refined_target_name: 'Weeds', refined_target_species: (blank - not biological)\n\n"
        "Species rule:\n"
        "- Provide species ONLY for biological diseases/pests where the causal organism is clearly within ONE genus.\n"
        "- Format MUST be exactly 'Genus spp.' (capital G, lowercase rest, space, 'spp.', period).\n"
        "- If multiple genera OR not biological OR uncertain: leave refined_target_species blank.\n\n"
        "Output rules:\n"
        "- Output MUST be TSV (Tab-Separated Values) with EXACT header:\n"
        "  target\trefined_target_name\trefined_target_species\n"
        "- Fields MUST be separated by TAB characters (\\t). Do NOT output commas as separators.\n"
        "- Return rows ONLY for the targets listed under 'TARGETS TO RETURN'.\n"
        "- Do not add any commentary, only the TSV.\n"
        f"{examples_block}\n\n"
        "FULL CONTEXT (all {source_target_type} targets for {crop} - use this to identify synonyms):\n"
        + "\n".join(all_targets_in_group)
        + "\n\nTARGETS TO RETURN (subset; output ONLY these rows):\n"
        + "\n".join(targets_to_return)
    )


def _call_llm_responses_api(prompt: str, cfg: LlmConfig) -> str:
    """
    Calls OpenAI Responses API using stdlib only to avoid dependency churn.
    Requires network access at runtime.
    """
    import urllib.request

    payload = {
        "model": cfg.model,
        "input": prompt,
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg.base_url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
    )

    last_err: Optional[Exception] = None
    for attempt in range(cfg.max_retries):
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
                body = resp.read().decode("utf-8")
            j = json.loads(body)
            # Responses API returns content in output[].content[].text
            texts: List[str] = []
            for item in j.get("output", []) or []:
                for c in item.get("content", []) or []:
                    if c.get("type") == "output_text":
                        texts.append(c.get("text", ""))
            return "\n".join(texts).strip()
        except Exception as e:
            last_err = e
            sleep_s = min(2 ** attempt, 20)
            time.sleep(sleep_s)
    raise RuntimeError(f"LLM call failed after retries: {last_err}")


def _parse_csv_response(text: str) -> Dict[str, str]:
    """
    Parse TSV (Tab-Separated Values) "target\ttarget_type" into dict[target] -> type.
    Uses tabs instead of commas to avoid issues with commas in target names.
    Very strict validation.
    """
    text = text.strip()
    # Remove any code fences if they appear
    text = re.sub(r"^```.*?\n", "", text).strip()
    text = re.sub(r"\n```$", "", text).strip()

    # Use csv.DictReader with tab delimiter (TSV format)
    reader = csv.DictReader(text.splitlines(), delimiter='\t', skipinitialspace=True)
    if not reader.fieldnames or [f.strip().lower() for f in reader.fieldnames] != ["target", "target_type"]:
        raise ValueError(f"Unexpected TSV header: {reader.fieldnames}")

    out: Dict[str, str] = {}
    for row in reader:
        t = _safe_str(row.get("target"))
        ty = _safe_str(row.get("target_type"))
        if not t:
            continue
        if ty not in ALLOWED_TYPES:
            raise ValueError(f"Invalid target_type '{ty}' for target '{t}'")
        out[t] = ty
    return out


def _parse_refine_csv_response(text: str) -> Dict[str, dict[str, str]]:
    text = text.strip()
    text = re.sub(r"^```.*?\n", "", text).strip()
    text = re.sub(r"\n```$", "", text).strip()

    # Use csv.DictReader with tab delimiter (TSV format) to avoid comma issues
    reader = csv.DictReader(text.splitlines(), delimiter='\t', skipinitialspace=True)
    expected = ["target", "refined_target_name", "refined_target_species"]
    if not reader.fieldnames or [f.strip().lower() for f in reader.fieldnames] != expected:
        raise ValueError(f"Unexpected TSV header: {reader.fieldnames}")

    out: Dict[str, dict[str, str]] = {}
    for row in reader:
        t = _safe_str(row.get("target"))
        rn = _safe_str(row.get("refined_target_name"))
        rs = _safe_str(row.get("refined_target_species"))
        if not t:
            continue
        if rs and not re.match(r"^[A-Z][a-z]+\s+spp\.$", rs):
            # Force blank if model didn't follow format
            rs = ""
        out[t] = {"refined_target_name": rn, "refined_target_species": rs}
    return out


def classify_targets_csv(
    csv_path: Path,
    *,
    cfg: LlmConfig,
    hard_examples: Optional[List[str]] = None,
    classify_all: bool = False,
    sleep_between_calls_s: float = 0.2,
) -> None:
    df = pd.read_csv(csv_path, low_memory=False)
    required = {"original_target_name", "original_crop", "original_target_type"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"{csv_path} missing required columns: {sorted(required)}")

    # Ensure source_target_type column exists (empty if not present)
    if "source_target_type" not in df.columns:
        df["source_target_type"] = ""

    # Normalize blank/nan
    df["original_target_type"] = df["original_target_type"].apply(lambda x: _safe_str(x))
    df["source_target_type"] = df["source_target_type"].apply(lambda x: _safe_str(x))
    df["original_target_name"] = df["original_target_name"].apply(lambda x: _safe_str(x))
    df["original_crop"] = df["original_crop"].apply(lambda x: _safe_str(x))

    # Determine which rows need classification: only rows where source_target_type is empty
    def needs(row: pd.Series) -> bool:
        if classify_all:
            # Even with --all, only process rows that haven't been LLM-classified yet
            source = _safe_str(row.get("source_target_type", ""))
            return not source  # Empty means not yet LLM-classified
        # Default: only process rows where source_target_type is empty
        source = _safe_str(row.get("source_target_type", ""))
        return not source

    df["__needs"] = df.apply(needs, axis=1)
    
    needs_count = df["__needs"].sum()
    total_count = len(df)
    
    if needs_count == 0:
        print(f"⚠️  No rows need classification (all {total_count} rows already have source_target_type set).")
        print(f"   All rows have been LLM-classified. Use --all to force reclassification.")
        return
    
    print(f"📊 Processing {needs_count} of {total_count} rows that need LLM classification (source_target_type is empty)...")
    if classify_all:
        print(f"   (--all flag: will process all rows with empty source_target_type)")

    # Group by crop
    crops = sorted(df["original_crop"].dropna().unique().tolist(), key=lambda x: x.lower())
    mapping_updates: Dict[Tuple[str, str], str] = {}  # (crop_norm, target_norm) -> type
    
    total_batches = 0
    for crop in crops:
        crop_rows = df[(df["original_crop"] == crop) & (df["__needs"])]
        if crop_rows.empty:
            continue

        targets = sorted(set(crop_rows["original_target_name"].tolist()), key=lambda x: x.lower())
        batches = list(_chunk(targets, cfg.batch_size))
        total_batches += len(batches)
        
        print(f"  Processing {len(targets)} targets for {crop} ({len(batches)} batch{'es' if len(batches) != 1 else ''})...")
        
        for batch_idx, batch in enumerate(batches, 1):
            print(f"    Batch {batch_idx}/{len(batches)}: {len(batch)} targets...", end=" ", flush=True)
            prompt = _build_prompt(crop, batch, hard_examples=hard_examples)
            response_text = _call_llm_responses_api(prompt, cfg)
            parsed = _parse_csv_response(response_text)

            # Match parsed results to batch targets (handle normalization differences)
            missing = []
            for t in batch:
                # Try exact match first
                ty = parsed.get(t)
                if not ty:
                    # Try case-insensitive match
                    ty = next((parsed[k] for k in parsed.keys() if k.lower() == t.lower()), None)
                if not ty:
                    # Try normalized match (strip whitespace, normalize)
                    t_normalized = _normalize_target_key(t)
                    ty = next((parsed[k] for k in parsed.keys() if _normalize_target_key(k) == t_normalized), None)
                
                if ty:
                    mapping_updates[(_normalize_crop_key(crop), _normalize_target_key(t))] = ty
                else:
                    # Default to Other if not found
                    mapping_updates[(_normalize_crop_key(crop), _normalize_target_key(t))] = "Other"
                    missing.append(t)
            
            status_msg = f"✓ ({len(parsed)} classifications received"
            if missing:
                status_msg += f", {len(missing)} defaulted to Other"
            status_msg += ")"
            print(status_msg)
            
            if missing:
                print(f"      ⚠️  Missing classifications for: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")

            # Apply updates incrementally and save CSV after each batch
            def apply_row_incremental(row: pd.Series) -> pd.Series:
                crop_norm = _normalize_crop_key(row["original_crop"])
                targ_norm = _normalize_target_key(row["original_target_name"])
                key = (crop_norm, targ_norm)
                if key in mapping_updates:
                    row["source_target_type"] = mapping_updates[key]
                return row
            
            df = df.apply(apply_row_incremental, axis=1)
            df.to_csv(csv_path, index=False)

            time.sleep(sleep_between_calls_s)
    
    print(f"\n✅ Completed {total_batches} LLM batch call(s)")
    
    # Final cleanup: remove temporary column
    df = df.drop(columns=["__needs"])
    df.to_csv(csv_path, index=False)
    
    updated_count = len(mapping_updates)
    print(f"💾 Final save: Stored LLM classifications in source_target_type for {updated_count} rows")
    print(f"   original_target_type unchanged (product_type-based) for comparison")


def refine_targets_csv(
    csv_path: Path,
    *,
    cfg: LlmConfig,
    hard_examples: Optional[List[str]] = None,
    overwrite: bool = False,
    sleep_between_calls_s: float = 0.2,
) -> None:
    df = pd.read_csv(csv_path, low_memory=False)
    required = {"original_target_name", "original_crop", "original_target_type"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"{csv_path} missing required columns: {sorted(required)}")

    # Ensure columns exist
    if "new_target_name" not in df.columns:
        df["new_target_name"] = ""
    if "new_target_species" not in df.columns:
        df["new_target_species"] = ""
    if "source_refined" not in df.columns:
        df["source_refined"] = ""
    if "source_target_type" not in df.columns:
        df["source_target_type"] = ""

    # Normalize nan/blank
    for col in [
        "original_target_name",
        "original_crop",
        "original_target_type",
        "source_target_type",
        "new_target_name",
        "new_target_species",
        "source_refined",
    ]:
        df[col] = df[col].apply(lambda x: _safe_str(x))

    # Only refine rows where:
    # 1. source_refined is empty (not yet refined by LLM)
    # 2. source_target_type is Disease, Insects, Weeds, or Growth Regulation (LLM-classified)
    # 3. if overwrite is False: do not overwrite existing manual edits in new_* columns
    def needs_refine(row: pd.Series) -> bool:
        source_refined = _safe_str(row.get("source_refined", ""))
        source_target_type = _safe_str(row.get("source_target_type", ""))
        
        # Must have been LLM-classified first
        if not source_target_type or source_target_type == "Other":
            return False
        
        # Only refine Disease, Insects, Weeds, Growth Regulation
        if source_target_type not in ("Disease", "Insects", "Weeds", "Growth Regulation"):
            return False
        
        # Only process rows where source_refined is empty
        if source_refined:
            return False

        if not overwrite:
            # Don't overwrite existing manual edits
            if _safe_str(row.get("new_target_name", "")) or _safe_str(row.get("new_target_species", "")):
                return False
        
        return True

    df["__needs_refine"] = df.apply(needs_refine, axis=1)

    needs_count = int(df["__needs_refine"].sum())
    total_count = len(df)
    if needs_count == 0:
        print(f"⚠️  No rows need refinement (either already refined, Other, not LLM-classified, or has manual new_* edits).")
        return

    print(f"📊 Processing {needs_count} of {total_count} rows that need LLM refinement (grouped by crop + source_target_type)...")

    # Group by (crop, source_target_type) so the LLM can see all targets in that group for synonym consolidation
    updates: Dict[Tuple[str, str], dict[str, str]] = {}  # (crop_norm, target_norm) -> fields
    group_df = df[df["__needs_refine"]].copy()
    groups = (
        group_df.groupby(["original_crop", "source_target_type"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values(["original_crop", "source_target_type"])
        .values.tolist()
    )

    total_batches = 0
    for crop, stype, _n in groups:
        crop = _safe_str(crop)
        stype = _safe_str(stype)
        if not crop or not stype or stype == "Other":
            continue

        group_rows = df[(df["original_crop"] == crop) & (df["source_target_type"] == stype) & (df["__needs_refine"])]
        if group_rows.empty:
            continue

        all_targets = sorted(set(group_rows["original_target_name"].tolist()), key=lambda x: x.lower())
        batches = list(_chunk(all_targets, cfg.batch_size))
        total_batches += len(batches)

        print(f"  Refining {len(all_targets)} targets for {crop} / {stype} ({len(batches)} batch{'es' if len(batches) != 1 else ''})...")

        for batch_idx, batch in enumerate(batches, 1):
            print(f"    Batch {batch_idx}/{len(batches)}: {len(batch)} targets...", end=" ", flush=True)
            prompt = _build_refine_prompt(
                crop,
                stype,
                all_targets_in_group=all_targets,
                targets_to_return=batch,
                hard_examples=hard_examples,
            )
            response_text = _call_llm_responses_api(prompt, cfg)
            parsed = _parse_refine_csv_response(response_text)

            missing: list[str] = []
            for t in batch:
                item = parsed.get(t)
                if not item:
                    # try case-insensitive / normalized match
                    item = next((parsed[k] for k in parsed.keys() if k.lower() == t.lower()), None)
                if not item:
                    t_norm = _normalize_target_key(t)
                    item = next((parsed[k] for k in parsed.keys() if _normalize_target_key(k) == t_norm), None)
                if not item:
                    missing.append(t)
                    continue

                updates[(_normalize_crop_key(crop), _normalize_target_key(t))] = item

            msg = f"✓ ({len(parsed)} refinements received"
            if missing:
                msg += f", {len(missing)} missing"
            msg += ")"
            print(msg)
            if missing:
                print(f"      ⚠️  Missing refinements for: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")

            # Apply updates incrementally and save CSV after each batch so interruption is safe.
            def apply_refine_incremental(row: pd.Series) -> pd.Series:
                if not _safe_str(row.get("__needs_refine", "")):
                    return row
                crop_norm = _normalize_crop_key(row["original_crop"])
                targ_norm = _normalize_target_key(row["original_target_name"])
                key = (crop_norm, targ_norm)
                if key not in updates:
                    return row
                item2 = updates[key]

                # Only write into new_* if overwrite OR the field is empty
                if overwrite or (not _safe_str(row.get("new_target_name", ""))):
                    row["new_target_name"] = item2.get("refined_target_name", "")
                if overwrite or (not _safe_str(row.get("new_target_species", ""))):
                    row["new_target_species"] = item2.get("refined_target_species", "")

                # Mark refined if we wrote anything (or if overwrite mode)
                if overwrite or row["new_target_name"] or row["new_target_species"]:
                    row["source_refined"] = f"LLM:{cfg.model}"
                return row

            df = df.apply(apply_refine_incremental, axis=1)
            df.to_csv(csv_path, index=False)

            time.sleep(sleep_between_calls_s)

    print(f"\n✅ Completed {total_batches} LLM refine batch call(s)")

    def apply_refine(row: pd.Series) -> pd.Series:
        crop_norm = _normalize_crop_key(row["original_crop"])
        targ_norm = _normalize_target_key(row["original_target_name"])
        key = (crop_norm, targ_norm)
        if key not in updates:
            return row
        item = updates[key]
        # Store refined values in new_* columns (keep originals unchanged); respect overwrite flag
        if overwrite or (not _safe_str(row.get("new_target_name", ""))):
            row["new_target_name"] = item.get("refined_target_name", "")
        if overwrite or (not _safe_str(row.get("new_target_species", ""))):
            row["new_target_species"] = item.get("refined_target_species", "")
        if overwrite or row["new_target_name"] or row["new_target_species"]:
            row["source_refined"] = f"LLM:{cfg.model}"
        return row

    df = df.apply(apply_refine, axis=1)
    df = df.drop(columns=["__needs_refine"])
    df.to_csv(csv_path, index=False)
    
    updated_count = len(updates)
    print(f"💾 Final save: applied {updated_count} LLM refinements (keys) into new_* columns")
    print(f"   source_refined set to 'LLM:{cfg.model}' where refined")
    print(f"   original_target_name/type unchanged for comparison")


def annotate_jsons(
    csv_path: Path,
    *,
    input_dir: Path,
    output_dir: Path,
) -> None:
    df = pd.read_csv(csv_path, low_memory=False)
    required = {"original_target_name", "original_crop", "original_target_type"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"{csv_path} missing required columns: {sorted(required)}")

    # Build lookup (crop_norm, target_norm) -> payload
    lookup: Dict[Tuple[str, str], dict[str, str]] = {}
    for _, row in df.iterrows():
        crop = _safe_str(row.get("original_crop"))
        target = _safe_str(row.get("original_target_name"))
        # Prefer refined overrides if present
        ty = _safe_str(row.get("source_target_type")) or _safe_str(row.get("original_target_type")) or "Other"
        refined_name = _safe_str(row.get("new_target_name")) or ""
        refined_species = _safe_str(row.get("new_target_species")) or ""
        if not crop or not target:
            continue
        lookup[(_normalize_crop_key(crop), _normalize_target_key(target))] = {
            "target_type": ty,
            "refined_target_name": refined_name,
            "refined_target_species": refined_species,
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for jf in sorted(input_dir.glob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue

        pesticide = data.get("pesticide") if isinstance(data, dict) else None
        if not isinstance(pesticide, dict):
            continue

        apps = pesticide.get("Application_Info", [])
        if not isinstance(apps, list):
            out_path = output_dir / jf.name
            out_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
            written += 1
            continue

        for app in apps:
            if not isinstance(app, dict):
                continue
            crops = [str(c.get("name") or "").strip() for c in (app.get("Target_Crop", []) or []) if isinstance(c, dict)]
            crops_norm = [_normalize_crop_key(c) for c in crops if c]

            targets = app.get("Target_Disease_Pest", [])
            if not isinstance(targets, list):
                continue

            for t in targets:
                if not isinstance(t, dict):
                    continue
                name = str(t.get("name") or "").strip()
                if not name:
                    continue

                # If multiple crops in the application, only set a type if all crops agree.
                types = set()
                refined_names = set()
                refined_species = set()
                for cn in crops_norm:
                    payload = lookup.get((cn, _normalize_target_key(name)))
                    if payload:
                        types.add(payload.get("target_type", "Other"))
                        if payload.get("refined_target_name"):
                            refined_names.add(payload["refined_target_name"])
                        if payload.get("refined_target_species"):
                            refined_species.add(payload["refined_target_species"])
                t["target_type"] = types.pop() if len(types) == 1 else "Other"
                t["refined_target_name"] = refined_names.pop() if len(refined_names) == 1 else ""
                t["refined_target_species"] = refined_species.pop() if len(refined_species) == 1 else ""

        out_path = output_dir / jf.name
        out_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
        written += 1

    print(f"Wrote {written} annotated JSON files to {output_dir}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="target_names_unified.csv", help="Path to target_names_unified.csv")
    ap.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-5.2"), help="OpenAI model name")
    ap.add_argument("--batch-size", type=int, default=200, help="Targets per request (100-300 recommended)")
    ap.add_argument("--all", action="store_true", help="Process all rows with empty source_target_type (default: same behavior, this flag is for clarity)")
    ap.add_argument("--classify", action="store_true", help="Run LLM classification: only processes rows where source_target_type is empty")
    ap.add_argument("--refine", action="store_true", help="Run LLM refinement (new_target_name/species/type) and update CSV")
    ap.add_argument("--overwrite-refine", action="store_true", help="Allow refine step to overwrite existing new_* fields")
    ap.add_argument("--annotate-json", action="store_true", help="Annotate altered_json into altered_json_target_classificaiton")
    ap.add_argument("--json-in", default="altered_json", help="Input JSON dir")
    ap.add_argument("--json-out", default="altered_json_target_classificaiton", help="Output JSON dir")
    ap.add_argument("--hard-examples", default="", help="Optional path to text file with ambiguous examples (one per line)")
    args = ap.parse_args()

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    hard_examples: Optional[List[str]] = None
    if args.hard_examples:
        p = Path(args.hard_examples).resolve()
        if p.exists():
            hard_examples = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

    if args.classify:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            # Fall back to Scott's key from key.py if available
            try:
                from key import scott_key  # type: ignore
                api_key = str(scott_key).strip()
            except Exception:
                api_key = ""
        if not api_key:
            raise SystemExit("Missing OPENAI_API_KEY env var (and could not load scott_key from key.py)")
        cfg = LlmConfig(model=args.model, api_key=api_key, batch_size=args.batch_size)
        classify_targets_csv(csv_path, cfg=cfg, hard_examples=hard_examples, classify_all=args.all)

    if args.refine:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            try:
                from key import scott_key  # type: ignore
                api_key = str(scott_key).strip()
            except Exception:
                api_key = ""
        if not api_key:
            raise SystemExit("Missing OPENAI_API_KEY env var (and could not load scott_key from key.py)")
        cfg = LlmConfig(model=args.model, api_key=api_key, batch_size=args.batch_size)
        refine_targets_csv(csv_path, cfg=cfg, hard_examples=hard_examples, overwrite=args.overwrite_refine)

    if args.annotate_json:
        annotate_jsons(
            csv_path,
            input_dir=Path(args.json_in).resolve(),
            output_dir=Path(args.json_out).resolve(),
        )

    if not args.classify and not args.refine and not args.annotate_json:
        ap.print_help()
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



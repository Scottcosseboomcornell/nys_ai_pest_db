#!/usr/bin/env python3
"""
Precompute filter index for fast Table 2 rendering.

Generates a JSON file mapping (Crop, TargetType, Target) -> list of EPA reg numbers,
and top targets per (Crop, TargetType) with counts.

Output: precomputed_filter_index.json in the same directory as this script.
"""

import os
import json
import glob
import time
from collections import defaultdict
from datetime import datetime


def log(message: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {message}", flush=True)

from target_lookup import (
    get_simplified_targets_list,
    get_target_type,
    get_original_targets_for_simplified_target,
)
from pest_category_lookup import get_categories_for_pesticide


def detect_data_dir() -> str:
    """Detect altered_json directory similar to the Flask app's detection."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_json_path = os.path.join(current_dir, "altered_json")
    local_json_path = os.path.join(current_dir, "..", "pipeline_critical_docs", "altered_json")
    if os.path.exists(server_json_path) and not os.path.islink(server_json_path):
        return server_json_path
    return os.path.normpath(local_json_path)


ALLOWED_CROPS = [
    "Apple", "Blackberry", "Blueberry", "Grape", "Cherry", "Cranberry",
    "Peach", "Pear", "Pecan", "Strawberry", "Spinach", "Nectarine",
    "Orange", "Pepper", "Tomato", "Almond", "Apricot", "Potato",
    "Raspberry", "Walnut", "Cucumber", "Broccoli",
]

TARGET_TYPES = ["Disease", "Insect", "Weed"]


def load_pesticide_data(json_dir: str):
    """Minimal loader that mirrors the flattened structure used by the app."""
    records = []
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if "pesticide" not in raw:
                continue
            p = raw["pesticide"]

            # Flatten application info into strings (same as app)
            application_info = []
            for app in p.get("Application_Info", []):
                crops = [c.get("name", "") for c in app.get("Target_Crop", [])]
                pests = [d.get("name", "") for d in app.get("Target_Disease_Pest", [])]
                application_info.append({
                    "Target_Crop": ", ".join([c for c in crops if c]),
                    "Target_Disease_Pest": ", ".join([d for d in pests if d]),
                    "low_rate": app.get("low_rate", "N/A"),
                    "high_rate": app.get("high_rate", "N/A"),
                    "units": app.get("units", "N/A"),
                    "REI": app.get("REI", "N/A"),
                    "PHI": app.get("PHI", "N/A"),
                    "application_Method": app.get("application_Method", "N/A"),
                    "max_applications_per_season": app.get("max_applications_per_season", "N/A"),
                })

            records.append({
                "epa_reg_no": p.get("epa_reg_no", "N/A"),
                "trade_Name": p.get("trade_Name", "N/A"),
                "COMPANY_NAME": p.get("COMPANY_NAME", "N/A"),
                "Safety_Information": p.get("Safety_Information", {}),
                "application_info": application_info,
            })
        except Exception:
            continue
    return records


def crop_matches_allowed(crop: str) -> bool:
    cl = (crop or "").lower()
    for ac in ALLOWED_CROPS:
        al = ac.lower()
        if cl == al or cl == al + "s" or al == cl + "s":
            return True
    return False


def compute_top_targets_for_crop_and_type(data, crop: str, target_type: str, top_k: int = 10):
    """Return list of (simplified_target, unique_pesticide_count) sorted by count desc."""
    crop_variants = [crop.lower()]
    if "apple" in crop.lower():
        crop_variants.extend(["apples", "apple tree", "apple trees"])
    elif "grape" in crop.lower():
        crop_variants.extend(["grapes", "grapevine", "grapevines"])

    target_to_epas = defaultdict(set)

    for pesticide in data:
        epa = pesticide.get("epa_reg_no", "")
        for app in pesticide.get("application_info", []):
            crops = [c.strip().lower() for c in (app.get("Target_Crop", "") or "").split(",") if c.strip()]
            targets = [d.strip() for d in (app.get("Target_Disease_Pest", "") or "").split(",") if d.strip()]
            if not any(cv in crops for cv in crop_variants):
                continue
            for t in targets:
                if target_type:
                    tt = get_target_type(t)
                    if tt != target_type:
                        continue
                for st in get_simplified_targets_list(t):
                    if st:
                        target_to_epas[st].add(epa)

    pairs = [(t, len(epas)) for t, epas in target_to_epas.items()]
    pairs.sort(key=lambda x: x[1], reverse=True)
    if top_k:
        pairs = pairs[:top_k]
    return pairs, target_to_epas


def build_precomputed_index():
    json_dir = detect_data_dir()
    log(f"Using JSON dir: {json_dir}")
    data = load_pesticide_data(json_dir)
    log(f"Loaded {len(data)} pesticide records")

    top_targets = {}
    lists = {}

    total_combos = len(ALLOWED_CROPS) * len(TARGET_TYPES)
    combo_idx = 0
    for crop in ALLOWED_CROPS:
        for ttype in TARGET_TYPES:
            combo_idx += 1
            log(f"Processing {crop} / {ttype} ({combo_idx}/{total_combos}) - computing top targets...")
            pairs, target_to_epas = compute_top_targets_for_crop_and_type(data, crop, ttype, top_k=10)

            key = f"{crop}|{ttype}"
            top_targets[key] = [{"name": t, "count": c} for t, c in pairs]
            log(f"Top targets ready for {key}: {[t for t,_ in pairs]}")

            # For each top target, compute exact EPA list by applying precise filter equivalently
            for i, entry in enumerate(top_targets[key], 1):
                starget = entry["name"]
                log(f"  [{i}/{len(top_targets[key])}] Building EPA list for target '{starget}'...")
                # Allowed original target names mapping for reverse lookup (lowercased for matching)
                original_targets = set(t.lower() for t in get_original_targets_for_simplified_target(starget))
                epa_set = set()
                for pesticide in data:
                    epa = pesticide.get("epa_reg_no", "")
                    # Crop/type/pest match
                    found = False
                    for app in pesticide.get("application_info", []):
                        crops = [c.strip().lower() for c in (app.get("Target_Crop", "") or "").split(",") if c.strip()]
                        pests = [d.strip().lower() for d in (app.get("Target_Disease_Pest", "") or "").split(",") if d.strip()]
                        crop_ok = any(cv in crops for cv in [crop.lower()]) or any(cv in crops for cv in [crop.lower()+"s"]) or any(cv in crops for cv in ["apples", "apple tree", "apple trees"]) if crop.lower()=="apple" else False
                        if not crop_ok:
                            # Simple variant handling
                            crop_ok = crop.lower() in crops
                        if not crop_ok:
                            continue
                        # target type
                        type_ok = True
                        if ttype:
                            type_ok = False
                            for pest_name in pests:
                                if get_target_type(pest_name) == ttype:
                                    type_ok = True
                                    break
                        if not type_ok:
                            continue
                        # pest simplified match via original reverse mapping (case-insensitive)
                        pest_ok = False
                        if not starget:
                            pest_ok = True
                        else:
                            for pest_name in pests:
                                if pest_name in original_targets:
                                    pest_ok = True
                                    break
                        if crop_ok and type_ok and pest_ok:
                            found = True
                            break
                    if found:
                        epa_set.add(epa)
                lists[f"{crop}|{ttype}|{starget}"] = sorted(epa_set)
                log(f"    -> {len(epa_set)} EPA regs")

            # Incremental write to a temp file so you can see progress on disk
            partial_out = {
                "meta": {"generated_at": int(time.time()), "version": 1, "partial": True},
                "top_targets": top_targets,
                "lists": lists,
            }
            tmp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precomputed_filter_index.tmp.json")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(partial_out, f, indent=2)
            log(f"Wrote partial progress to {tmp_path}")

    out = {
        "meta": {
            "generated_at": int(time.time()),
            "version": 1,
            "note": "Precomputed crop/target-type/target -> EPA lists and top targets",
        },
        "top_targets": top_targets,
        "lists": lists,
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precomputed_filter_index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    log(f"Wrote precomputed index to {out_path}")


if __name__ == "__main__":
    build_precomputed_index()



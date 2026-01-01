from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory

from .auth import (
    get_authenticated_supabase_client,
    get_current_user_id,
    is_authenticated,
    is_editor,
    refresh_access_token,
)
from .data import JsonPesticideStore, normalize_crop_key
from .supabase_client import get_supabase_client, is_supabase_configured
from .target_lookup_csv import TargetLookupCsv

bp = Blueprint("routes", __name__)

# Simple global store (fine for dev + single-process; later can be refactored)
_STORE = JsonPesticideStore(
    cache_seconds=int(os.environ.get("NYS_CACHE_SECONDS", "0"))
)
_TARGET_LOOKUP = TargetLookupCsv()

def _use_supabase_index() -> bool:
    return os.environ.get("NYS_USE_SUPABASE_INDEX", "0") == "1" and is_supabase_configured()


def _pesticide_summary_from_label_index_row(row: dict) -> dict:
    """Map Supabase label_index row -> frontend-compatible pesticide summary dict."""
    source_file = (row.get("source_file") or "").strip()
    epa = row.get("epa_reg_no")
    trade = row.get("trade_name")
    company = row.get("company_name")
    product_type = row.get("product_type")
    ingredients_json = row.get("active_ingredients_json") or []
    if not isinstance(ingredients_json, list):
        ingredients_json = []

    return {
        "_source_file": source_file,
        "epa_reg_no": epa,
        "trade_Name": trade,
        "company_name": company,
        "product_type": product_type,
        "Active_Ingredients": ingredients_json,
    }


@bp.route("/")
def homepage():
    return render_template("homepage.html")


@bp.route("/nys-pesticide-database")
def nys_pesticide_database():
    return render_template("search.html", active_tab="search")


@bp.route("/nys-pesticide-database/info")
def nys_pesticide_database_info():
    return render_template("info.html", active_tab="info")


@bp.route("/my-farm")
def my_farm():
    return render_template("my_farm.html", active_tab="my-farm")


@bp.route("/application-log")
def application_log():
    return render_template("application_log.html", active_tab="application-log")


@bp.route("/editor")
def editor():
    """Editor page for authorized users to edit crops, target types, and targets."""
    if not is_authenticated():
        abort(401)
    if not is_editor():
        abort(403)
    return render_template("editor.html", active_tab="editor")


@bp.route("/api/editor/crop-names")
def api_editor_crop_names():
    """Get crop names for editing (requires editor access)."""
    if not is_authenticated() or not is_editor():
        abort(403)
    
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "crop_names_unified.csv"
    
    # Get label counts per crop
    label_counts = _count_labels_per_crop()
    
    if not csv_path.exists():
        return jsonify({"crops": []})
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        crops = []
        for _, row in df.iterrows():
            original = str(row.get("original_crop_name", "")).strip()
            if not original or original.lower() == "nan":
                continue
            
            edited = str(row.get("edited_crop_name", "")).strip()
            if edited.lower() == "nan":
                edited = ""
            
            # Handle deployed (default True)
            deployed_raw = row.get("deployed", True)
            deployed = True
            if pd.notna(deployed_raw):
                if isinstance(deployed_raw, bool):
                    deployed = deployed_raw
                elif isinstance(deployed_raw, str):
                    deployed = deployed_raw.lower() in ("true", "1", "yes", "y")
                elif isinstance(deployed_raw, (int, float)):
                    deployed = bool(deployed_raw)
            
            # Get label count for this crop (normalize to match)
            normalized_original = normalize_crop_key(original)
            label_count = label_counts.get(normalized_original, 0)
            
            crops.append({
                "original_crop_name": original,
                "edited_crop_name": edited,
                "deployed": deployed,
                "label_count": label_count
            })
        return jsonify({"crops": crops})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/editor/crop-names", methods=["POST"])
def api_editor_save_crop_names():
    """Save edited crop names (requires editor access)."""
    if not is_authenticated() or not is_editor():
        abort(403)
    
    data = request.get_json()
    if not data or "crops" not in data:
        return jsonify({"error": "Invalid request"}), 400
    
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "crop_names_unified.csv"
    
    try:
        crops_data = []
        for crop in data["crops"]:
            original = str(crop.get("original_crop_name", "")).strip()
            if not original:
                continue
            
            edited = str(crop.get("edited_crop_name", "")).strip()
            deployed = crop.get("deployed", True)
            if isinstance(deployed, str):
                deployed = deployed.lower() in ("true", "1", "yes", "y")
            
            crops_data.append({
                "original_crop_name": original,
                "edited_crop_name": edited if edited else "",
                "deployed": deployed
            })
        
        df = pd.DataFrame(crops_data)
        df = df.sort_values("original_crop_name")
        df.to_csv(csv_path, index=False)
        
        return jsonify({"success": True, "message": f"Saved {len(crops_data)} crop names"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/editor/target-names")
def api_editor_target_names():
    """Get target names for editing (requires editor access).
    
    Returns deduplicated targets by (refined_target_name, source_target_type).
    Uses new_target_name if available, otherwise original_target_name.
    """
    if not is_authenticated() or not is_editor():
        abort(403)
    
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "target_names_unified.csv"
    
    # Load unified crop names mapping
    unified_crop_mapping, _ = _load_unified_crop_names()
    
    # Count labels per target (per unified crop + type + refined target)
    target_label_counts = _count_labels_per_target()
    
    if not csv_path.exists():
        return jsonify({"targets": [], "unified_crops": []})
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        
        # Deduplicate by (unified_crop, refined_target_name, source_target_type)
        # where refined_target_name = new_target_name if exists, else original_target_name
        deduplicated: dict[tuple[str, str, str], dict] = {}  # (unified_crop, refined_target_name, source_target_type) -> target data
        crops_seen: set[str] = set()
        
        for _, row in df.iterrows():
            original_target = str(row.get("original_target_name", "")).strip()
            original_crop = str(row.get("original_crop", "")).strip()
            original_target_type = str(row.get("original_target_type", "")).strip()
            source_target_type = str(row.get("source_target_type", "")).strip()
            
            if not original_target or not original_crop:
                continue
            
            new_target = str(row.get("new_target_name", "")).strip()
            new_target_species = str(row.get("new_target_species", "")).strip()
            
            # Handle "nan" string values - convert to empty string
            if new_target.lower() == "nan":
                new_target = ""
            if new_target_species.lower() == "nan":
                new_target_species = ""
            if source_target_type.lower() == "nan":
                source_target_type = ""
            
            # Refined target name: use new_target_name if available, otherwise original_target_name
            refined_target_name = new_target if new_target else original_target
            
            # Use source_target_type if available, otherwise fall back to original_target_type
            display_target_type = source_target_type if source_target_type else original_target_type
            
            # Get unified crop name for this original crop
            normalized_original_crop = normalize_crop_key(original_crop)
            unified_crop = unified_crop_mapping.get(normalized_original_crop, original_crop)
            unified_crop_display = unified_crop.title() if unified_crop else original_crop
            
            crops_seen.add(unified_crop_display)
            
            # Handle deployed (default True) - OR merge across duplicates
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
            
            # Handle main_target_list (default False) - OR merge across duplicates
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
            
            # Deduplication key: (unified_crop, refined_target_name, source_target_type)
            key = (unified_crop_display, refined_target_name, display_target_type)
            
            if key not in deduplicated:
                # Get label count for this (unified_crop, refined_target_name, source_target_type) combination
                crop_norm = normalize_crop_key(unified_crop_display)
                refined_l = refined_target_name.lower().strip()
                type_l = display_target_type.lower().strip()
                label_count = target_label_counts.get((crop_norm, type_l, refined_l), 0)

                # If this (crop, type, refined target) doesn't map to any label in the JSONs,
                # hide it from the editor to keep the editor consistent with the guided filter.
                if label_count <= 0:
                    continue
                
                deduplicated[key] = {
                    "refined_target_name": refined_target_name,
                    "source_target_type": display_target_type,
                    "new_target_name": new_target,  # Current new_target_name (for editing)
                    "new_target_species": new_target_species,  # Current new_target_species (for editing)
                    "unified_crop": unified_crop_display,
                    "deployed": deployed,
                    "main_target_list": main_target_list,
                    "label_count": label_count,
                    # Keep original values for reference and filtering
                    "original_target_name": original_target,
                    "original_crop": original_crop,
                    "original_target_type": original_target_type,
                }
            else:
                # Merge flags (OR logic)
                deduplicated[key]["deployed"] = deduplicated[key]["deployed"] or deployed
                deduplicated[key]["main_target_list"] = deduplicated[key]["main_target_list"] or main_target_list
                # Label count is already set from the first occurrence (same key = same count)
        
        # Convert to list
        targets = list(deduplicated.values())
        
        # Return sorted list of unified crops
        unified_crops = sorted(crops_seen, key=lambda x: x.lower())
        
        return jsonify({"targets": targets, "unified_crops": unified_crops})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/editor/target-names", methods=["POST"])
def api_editor_save_target_names():
    """Save edited target names (requires editor access).
    
    Updates all rows matching (refined_target_name, source_target_type) with the new values.
    """
    if not is_authenticated() or not is_editor():
        abort(403)
    
    data = request.get_json()
    if not data or "targets" not in data:
        return jsonify({"error": "Invalid request"}), 400
    
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "target_names_unified.csv"
    
    if not csv_path.exists():
        return jsonify({"error": "target_names_unified.csv not found"}), 404
    
    try:
        # Load existing CSV
        df = pd.read_csv(csv_path, low_memory=False)
        
        # Ensure required columns exist
        if "source_target_type" not in df.columns:
            df["source_target_type"] = ""
        if "new_target_name" not in df.columns:
            df["new_target_name"] = ""
        if "new_target_species" not in df.columns:
            df["new_target_species"] = ""
        
        # Load unified crop names mapping for crop-scoped updates
        unified_crop_mapping, _ = _load_unified_crop_names()  # normalized_original -> unified_lower

        # Precompute normalized unified crop for each row
        def _row_unified_crop_norm(x: Any) -> str:
            raw = str(x or "").strip()
            if not raw or raw.lower() == "nan":
                return ""
            norm = normalize_crop_key(raw)
            return normalize_crop_key(unified_crop_mapping.get(norm, norm))

        df_unified_crop_norm = df["original_crop"].apply(_row_unified_crop_norm) if "original_crop" in df.columns else pd.Series([""] * len(df))

        # Precompute refined name + display type (as the editor sees them) for matching
        df_new = df["new_target_name"].fillna("").astype(str) if "new_target_name" in df.columns else pd.Series([""] * len(df))
        df_new = df_new.apply(lambda s: "" if str(s).strip().lower() == "nan" else str(s))
        df_orig = df["original_target_name"].fillna("").astype(str) if "original_target_name" in df.columns else pd.Series([""] * len(df))
        df_refined = df_new.apply(lambda s: str(s).strip())  # candidate
        df_refined = df_refined.where(df_refined != "", df_orig.apply(lambda s: str(s).strip()))
        df_refined_l = df_refined.str.lower()

        df_source = df["source_target_type"].fillna("").astype(str) if "source_target_type" in df.columns else pd.Series([""] * len(df))
        df_source = df_source.apply(lambda s: "" if str(s).strip().lower() == "nan" else str(s))
        df_orig_type = df["original_target_type"].fillna("").astype(str) if "original_target_type" in df.columns else pd.Series(["Other"] * len(df))
        df_display_type = df_source.apply(lambda s: str(s).strip())
        df_display_type = df_display_type.where(df_display_type != "", df_orig_type.apply(lambda s: str(s).strip() or "Other"))
        df_display_type_l = df_display_type.str.lower()

        # Process each edited target
        for target in data["targets"]:
            refined_target_name = str(target.get("refined_target_name", "")).strip()
            source_target_type = str(target.get("source_target_type", "")).strip()
            unified_crop = str(target.get("unified_crop", "")).strip()
            new_target_name = str(target.get("new_target_name", "")).strip()
            new_target_type = str(target.get("new_target_type", "")).strip()  # This will overwrite source_target_type
            new_target_species = str(target.get("new_target_species", "")).strip()
            
            if not refined_target_name or not source_target_type or not unified_crop:
                continue

            crop_norm = normalize_crop_key(unified_crop)
            refined_l = refined_target_name.lower().strip()
            type_l = source_target_type.lower().strip()

            # Match by unified crop + refined name + displayed type
            mask = (
                (df_unified_crop_norm == crop_norm) &
                (df_refined_l == refined_l) &
                (df_display_type_l == type_l)
            )
            
            if mask.any():
                # Update matching rows
                if new_target_name:
                    df.loc[mask, "new_target_name"] = new_target_name
                if new_target_type:
                    # Overwrite source_target_type with new_target_type
                    df.loc[mask, "source_target_type"] = new_target_type
                if new_target_species:
                    df.loc[mask, "new_target_species"] = new_target_species
                
                # Update deployed and main_target_list if provided
                if "deployed" in target:
                    deployed = target["deployed"]
                    if isinstance(deployed, str):
                        deployed = deployed.lower() in ("true", "1", "yes", "y")
                    df.loc[mask, "deployed"] = deployed
                
                if "main_target_list" in target:
                    main_target_list = target["main_target_list"]
                    if isinstance(main_target_list, str):
                        main_target_list = main_target_list.lower() in ("true", "1", "yes", "y")
                    df.loc[mask, "main_target_list"] = main_target_list
        
        # Save updated CSV
        df = df.sort_values(["original_crop", "source_target_type", "original_target_name"])
        df.to_csv(csv_path, index=False)
        
        return jsonify({"success": True, "message": f"Saved changes to target entries"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/pdf-viewer")
def pdf_viewer():
    """
    Minimal PDF.js viewer page.

    Query params:
    - file: relative PDF URL (must start with /pdfs/)
    - page: initial page number
    - zoom: initial zoom percent
    """
    file = request.args.get("file", default="", type=str)

    # Security: only allow serving PDFs from our /pdfs/ route (same-origin)
    # Prevent path traversal and external URLs.
    if not file.startswith("/pdfs/") or ".." in file or "\\" in file:
        abort(404)

    return render_template("pdf_viewer.html")


@bp.route("/pdfs/<path:filename>")
def serve_pdf(filename: str):
    """Serve PDF files from the PDFs directory."""
    # web_application_nys/app -> web_application_nys -> .. -> PDFs
    app_dir = Path(__file__).resolve().parents[1]
    pdfs_dir = (app_dir / ".." / "PDFs").resolve()
    
    # Security: ensure filename doesn't contain path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        abort(404)
    
    # Check if file exists
    pdf_path = pdfs_dir / filename
    if not pdf_path.exists() or not pdf_path.is_file():
        abort(404)
    
    # Only serve PDF files
    if not filename.lower().endswith(".pdf"):
        abort(404)
    
    return send_from_directory(str(pdfs_dir), filename, mimetype="application/pdf")


@bp.route("/api/health")
def api_health():
    try:
        stats = _STORE.stats()
        return jsonify(
            {
                "status": "healthy",
                "json_dir": str(_STORE.json_dir),
                "total_files": stats.total_files,
                "total_records": stats.total_records,
            }
        )
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@bp.route("/api/stats")
def api_stats():
    stats = _STORE.stats()
    return jsonify(
        {
            "total_files": stats.total_files,
            "total_records": stats.total_records,
            "last_updated_ts": stats.last_updated_ts,
        }
    )


@bp.route("/api/pesticides")
def api_pesticides():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    items, total = _STORE.list_page(page=page, per_page=per_page)

    return jsonify(
        {
            "pesticides": items,
            "pagination": {
                "page": page,
                "per_page": min(max(per_page, 1), 500),
                "total": total,
                "pages": (total + max(per_page, 1) - 1) // max(per_page, 1),
                "has_next": page * max(per_page, 1) < total,
                "has_prev": page > 1,
            },
        }
    )


@bp.route("/api/search")
def api_search():
    query = request.args.get("q", default="", type=str)
    search_type = request.args.get("type", default="both", type=str)
    limit = request.args.get("limit", default=200, type=int)

    if _use_supabase_index():
        client = get_supabase_client()
        if not client:
            return jsonify({"error": "Supabase not configured"}), 500

        q = (query or "").strip()
        if not q:
            return jsonify({"query": query, "search_type": search_type, "total": 0, "results": []})

        limit = min(max(int(limit), 1), 500)

        # For now, use a denormalized `search_text` field for fast substring search.
        # This keeps behavior consistent across trade/company/epa/ingredients.
        sel = "source_file,epa_reg_no,trade_name,company_name,product_type,active_ingredients_json"
        req = client.table("label_index").select(sel).ilike("search_text", f"%{q.lower()}%").limit(limit)

        # If a specific search type is requested, bias it with an additional filter.
        st = (search_type or "both").strip()
        if st == "epa_reg_no":
            req = client.table("label_index").select(sel).ilike("epa_reg_no", f"%{q}%").limit(limit)
        elif st == "trade_Name":
            req = client.table("label_index").select(sel).ilike("trade_name", f"%{q}%").limit(limit)
        elif st == "company":
            req = client.table("label_index").select(sel).ilike("company_name", f"%{q}%").limit(limit)
        # active_ingredient currently goes through search_text

        resp = req.execute()
        rows = resp.data or []
        results = [_pesticide_summary_from_label_index_row(r) for r in rows if isinstance(r, dict)]
    else:
        results = _STORE.search(query=query, search_type=search_type, limit=limit)

    return jsonify(
        {
            "query": query,
            "search_type": search_type,
            "total": len(results),
            "results": results,
        }
    )


@bp.route("/api/pesticide/<path:epa_reg_no>")
def api_pesticide_detail(epa_reg_no: str):
    p = _STORE.get_by_epa(epa_reg_no)
    if not p:
        return jsonify({"error": "Pesticide not found", "epa_reg_no": epa_reg_no}), 404
    return jsonify(p)


@bp.route("/api/pesticide-file/<path:source_file>")
def api_pesticide_detail_by_file(source_file: str):
    """Fetch pesticide details by JSON filename to avoid EPA-reg-no collisions."""
    # Only allow basename lookups (prevent path traversal / accidental slashes)
    fname = os.path.basename(source_file or "")
    p = _STORE.get_by_source_file(fname)
    if not p:
        return jsonify({"error": "Pesticide not found", "source_file": fname}), 404
    return jsonify(p)


def _load_unified_crop_names() -> tuple[dict[str, str], dict[str, bool]]:
    """Load crop_names_unified.csv and return mappings for unified names and deployed status.
    
    Returns:
        Tuple of:
        - Dictionary mapping normalized_original_crop_name -> unified_crop_name
        - Dictionary mapping normalized_original_crop_name -> deployed (bool)
    """
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "crop_names_unified.csv"
    
    if not csv_path.exists():
        return {}, {}
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        if "original_crop_name" not in df.columns:
            return {}, {}
        
        # Map normalized original crop name -> unified crop name
        mapping: dict[str, str] = {}
        deployed_map: dict[str, bool] = {}
        
        for _, row in df.iterrows():
            original_raw = row.get("original_crop_name")
            edited_raw = row.get("edited_crop_name")
            deployed_raw = row.get("deployed", True)  # Default to True if column doesn't exist
            
            # Handle pandas NaN and string "nan"
            original = ""
            if pd.notna(original_raw):
                original = str(original_raw).strip()
            if original.lower() == "nan":
                original = ""
            
            edited = ""
            if pd.notna(edited_raw):
                edited = str(edited_raw).strip()
            if edited.lower() == "nan":
                edited = ""
            
            # Handle deployed (default True)
            deployed = True
            if pd.notna(deployed_raw):
                if isinstance(deployed_raw, bool):
                    deployed = deployed_raw
                elif isinstance(deployed_raw, str):
                    deployed = deployed_raw.lower() in ("true", "1", "yes", "y")
                elif isinstance(deployed_raw, (int, float)):
                    deployed = bool(deployed_raw)
            
            # Skip empty original crop names
            if not original:
                continue
            
            # Normalize the original crop name to match how _STORE.list_crops() normalizes
            normalized_original = normalize_crop_key(original)
            if not normalized_original:
                continue
            
            # Determine unified name: use edited if provided and not empty, otherwise use normalized original
            if edited and edited.strip():
                # Normalize the edited name too for consistency
                unified = normalize_crop_key(edited)
                if unified:
                    mapping[normalized_original] = unified
                else:
                    mapping[normalized_original] = normalized_original
            else:
                mapping[normalized_original] = normalized_original
            
            deployed_map[normalized_original] = deployed
        return mapping, deployed_map
    except Exception:
        return {}, {}


def _get_unified_crop_name(crop_name: str, unified_mapping: dict[str, str]) -> str:
    """Get the unified crop name for a given crop name."""
    return unified_mapping.get(crop_name, crop_name)


def _load_unified_target_names() -> dict[str, dict[str, Any]]:
    """Load target_names_unified.csv and return a mapping.
    
    Returns:
        Dictionary mapping (normalized_target, normalized_crop) -> {
            'unified_target': str,
            'unified_target_type': str,
            'original_target_type': str,
            'deployed': bool,
            'main_target_list': bool
        }
    """
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "target_names_unified.csv"
    
    if not csv_path.exists():
        return {}
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        required_cols = ["original_target_name", "original_crop", "original_target_type"]
        if not all(col in df.columns for col in required_cols):
            return {}
        
        mapping: dict[tuple[str, str], dict[str, Any]] = {}
        
        for _, row in df.iterrows():
            original_target_raw = row.get("original_target_name")
            original_crop_raw = row.get("original_crop")
            original_target_type_raw = row.get("original_target_type")
            
            # Handle pandas NaN
            original_target = ""
            if pd.notna(original_target_raw):
                original_target = str(original_target_raw).strip()
            if original_target.lower() == "nan" or not original_target:
                continue
            
            original_crop = ""
            if pd.notna(original_crop_raw):
                original_crop = str(original_crop_raw).strip()
            if original_crop.lower() == "nan" or not original_crop:
                continue
            
            original_target_type = ""
            if pd.notna(original_target_type_raw):
                original_target_type = str(original_target_type_raw).strip()
            if original_target_type.lower() == "nan" or not original_target_type:
                original_target_type = "Other"
            
            new_target_raw = row.get("new_target_name", "")
            new_target_type_raw = row.get("new_target_type", "")
            
            new_target = ""
            if pd.notna(new_target_raw):
                new_target = str(new_target_raw).strip()
            if new_target.lower() == "nan":
                new_target = ""
            
            new_target_type = ""
            if pd.notna(new_target_type_raw):
                new_target_type = str(new_target_type_raw).strip()
            if new_target_type.lower() == "nan":
                new_target_type = ""
            
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
            
            # Normalize for lookup key (CSV is now unique by crop+target, not crop+target+type)
            normalized_target = original_target.lower().strip()
            normalized_crop = normalize_crop_key(original_crop)
            key = (normalized_target, normalized_crop)
            
            # Determine unified values
            unified_target = new_target.lower().strip() if new_target else normalized_target
            unified_target_type = new_target_type.lower().strip() if new_target_type else original_target_type.lower().strip()
            
            mapping[key] = {
                'unified_target': unified_target,
                'unified_target_type': unified_target_type,
                'original_target_type': original_target_type.lower().strip(),
                'deployed': deployed,
                'main_target_list': main_target_list
            }
        
        return mapping
    except Exception:
        return {}


def _count_labels_per_crop() -> dict[str, int]:
    """Count the number of unique pesticide labels (EPA reg nos) per normalized crop."""
    crop_label_counts: dict[str, set[str]] = {}  # normalized_crop -> set of epa_reg_nos
    
    for p, app in _STORE.iter_applications():
        epa = str(p.get("epa_reg_no") or "").strip()
        if not epa:
            continue
        
        for crop in app.get("Target_Crop", []) or []:
            if not isinstance(crop, dict):
                continue
            raw = str(crop.get("name") or "").strip()
            if not raw:
                continue
            normalized = normalize_crop_key(raw)
            if normalized:
                crop_label_counts.setdefault(normalized, set()).add(epa)
    
    # Convert to counts
    return {crop: len(epas) for crop, epas in crop_label_counts.items()}


def _build_target_mapping_from_csv() -> dict[tuple[str, str], dict[str, Any]]:
    """Build a lookup from (normalized_original_crop, normalized_target_name) -> unified info.

    This is the canonical mapping used by guided filter + editor to:
    - map raw JSON target names to refined names (new_target_name) when present
    - use source_target_type when present (otherwise original_target_type)
    - respect deployed/main_target_list flags
    """
    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "target_names_unified.csv"
    if not csv_path.exists():
        return {}

    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception:
        return {}

    mapping: dict[tuple[str, str], dict[str, Any]] = {}

    for _, row in df.iterrows():
        original_target = str(row.get("original_target_name", "")).strip()
        original_crop = str(row.get("original_crop", "")).strip()
        original_target_type = str(row.get("original_target_type", "")).strip() or "Other"
        source_target_type = str(row.get("source_target_type", "")).strip()
        new_target = str(row.get("new_target_name", "")).strip()

        if not original_target or not original_crop:
            continue

        if new_target.lower() == "nan":
            new_target = ""
        if source_target_type.lower() == "nan":
            source_target_type = ""

        refined_target_name = (new_target if new_target else original_target).strip()
        display_target_type = (source_target_type if source_target_type else original_target_type).strip() or "Other"

        # deployed (default True)
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

        # main_target_list (default False)
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

        key = (normalize_crop_key(original_crop), normalize_crop_key(original_target))
        mapping[key] = {
            "refined_target_name": refined_target_name,
            "refined_target_l": refined_target_name.lower().strip(),
            "display_target_type": display_target_type,
            "display_target_type_l": display_target_type.lower().strip(),
            "deployed": deployed,
            "main_target_list": main_target_list,
        }

    return mapping


def _count_labels_per_target() -> dict[tuple[str, str, str], int]:
    """Count unique labels per (unified_crop, display_target_type, refined_target_name).

    Key is normalized: (unified_crop_norm, display_type_lower, refined_target_lower).
    """
    target_mapping = _build_target_mapping_from_csv()
    if not target_mapping:
        return {}

    unified_crop_mapping, _ = _load_unified_crop_names()  # normalized_original -> unified_lower

    # (unified_crop_norm, type_l, refined_target_l) -> set[source_file]
    counts: dict[tuple[str, str, str], set[str]] = {}

    for p, app in _STORE.iter_applications():
        source_file = str(p.get("_source_file") or "").strip()
        if not source_file:
            epa = str(p.get("epa_reg_no") or "").strip()
            if not epa:
                continue
            source_file = epa.lower()
        source_file_l = source_file.lower()

        # Collect all crop variants in this application (original + unified)
        crop_pairs: list[tuple[str, str]] = []  # (normalized_original_crop, unified_crop_norm)
        for crop in app.get("Target_Crop", []) or []:
            if not isinstance(crop, dict):
                continue
            raw = str(crop.get("name") or "").strip()
            if not raw:
                continue
            norm_orig = normalize_crop_key(raw)
            if not norm_orig:
                continue
            unified_norm = normalize_crop_key(unified_crop_mapping.get(norm_orig, norm_orig))
            crop_pairs.append((norm_orig, unified_norm))

        if not crop_pairs:
            continue

        for t in app.get("Target_Disease_Pest", []) or []:
            if not isinstance(t, dict):
                continue
            target_name = str(t.get("name") or "").strip()
            if not target_name:
                continue
            norm_target = normalize_crop_key(target_name)
            if not norm_target:
                continue

            for norm_orig_crop, unified_crop_norm in crop_pairs:
                info = target_mapping.get((norm_orig_crop, norm_target))
                if not info:
                    continue
                if not info.get("deployed", True):
                    continue
                refined_l = str(info.get("refined_target_l") or "").strip().lower()
                type_l = str(info.get("display_target_type_l") or "other").strip().lower()
                if not refined_l or not unified_crop_norm:
                    continue
                counts.setdefault((unified_crop_norm, type_l, refined_l), set()).add(source_file_l)

    return {k: len(v) for k, v in counts.items()}


@bp.route("/api/enums/crops")
def api_enums_crops():
    """Return unique crops for guided filtering, using unified crop names if available.
    
    Only includes crops where deployed=True in the CSV.
    If edited_crop_name is blank in the CSV, uses normalized original_crop_name.
    Crops not in the CSV use their normalized original name and are included by default.
    """
    if _use_supabase_index():
        client = get_supabase_client()
        if not client:
            return jsonify({"error": "Supabase not configured"}), 500

        # label_crop_counts has unique crop_norm rows already
        resp = client.table("label_crop_counts").select("crop_norm,label_count").execute()
        rows = resp.data or []
        crops = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            cn = str(r.get("crop_norm") or "").strip()
            if cn:
                crops.append(cn.title())
        crops = sorted(set(crops), key=lambda x: x.lower())
        return jsonify({"crops": crops})

    all_crops = _STORE.list_crops()  # These are title-cased normalized names like "Carrot", "Oat"
    unified_mapping, deployed_map = _load_unified_crop_names()  # Maps normalized_lowercase -> unified_lowercase, deployed
    
    # Group crops by their unified name, filtering out non-deployed crops
    # unified_mapping maps: normalized_original (lowercase) -> unified_name (lowercase)
    unified_to_originals: dict[str, list[str]] = {}
    for crop in all_crops:
        # Normalize the crop name to lowercase for lookup
        normalized_crop_lower = normalize_crop_key(crop)
        
        # Check if this crop is deployed (default True if not in CSV)
        is_deployed = deployed_map.get(normalized_crop_lower, True)
        if not is_deployed:
            continue
        
        # Get unified name: if crop is in mapping, use mapped value, otherwise use the crop name itself
        unified_lower = unified_mapping.get(normalized_crop_lower, normalized_crop_lower)
        # Title-case the unified name for display
        unified_display = unified_lower.title() if unified_lower else crop
        unified_to_originals.setdefault(unified_display, []).append(crop)
    
    # Return unique unified crop names (sorted)
    # These will be the edited names if provided, otherwise normalized original names
    unified_crops = sorted(unified_to_originals.keys(), key=lambda x: x.lower())
    return jsonify({"crops": unified_crops})


@bp.route("/api/enums/target-types")
def api_enums_target_types():
    """Return target types for a given crop from target_names_unified.csv."""
    crop = normalize_crop_key(request.args.get("crop", default="", type=str))

    if _use_supabase_index():
        if not crop:
            return jsonify({"crop": crop, "target_types": ["Other"]})
        client = get_supabase_client()
        if not client:
            return jsonify({"error": "Supabase not configured"}), 500

        resp = (
            client.table("label_crop_target_type_counts")
            .select("target_type_norm")
            .eq("crop_norm", crop)
            .execute()
        )
        rows = resp.data or []
        types = []
        for r in rows:
            if isinstance(r, dict):
                t = str(r.get("target_type_norm") or "").strip()
                if t:
                    types.append(t.title())
        types = sorted(set(types), key=lambda x: x.lower()) or ["Other"]
        return jsonify({"crop": crop, "target_types": types})

    script_dir = Path(__file__).resolve().parent.parent.parent
    csv_path = script_dir / "target_names_unified.csv"
    
    # Load unified crop names mapping
    unified_crop_mapping, _ = _load_unified_crop_names()
    
    # Create reverse mapping: unified -> list of originals
    unified_to_originals: dict[str, list[str]] = {}
    for orig, unified in unified_crop_mapping.items():
        unified_to_originals.setdefault(unified, []).append(orig)
    # Also add crops that aren't in the mapping
    all_crops = _STORE.list_crops()
    for c in all_crops:
        if c not in unified_crop_mapping:
            unified_to_originals.setdefault(c, []).append(c)
    
    # Get all original crop names that map to the selected unified crop
    if crop:
        matching_originals = unified_to_originals.get(crop, [crop])
        matching_originals_normalized = {normalize_crop_key(c) for c in matching_originals}
    else:
        matching_originals_normalized = None
    
    if not csv_path.exists():
        return jsonify({"crop": crop, "target_types": ["Other"]})
    
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        
        # Filter by crop if specified
        if crop and matching_originals_normalized:
            # Filter rows where original_crop matches any of the matching originals
            crop_mask = df['original_crop'].apply(
                lambda x: normalize_crop_key(str(x) if pd.notna(x) else "") in matching_originals_normalized
            )
            df_filtered = df[crop_mask]
        else:
            df_filtered = df
        
        # Get unique target types from original_target_type column
        target_types = df_filtered['original_target_type'].dropna().unique()
        target_types = [str(t).strip() for t in target_types if t and str(t).strip()]
        
        # Remove duplicates and sort
        target_types = sorted(set(target_types))
        
        # If no target types found, return "Other"
        if not target_types:
            target_types = ["Other"]
        
        return jsonify({"crop": crop, "target_types": target_types})
    except Exception as e:
        # Fallback to Other if there's an error
        return jsonify({"crop": crop, "target_types": ["Other"], "error": str(e)})


@bp.route("/api/enums/targets")
def api_enums_targets():
    """Return simplified targets (with counts) for crop + target type, using unified targets.
    
    Only includes targets where deployed=True.
    Targets with main_target_list=True are marked in the response.
    """
    crop = request.args.get("crop", default="", type=str).strip()  # This is already unified
    target_type = request.args.get("target_type", default="", type=str).strip()

    if not crop:
        return jsonify({"error": "crop is required"}), 400
    if not target_type:
        return jsonify({"error": "target_type is required"}), 400

    if _use_supabase_index():
        client = get_supabase_client()
        if not client:
            return jsonify({"error": "Supabase not configured"}), 500

        crop_norm = normalize_crop_key(crop)
        type_norm = target_type.lower().strip()
        resp = (
            client.table("label_crop_target_counts")
            .select("target_norm,label_count,main_target_list")
            .eq("crop_norm", crop_norm)
            .eq("target_type_norm", type_norm)
            .execute()
        )
        rows = resp.data or []
        main_targets = []
        other_targets = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            tn = str(r.get("target_norm") or "").strip()
            if not tn:
                continue
            count = int(r.get("label_count") or 0)
            is_main = bool(r.get("main_target_list") or False)
            obj = {"name": tn.title(), "count": count, "main_target_list": is_main}
            (main_targets if is_main else other_targets).append(obj)

        main_targets.sort(key=lambda x: (-x["count"], x["name"].lower()))
        other_targets.sort(key=lambda x: (-x["count"], x["name"].lower()))
        targets = main_targets + other_targets
        return jsonify(
            {
                "crop": crop,
                "target_type": target_type,
                "targets": targets,
                "main_targets": [t["name"] for t in main_targets],
                "has_more": len(other_targets) > 0,
            }
        )

    unified_mapping, _ = _load_unified_crop_names()
    target_mapping = _build_target_mapping_from_csv()
    if not target_mapping:
        return jsonify({"crop": crop, "target_type": target_type, "targets": [], "main_targets": []})
    
    # Create reverse mapping: unified -> list of originals
    unified_to_originals: dict[str, list[str]] = {}
    for orig, unified in unified_mapping.items():
        unified_to_originals.setdefault(unified, []).append(orig)
    # Also add crops that aren't in the mapping
    all_crops = _STORE.list_crops()
    for c in all_crops:
        if c not in unified_mapping:
            unified_to_originals.setdefault(c, []).append(c)

    # Get all original crop names that map to the selected unified crop
    matching_originals = unified_to_originals.get(crop, [crop])
    matching_originals_normalized = {normalize_crop_key(c) for c in matching_originals}

    # refined_target_name -> {'count': int, 'main_target_list': bool, 'source_files': set}
    buckets: dict[str, dict[str, Any]] = {}
    normalized_type = target_type.lower().strip()

    for p, app in _STORE.iter_applications():
        # Crop match: collect all matching original crop variants in this application
        matched_crop_norms: set[str] = set()
        for c in app.get("Target_Crop", []) or []:
            if not isinstance(c, dict):
                continue
            original_crop = str(c.get("name") or "").strip()
            norm = normalize_crop_key(original_crop)
            if norm and norm in matching_originals_normalized:
                matched_crop_norms.add(norm)

        if not matched_crop_norms:
            continue

        source_file = str(p.get("_source_file") or "").strip()
        if not source_file:
            source_file = str(p.get("epa_reg_no") or "").strip().lower()
        
        for t in app.get("Target_Disease_Pest", []) or []:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name:
                continue

            normalized_target = normalize_crop_key(name)
            if not normalized_target:
                continue

            # Find first matching mapping among crop variants
            hit_info = None
            for crop_norm in matched_crop_norms:
                hit_info = target_mapping.get((crop_norm, normalized_target))
                if hit_info:
                    break
            if not hit_info:
                continue

            if not hit_info.get("deployed", True):
                continue
            if hit_info.get("display_target_type_l", "").lower().strip() != normalized_type:
                continue

            refined_target_name = str(hit_info.get("refined_target_name") or "").strip()
            if not refined_target_name:
                continue

            bucket_key = refined_target_name.lower().strip()
            refined_target_display = refined_target_name.title()
            main_target_list = bool(hit_info.get("main_target_list", False))

            if bucket_key not in buckets:
                buckets[bucket_key] = {
                    "name": refined_target_display,
                    "count": 0,
                    "main_target_list": main_target_list,
                    "source_files": set(),
                }

            buckets[bucket_key]["source_files"].add(source_file)
            buckets[bucket_key]["count"] = len(buckets[bucket_key]["source_files"])

    # Convert to list and sort: main_target_list first, then by count descending, then alphabetically
    targets = []
    main_targets = []
    other_targets = []
    
    for unified_target, data in buckets.items():
        target_obj = {
            "name": data['name'],
            "count": data['count'],
            "main_target_list": data['main_target_list']
        }
        if data['main_target_list']:
            main_targets.append(target_obj)
        else:
            other_targets.append(target_obj)
    
    # Sort main targets by count desc, then name
    main_targets.sort(key=lambda x: (-x["count"], x["name"].lower()))
    # Sort other targets by count desc, then name
    other_targets.sort(key=lambda x: (-x["count"], x["name"].lower()))
    
    # Combine: main targets first, then other targets
    targets = main_targets + other_targets
    
    return jsonify({
        "crop": crop,
        "target_type": target_type,
        "targets": targets,
        "main_targets": [t["name"] for t in main_targets],
        "has_more": len(other_targets) > 0
    })


@bp.route("/api/enums/units")
def api_enums_units():
    """Return unique unified units from units_unified.csv."""
    try:
        script_dir = Path(__file__).resolve().parent.parent.parent
        units_csv_path = script_dir / "units_unified.csv"
        
        if not units_csv_path.exists():
            return jsonify({"error": "units_unified.csv not found"}), 404
        
        df = pd.read_csv(units_csv_path, low_memory=False)
        
        # Get unique non-blank values from the "Unified" column
        unified_col = None
        for c in df.columns:
            if str(c).strip().lower() == "unified":
                unified_col = c
                break
        
        if unified_col is None:
            return jsonify({"error": "Unified column not found in units_unified.csv"}), 500
        
        units = df[unified_col].dropna().unique()
        units = [str(u).strip() for u in units if str(u).strip()]
        units = sorted(units)
        
        return jsonify({"units": units})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/filter")
def api_filter():
    """Filter pesticides by crop + target type + simplified target (guided filter)."""
    crop = request.args.get("crop", default="", type=str).strip()  # This is already unified
    target_type = request.args.get("target_type", default="", type=str).strip()
    target = request.args.get("target", default="", type=str).strip()
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    if not crop or not target_type or not target:
        return jsonify({"error": "crop, target_type, and target are required"}), 400

    page = max(page, 1)
    per_page = min(max(per_page, 1), 500)

    if _use_supabase_index():
        client = get_supabase_client()
        if not client:
            return jsonify({"error": "Supabase not configured"}), 500

        crop_norm = normalize_crop_key(crop)
        type_norm = target_type.lower().strip()
        target_norm = target.lower().strip()

        start = (page - 1) * per_page
        end = start + per_page - 1

        sel = (
            "source_file,"
            "label_index(source_file,epa_reg_no,trade_name,company_name,product_type,active_ingredients_json)"
        )
        resp = (
            client.table("label_crop_target")
            .select(sel, count="exact")
            .eq("crop_norm", crop_norm)
            .eq("target_type_norm", type_norm)
            .eq("target_norm", target_norm)
            .range(start, end)
            .execute()
        )

        total = int(getattr(resp, "count", 0) or 0)
        out: list[dict] = []
        for row in resp.data or []:
            if not isinstance(row, dict):
                continue
            li = row.get("label_index")
            if not isinstance(li, dict):
                continue
            out.append(_pesticide_summary_from_label_index_row(li))

        return jsonify(
            {
                "pesticides": out,
                "total": total,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "has_next": (start + len(out)) < total,
                    "total_pages": (total + per_page - 1) // per_page if total else 0,
                },
            }
        )

    unified_mapping, _ = _load_unified_crop_names()
    # Create reverse mapping: unified -> list of originals
    unified_to_originals: dict[str, list[str]] = {}
    for orig, unified in unified_mapping.items():
        unified_to_originals.setdefault(unified, []).append(orig)
    # Also add crops that aren't in the mapping
    all_crops = _STORE.list_crops()
    for c in all_crops:
        if c not in unified_mapping:
            unified_to_originals.setdefault(c, []).append(c)

    # Get all original crop names that map to the selected unified crop
    matching_originals = unified_to_originals.get(crop, [crop])
    matching_originals_normalized = {normalize_crop_key(c) for c in matching_originals}

    # Build target mapping from CSV once
    target_mapping = _build_target_mapping_from_csv()

    matched: list[dict] = []
    seen_source_files: set[str] = set()

    target_l = target.lower()
    target_type_l = target_type.lower().strip()

    for p, app in _STORE.iter_applications():
        # Use source_file (unique per label) for deduplication instead of EPA reg no
        source_file = str(p.get("_source_file") or "").strip()
        if not source_file:
            # Fallback to EPA reg no if source_file is missing (shouldn't happen in normal operation)
            epa = str(p.get("epa_reg_no") or "").strip()
            if not epa:
                continue
            source_file = epa.lower()  # Use normalized EPA as fallback
        
        # Normalize source_file to lowercase for consistent deduplication
        source_file_normalized = source_file.lower()
        
        # Skip if we've already added this pesticide label (check at the very start)
        if source_file_normalized in seen_source_files:
            continue

        # Crop match - check if any original crop matches the unified crop
        crop_ok = False
        crop_normalized = None
        for c in app.get("Target_Crop", []) or []:
            if isinstance(c, dict):
                original_crop = str(c.get("name") or "").strip()
                normalized_original = normalize_crop_key(original_crop)
                if normalized_original in matching_originals_normalized:
                    crop_ok = True
                    crop_normalized = normalized_original
                    break
        if not crop_ok or not crop_normalized:
            continue

        # Target match (by refined_target_name + source_target_type)
        hit = False

        if target_mapping:
            for t in app.get("Target_Disease_Pest", []) or []:
                if not isinstance(t, dict):
                    continue
                name = str(t.get("name") or "").strip()
                if not name:
                    continue

                normalized_target = normalize_crop_key(name)
                if not normalized_target:
                    continue

                info = target_mapping.get((crop_normalized, normalized_target))
                if not info:
                    continue
                if not info.get("deployed", True):
                    continue
                if info.get("display_target_type_l", "").lower().strip() != target_type_l:
                    continue
                if info.get("refined_target_l", "").lower().strip() == target_l:
                    hit = True
                    break
        else:
            # Fallback to old lookup if CSV doesn't exist / couldn't be read
            for t in app.get("Target_Disease_Pest", []) or []:
                if not isinstance(t, dict):
                    continue
                name = str(t.get("name") or "").strip()
                if not name:
                    continue
                info = _TARGET_LOOKUP.lookup(name)
                if info.target_type != target_type:
                    continue
                simplified = (info.simplified or name).strip().lower()
                if simplified == target_l:
                    hit = True
                    break

        if hit:
            # Mark as seen BEFORE appending to ensure we never add duplicates
            # This prevents the same pesticide label from being added multiple times
            # even if it has multiple Application_Info entries with different crop variants
            seen_source_files.add(source_file_normalized)
            matched.append(p)

    total = len(matched)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify(
        {
            "pesticides": matched[start:end],
            "total": total,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "has_next": end < total,
                "total_pages": (total + per_page - 1) // per_page if total else 0,
            },
        }
    )


@bp.route("/api/favorites")
def api_favorites():
    """Get user's favorite pesticides."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Get user's favorites (RLS will automatically filter by user_id).
        # Prefer `source_file` (unique per JSON/PDF label), fall back to `epa_reg_no` for legacy rows.
        response = client.table("user_favorites").select("epa_reg_no,source_file").execute()
        rows = response.data or []
        epa_with_source = {
            (str(r.get("epa_reg_no") or "").strip())
            for r in rows
            if str(r.get("source_file") or "").strip()
        }

        favorites = []
        for fav in rows:
            source_file = (fav.get("source_file") or "").strip()
            epa = (fav.get("epa_reg_no") or "").strip()
            # If the user has at least one source-file-based favorite for this EPA,
            # ignore legacy EPA-only favorites to avoid duplicates/wrong label display.
            if not source_file and epa and epa in epa_with_source:
                continue
            pesticide = None
            if source_file:
                pesticide = _STORE.get_by_source_file(os.path.basename(source_file))
            if not pesticide and epa:
                pesticide = _STORE.get_by_epa(epa)
            if pesticide:
                favorites.append(pesticide)
        return jsonify({"favorites": favorites, "total": len(favorites)})
    except Exception as e:
        error_msg = str(e)
        # Check if token expired
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            # Try to refresh the token
            if refresh_access_token():
                # Retry the request with new token
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("user_favorites").select("epa_reg_no,source_file").execute()
                        rows = response.data or []
                        epa_with_source = {
                            (str(r.get("epa_reg_no") or "").strip())
                            for r in rows
                            if str(r.get("source_file") or "").strip()
                        }

                        favorites = []
                        for fav in rows:
                            source_file = (fav.get("source_file") or "").strip()
                            epa = (fav.get("epa_reg_no") or "").strip()
                            if not source_file and epa and epa in epa_with_source:
                                continue
                            pesticide = None
                            if source_file:
                                pesticide = _STORE.get_by_source_file(os.path.basename(source_file))
                            if not pesticide and epa:
                                pesticide = _STORE.get_by_epa(epa)
                            if pesticide:
                                favorites.append(pesticide)
                        return jsonify({"favorites": favorites, "total": len(favorites)})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@bp.route("/api/favorites/check-file/<path:source_file>")
def api_favorites_check_file(source_file: str):
    """Check if a specific label (by JSON filename) is favorited by the current user."""
    if not is_authenticated():
        return jsonify({"is_favorited": False})

    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"is_favorited": False})

    fname = os.path.basename(source_file or "").strip()
    if not fname:
        return jsonify({"is_favorited": False})

    try:
        response = client.table("user_favorites").select("id").eq("source_file", fname).execute()
        return jsonify({"is_favorited": len(response.data) > 0})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("user_favorites").select("id").eq("source_file", fname).execute()
                        return jsonify({"is_favorited": len(response.data) > 0})
                    except Exception:
                        return jsonify({"is_favorited": False})
        return jsonify({"is_favorited": False})


@bp.route("/api/favorites/check/<path:epa_reg_no>")
def api_favorites_check(epa_reg_no: str):
    """Check if a pesticide is favorited by the current user."""
    if not is_authenticated():
        return jsonify({"is_favorited": False})
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"is_favorited": False})
    
    try:
        # RLS will automatically filter by user_id
        response = client.table("user_favorites").select("id").eq("epa_reg_no", epa_reg_no).execute()
        return jsonify({"is_favorited": len(response.data) > 0})
    except Exception as e:
        error_msg = str(e)
        # Check if token expired
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("user_favorites").select("id").eq("epa_reg_no", epa_reg_no).execute()
                        return jsonify({"is_favorited": len(response.data) > 0})
                    except Exception:
                        return jsonify({"is_favorited": False})
        return jsonify({"is_favorited": False})


@bp.route("/api/favorites/add-file/<path:source_file>", methods=["POST"])
def api_favorites_add_file(source_file: str):
    """Add a specific label (by JSON filename) to user's favorites."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401

    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401

    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500

    fname = os.path.basename(source_file or "").strip()
    if not fname:
        return jsonify({"error": "Invalid source_file"}), 400

    pesticide = _STORE.get_by_source_file(fname)
    if not pesticide:
        return jsonify({"error": "Pesticide not found", "source_file": fname}), 404

    epa_reg_no = str(pesticide.get("epa_reg_no") or "").strip()

    try:
        client.table("user_favorites").insert(
            {
                "user_id": user_id,
                "epa_reg_no": epa_reg_no,
                "source_file": fname,
            }
        ).execute()
        return jsonify({"success": True, "message": "Added to favorites"})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_favorites").insert(
                            {
                                "user_id": user_id,
                                "epa_reg_no": epa_reg_no,
                                "source_file": fname,
                            }
                        ).execute()
                        return jsonify({"success": True, "message": "Added to favorites"})
                    except Exception as retry_error:
                        retry_msg = str(retry_error)
                        if "duplicate key" in retry_msg.lower() or "unique constraint" in retry_msg.lower():
                            return jsonify({"success": True, "message": "Already in favorites"})
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            return jsonify({"success": True, "message": "Already in favorites"})
        return jsonify({"error": error_msg}), 500


@bp.route("/api/favorites/add/<path:epa_reg_no>", methods=["POST"])
def api_favorites_add(epa_reg_no: str):
    """Add a pesticide to user's favorites."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    # Get pesticide name for the favorite record
    pesticide = _STORE.get_by_epa(epa_reg_no)
    if not pesticide:
        return jsonify({"error": "Pesticide not found"}), 404
    
    try:
        # Insert favorite (RLS will automatically set user_id from the token)
        # We still include user_id explicitly for clarity, but RLS will verify it matches
        client.table("user_favorites").insert({
            "user_id": user_id,
            "epa_reg_no": epa_reg_no,
        }).execute()
        
        return jsonify({"success": True, "message": "Added to favorites"})
    except Exception as e:
        error_msg = str(e)
        # Check if token expired
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_favorites").insert({
                            "user_id": user_id,
                            "epa_reg_no": epa_reg_no,
                        }).execute()
                        return jsonify({"success": True, "message": "Added to favorites"})
                    except Exception as retry_error:
                        retry_msg = str(retry_error)
                        if "duplicate key" in retry_msg.lower() or "unique constraint" in retry_msg.lower():
                            return jsonify({"success": True, "message": "Already in favorites"})
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            return jsonify({"success": True, "message": "Already in favorites"})
        return jsonify({"error": error_msg}), 500


@bp.route("/api/favorites/remove-file/<path:source_file>", methods=["POST"])
def api_favorites_remove_file(source_file: str):
    """Remove a specific label (by JSON filename) from user's favorites."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401

    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401

    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500

    fname = os.path.basename(source_file or "").strip()
    if not fname:
        return jsonify({"error": "Invalid source_file"}), 400

    try:
        client.table("user_favorites").delete().eq("source_file", fname).execute()
        return jsonify({"success": True, "message": "Removed from favorites"})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_favorites").delete().eq("source_file", fname).execute()
                        return jsonify({"success": True, "message": "Removed from favorites"})
                    except Exception:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@bp.route("/api/favorites/remove/<path:epa_reg_no>", methods=["POST"])
def api_favorites_remove(epa_reg_no: str):
    """Remove a pesticide from user's favorites."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Delete favorite (RLS will automatically filter by user_id)
        client.table("user_favorites").delete().eq("epa_reg_no", epa_reg_no).execute()
        
        return jsonify({"success": True, "message": "Removed from favorites"})
    except Exception as e:
        error_msg = str(e)
        # Check if token expired
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_favorites").delete().eq("epa_reg_no", epa_reg_no).execute()
                        return jsonify({"success": True, "message": "Removed from favorites"})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@bp.route("/api/user/preferences/tank-volume", methods=["GET"])
def api_get_tank_volume():
    """Get user's saved tank volume preference."""
    if not is_authenticated():
        return jsonify({"tank_volume": 500})  # Return default if not authenticated
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"tank_volume": 500})
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"tank_volume": 500})
    
    try:
        result = client.table("user_preferences").select("tank_volume").eq("user_id", user_id).execute()
        if result.data and len(result.data) > 0:
            tank_volume = result.data[0].get("tank_volume", 500)
            return jsonify({"tank_volume": float(tank_volume) if tank_volume else 500})
        return jsonify({"tank_volume": 500})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        result = client.table("user_preferences").select("tank_volume").eq("user_id", user_id).execute()
                        if result.data and len(result.data) > 0:
                            tank_volume = result.data[0].get("tank_volume", 500)
                            return jsonify({"tank_volume": float(tank_volume) if tank_volume else 500})
                        return jsonify({"tank_volume": 500})
                    except Exception:
                        return jsonify({"tank_volume": 500})
            return jsonify({"tank_volume": 500})
        return jsonify({"tank_volume": 500})


@bp.route("/api/user/preferences/tank-volume", methods=["PUT"])
def api_set_tank_volume():
    """Save user's tank volume preference."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    data = request.get_json()
    tank_volume = data.get("tank_volume")
    if tank_volume is None:
        return jsonify({"error": "tank_volume is required"}), 400
    
    try:
        tank_volume = float(tank_volume)
        if tank_volume < 10:
            return jsonify({"error": "Tank volume must be at least 10"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid tank_volume value"}), 400
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Try to update existing preference
        result = client.table("user_preferences").update({
            "tank_volume": tank_volume,
            "updated_at": "now()"
        }).eq("user_id", user_id).execute()
        
        # If no rows were updated, insert a new record
        if not result.data or len(result.data) == 0:
            client.table("user_preferences").insert({
                "user_id": user_id,
                "tank_volume": tank_volume
            }).execute()
        
        return jsonify({"success": True, "tank_volume": tank_volume})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        result = client.table("user_preferences").update({
                            "tank_volume": tank_volume,
                            "updated_at": "now()"
                        }).eq("user_id", user_id).execute()
                        
                        if not result.data or len(result.data) == 0:
                            client.table("user_preferences").insert({
                                "user_id": user_id,
                                "tank_volume": tank_volume
                            }).execute()
                        
                        return jsonify({"success": True, "tank_volume": tank_volume})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500

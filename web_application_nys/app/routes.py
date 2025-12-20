from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory

from .data import JsonPesticideStore, normalize_crop_key
from .target_lookup_csv import TargetLookupCsv

bp = Blueprint("routes", __name__)

# Simple global store (fine for dev + single-process; later can be refactored)
_STORE = JsonPesticideStore(
    cache_seconds=int(os.environ.get("NYS_CACHE_SECONDS", "0"))
)
_TARGET_LOOKUP = TargetLookupCsv()


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


@bp.route("/api/enums/crops")
def api_enums_crops():
    """Return unique crops for guided filtering."""
    return jsonify({"crops": _STORE.list_crops()})


@bp.route("/api/enums/target-types")
def api_enums_target_types():
    """Return target types for a given crop (derived from dataset + CSV lookup)."""
    crop = normalize_crop_key(request.args.get("crop", default="", type=str))

    if not crop:
        return jsonify({"target_types": list(_TARGET_LOOKUP.get_target_types())})

    types = set()
    for _, app in _STORE.iter_applications():
        # Crop match (case-insensitive)
        crop_ok = False
        for c in app.get("Target_Crop", []) or []:
            if isinstance(c, dict) and normalize_crop_key(str(c.get("name") or "")) == crop:
                crop_ok = True
                break
        if not crop_ok:
            continue

        for t in app.get("Target_Disease_Pest", []) or []:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name:
                continue
            types.add(_TARGET_LOOKUP.lookup(name).target_type or "Other")

    if not types:
        types = {"Other"}
    return jsonify({"crop": crop, "target_types": sorted(types)})


@bp.route("/api/enums/targets")
def api_enums_targets():
    """Return simplified targets (with counts) for crop + target type."""
    crop = normalize_crop_key(request.args.get("crop", default="", type=str))
    target_type = request.args.get("target_type", default="", type=str).strip()

    if not crop:
        return jsonify({"error": "crop is required"}), 400
    if not target_type:
        return jsonify({"error": "target_type is required"}), 400

    # simplified_target -> set(epa_reg_no)
    buckets: dict[str, set[str]] = {}

    for p, app in _STORE.iter_applications():
        # Crop match
        crop_ok = False
        for c in app.get("Target_Crop", []) or []:
            if isinstance(c, dict) and normalize_crop_key(str(c.get("name") or "")) == crop:
                crop_ok = True
                break
        if not crop_ok:
            continue

        epa = str(p.get("epa_reg_no") or "").strip()
        for t in app.get("Target_Disease_Pest", []) or []:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name:
                continue

            info = _TARGET_LOOKUP.lookup(name)
            if info.target_type != target_type:
                continue
            simplified = (info.simplified or name).strip()
            if not simplified:
                continue
            buckets.setdefault(simplified, set()).add(epa)

    targets = [{"name": k, "count": len(v)} for k, v in buckets.items()]
    targets.sort(key=lambda x: (-x["count"], x["name"].lower()))
    return jsonify({"crop": crop, "target_type": target_type, "targets": targets})


@bp.route("/api/filter")
def api_filter():
    """Filter pesticides by crop + target type + simplified target (guided filter)."""
    crop = normalize_crop_key(request.args.get("crop", default="", type=str))
    target_type = request.args.get("target_type", default="", type=str).strip()
    target = request.args.get("target", default="", type=str).strip()
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=50, type=int)

    if not crop or not target_type or not target:
        return jsonify({"error": "crop, target_type, and target are required"}), 400

    page = max(page, 1)
    per_page = min(max(per_page, 1), 500)

    matched: list[dict] = []
    seen_epa: set[str] = set()

    target_l = target.lower()

    for p, app in _STORE.iter_applications():
        epa = str(p.get("epa_reg_no") or "").strip()
        if epa in seen_epa:
            continue

        # Crop match
        crop_ok = False
        for c in app.get("Target_Crop", []) or []:
            if isinstance(c, dict) and normalize_crop_key(str(c.get("name") or "")) == crop:
                crop_ok = True
                break
        if not crop_ok:
            continue

        # Target match (by simplified name + type)
        hit = False
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
            matched.append(p)
            seen_epa.add(epa)

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

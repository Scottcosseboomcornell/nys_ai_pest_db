"""Application log routes for saving and retrieving application log entries."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .auth import get_authenticated_supabase_client, get_current_user_id, is_authenticated, refresh_access_token

app_log_bp = Blueprint("app_log", __name__, url_prefix="/api/application-log")


@app_log_bp.route("/blocks", methods=["GET"])
def get_farm_blocks():
    """Get all farm blocks for the current user."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Get all farm data with blocks
        response = client.table("user_farm_data").select("*").order("farm_name").order("block").execute()
        
        # Group by farm and return blocks
        farms = {}
        for row in response.data:
            farm_name = row.get("farm_name") or "Unnamed Farm"
            if farm_name not in farms:
                farms[farm_name] = {
                    "farm_name": farm_name,
                    "location": row.get("location"),
                    "blocks": [],
                }
            
            farms[farm_name]["blocks"].append({
                "id": str(row.get("id")),
                "block": row.get("block"),
                "crop": row.get("crop"),
                "variety": row.get("variety"),
                "acreage": float(row.get("acreage") or 0),
                "projected_harvest_date": row.get("projected_harvest_date"),
            })
        
        return jsonify({"farms": list(farms.values())})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("user_farm_data").select("*").order("farm_name").order("block").execute()
                        farms = {}
                        for row in response.data:
                            farm_name = row.get("farm_name") or "Unnamed Farm"
                            if farm_name not in farms:
                                farms[farm_name] = {
                                    "farm_name": farm_name,
                                    "location": row.get("location"),
                                    "blocks": [],
                                }
                            farms[farm_name]["blocks"].append({
                                "id": str(row.get("id")),
                                "block": row.get("block"),
                                "crop": row.get("crop"),
                                "variety": row.get("variety"),
                                "acreage": float(row.get("acreage") or 0),
                                "projected_harvest_date": row.get("projected_harvest_date"),
                            })
                        return jsonify({"farms": list(farms.values())})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@app_log_bp.route("/entries", methods=["GET"])
def get_application_logs():
    """Get all application log entries for the current user."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        response = client.table("application_logs").select("*").order("application_date", desc=True).execute()
        entries = response.data or []
        # Reverse to show most recent first
        entries.reverse()
        return jsonify({"entries": entries, "total": len(entries)})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("application_logs").select("*").order("application_date", desc=True).execute()
                        entries = response.data or []
                        entries.reverse()
                        return jsonify({"entries": entries, "total": len(entries)})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@app_log_bp.route("/entries", methods=["POST"])
def create_application_log():
    """Create a new application log entry."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    
    # Validate required fields
    epa_reg_no = (data.get("epa_reg_no") or "").strip()
    crop = (data.get("crop") or "").strip()
    target = (data.get("target") or "").strip()
    application_date = data.get("application_date")
    selected_rate = (data.get("selected_rate") or "").strip()
    
    if not epa_reg_no:
        return jsonify({"error": "EPA Reg No is required"}), 400
    if not crop:
        return jsonify({"error": "Crop is required"}), 400
    if not target:
        return jsonify({"error": "Target is required"}), 400
    if not application_date:
        return jsonify({"error": "Application date is required"}), 400
    if not selected_rate:
        return jsonify({"error": "Rate is required"}), 400
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Prepare the record
        record = {
            "user_id": user_id,
            "epa_reg_no": epa_reg_no,
            "pesticide_name": data.get("pesticide_name") or None,
            "crop": crop,
            "target": target,
            "selected_rate": selected_rate,
            "rei": data.get("rei") or None,
            "phi": data.get("phi") or None,
            "mode_of_action": data.get("mode_of_action") or None,
            "application_date": application_date,
            "acreage": data.get("acreage"),
            "gallons_per_acre": data.get("gallons_per_acre"),
            "total_product": data.get("total_product"),
            "total_water": data.get("total_water"),
            "farm_name": data.get("farm_name") or None,
            "blocks": data.get("blocks") or [],  # Array of block IDs
            "block": data.get("block") or None,  # Single block name (for backward compatibility)
            "variety": data.get("variety") or None,
            "notes": (data.get("notes") or "").strip() or None,
        }
        
        response = client.table("application_logs").insert(record).execute()
        
        if response.data:
            return jsonify({
                "success": True,
                "message": "Application log entry created successfully",
                "entry": response.data[0]
            })
        else:
            return jsonify({"error": "Failed to create entry"}), 500
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        record = {
                            "user_id": user_id,
                            "epa_reg_no": epa_reg_no,
                            "pesticide_name": data.get("pesticide_name") or None,
                            "crop": crop,
                            "target": target,
                            "selected_rate": selected_rate,
                            "rei": data.get("rei") or None,
                            "phi": data.get("phi") or None,
                            "mode_of_action": data.get("mode_of_action") or None,
                            "application_date": application_date,
                            "acreage": data.get("acreage"),
                            "gallons_per_acre": data.get("gallons_per_acre"),
                            "total_product": data.get("total_product"),
                            "total_water": data.get("total_water"),
                            "farm_name": data.get("farm_name") or None,
                            "blocks": data.get("blocks") or [],
                            "block": data.get("block") or None,
                            "variety": data.get("variety") or None,
                            "notes": (data.get("notes") or "").strip() or None,
                        }
                        response = client.table("application_logs").insert(record).execute()
                        if response.data:
                            return jsonify({
                                "success": True,
                                "message": "Application log entry created successfully",
                                "entry": response.data[0]
                            })
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@app_log_bp.route("/entries/<entry_id>", methods=["GET"])
def get_application_log_entry(entry_id: str):
    """Get a single application log entry by ID."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        response = client.table("application_logs").select("*").eq("id", entry_id).eq("user_id", user_id).execute()
        
        if not response.data:
            return jsonify({"error": "Entry not found"}), 404
        
        return jsonify({"entry": response.data[0]})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("application_logs").select("*").eq("id", entry_id).eq("user_id", user_id).execute()
                        if not response.data:
                            return jsonify({"error": "Entry not found"}), 404
                        return jsonify({"entry": response.data[0]})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@app_log_bp.route("/entries/<entry_id>", methods=["PUT"])
def update_application_log(entry_id: str):
    """Update an existing application log entry."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    
    # Validate required fields
    epa_reg_no = (data.get("epa_reg_no") or "").strip()
    crop = (data.get("crop") or "").strip()
    target = (data.get("target") or "").strip()
    application_date = data.get("application_date")
    selected_rate = (data.get("selected_rate") or "").strip()
    
    if not epa_reg_no:
        return jsonify({"error": "EPA Reg No is required"}), 400
    if not crop:
        return jsonify({"error": "Crop is required"}), 400
    if not target:
        return jsonify({"error": "Target is required"}), 400
    if not application_date:
        return jsonify({"error": "Application date is required"}), 400
    if not selected_rate:
        return jsonify({"error": "Rate is required"}), 400
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Prepare the update record
        update_record = {
            "epa_reg_no": epa_reg_no,
            "pesticide_name": data.get("pesticide_name") or None,
            "crop": crop,
            "target": target,
            "selected_rate": selected_rate,
            "rei": data.get("rei") or None,
            "phi": data.get("phi") or None,
            "mode_of_action": data.get("mode_of_action") or None,
            "application_date": application_date,
            "acreage": data.get("acreage"),
            "gallons_per_acre": data.get("gallons_per_acre"),
            "total_product": data.get("total_product"),
            "total_water": data.get("total_water"),
            "farm_name": data.get("farm_name") or None,
            "blocks": data.get("blocks") or [],
            "block": data.get("block") or None,
            "variety": data.get("variety") or None,
            "notes": (data.get("notes") or "").strip() or None,
        }
        
        response = client.table("application_logs").update(update_record).eq("id", entry_id).eq("user_id", user_id).execute()
        
        if response.data:
            return jsonify({
                "success": True,
                "message": "Application log entry updated successfully",
                "entry": response.data[0]
            })
        else:
            return jsonify({"error": "Entry not found or update failed"}), 404
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        update_record = {
                            "epa_reg_no": epa_reg_no,
                            "pesticide_name": data.get("pesticide_name") or None,
                            "crop": crop,
                            "target": target,
                            "selected_rate": selected_rate,
                            "rei": data.get("rei") or None,
                            "phi": data.get("phi") or None,
                            "mode_of_action": data.get("mode_of_action") or None,
                            "application_date": application_date,
                            "acreage": data.get("acreage"),
                            "gallons_per_acre": data.get("gallons_per_acre"),
                            "total_product": data.get("total_product"),
                            "total_water": data.get("total_water"),
                            "farm_name": data.get("farm_name") or None,
                            "blocks": data.get("blocks") or [],
                            "block": data.get("block") or None,
                            "variety": data.get("variety") or None,
                            "notes": (data.get("notes") or "").strip() or None,
                        }
                        response = client.table("application_logs").update(update_record).eq("id", entry_id).eq("user_id", user_id).execute()
                        if response.data:
                            return jsonify({
                                "success": True,
                                "message": "Application log entry updated successfully",
                                "entry": response.data[0]
                            })
                        return jsonify({"error": "Entry not found or update failed"}), 404
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@app_log_bp.route("/entries/<entry_id>/applied", methods=["PUT"])
def update_applied_status(entry_id: str):
    """Update the applied status and actual application date for an entry."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    
    applied = data.get("applied", False)
    actual_application_date = data.get("actual_application_date")
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        update_record = {
            "applied": applied,
        }
        
        # If applied is True and actual_application_date is provided, update both
        # If applied is False, clear actual_application_date
        if applied:
            if actual_application_date:
                update_record["actual_application_date"] = actual_application_date
                # Also update application_date to match actual_application_date
                update_record["application_date"] = actual_application_date
        else:
            update_record["actual_application_date"] = None
        
        response = client.table("application_logs").update(update_record).eq("id", entry_id).eq("user_id", user_id).execute()
        
        if response.data:
            return jsonify({
                "success": True,
                "message": "Applied status updated successfully",
                "entry": response.data[0]
            })
        else:
            return jsonify({"error": "Entry not found or update failed"}), 404
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        update_record = {
                            "applied": applied,
                        }
                        if applied:
                            if actual_application_date:
                                update_record["actual_application_date"] = actual_application_date
                                update_record["application_date"] = actual_application_date
                        else:
                            update_record["actual_application_date"] = None
                        response = client.table("application_logs").update(update_record).eq("id", entry_id).eq("user_id", user_id).execute()
                        if response.data:
                            return jsonify({
                                "success": True,
                                "message": "Applied status updated successfully",
                                "entry": response.data[0]
                            })
                        return jsonify({"error": "Entry not found or update failed"}), 404
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@app_log_bp.route("/entries/<entry_id>", methods=["DELETE"])
def delete_application_log(entry_id: str):
    """Delete an application log entry."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        response = client.table("application_logs").delete().eq("id", entry_id).eq("user_id", user_id).execute()
        
        if response.data:
            return jsonify({
                "success": True,
                "message": "Application log entry deleted successfully"
            })
        else:
            return jsonify({"error": "Entry not found"}), 404
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("application_logs").delete().eq("id", entry_id).eq("user_id", user_id).execute()
                        if response.data:
                            return jsonify({
                                "success": True,
                                "message": "Application log entry deleted successfully"
                            })
                        return jsonify({"error": "Entry not found"}), 404
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


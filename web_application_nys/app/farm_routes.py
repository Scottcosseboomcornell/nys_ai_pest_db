"""Farm management routes for user farm data."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .auth import get_authenticated_supabase_client, get_current_user_id, is_authenticated, refresh_access_token

farm_bp = Blueprint("farm", __name__, url_prefix="/api/farm")


@farm_bp.route("/farms", methods=["GET"])
def get_farms():
    """Get all farms for the current user."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Get all farm data, grouped by farm_name
        # Filter out rows without farm_name (old data) or group them separately
        response = client.table("user_farm_data").select("*").order("farm_name").order("block").execute()
        
        # Group by farm_name
        farms_dict = {}
        unnamed_blocks = []
        
        for row in response.data:
            farm_name = row.get("farm_name")
            if not farm_name or not farm_name.strip():
                # Handle old data without farm_name
                unnamed_blocks.append({
                    "id": row.get("id"),
                    "block": row.get("block"),
                    "crop": row.get("crop"),
                    "variety": row.get("variety"),
                    "acreage": float(row.get("acreage") or 0),
                    "projected_harvest_date": row.get("projected_harvest_date"),
                    "notes": row.get("notes"),
                })
                continue
            
            farm_name = farm_name.strip()
            if farm_name not in farms_dict:
                farms_dict[farm_name] = {
                    "farm_name": farm_name,
                    "location": row.get("location"),
                    "blocks": [],
                }
            
            # Add block data
            farms_dict[farm_name]["blocks"].append({
                "id": row.get("id"),
                "block": row.get("block"),
                "crop": row.get("crop"),
                "variety": row.get("variety"),
                "acreage": float(row.get("acreage") or 0),
                "projected_harvest_date": row.get("projected_harvest_date"),
                "notes": row.get("notes"),
            })
        
        # Add unnamed blocks as a separate "Unnamed Farm" if any exist
        if unnamed_blocks:
            farms_dict["Unnamed Farm"] = {
                "farm_name": "Unnamed Farm",
                "location": None,
                "blocks": unnamed_blocks,
            }
        
        farms = list(farms_dict.values())
        return jsonify({"farms": farms, "total": len(farms)})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        response = client.table("user_farm_data").select("*").order("farm_name").order("block").execute()
                        farms_dict = {}
                        for row in response.data:
                            farm_name = row.get("farm_name") or "Unnamed Farm"
                            if farm_name not in farms_dict:
                                farms_dict[farm_name] = {
                                    "farm_name": farm_name,
                                    "location": row.get("location"),
                                    "blocks": [],
                                }
                            farms_dict[farm_name]["blocks"].append({
                                "id": row.get("id"),
                                "block": row.get("block"),
                                "crop": row.get("crop"),
                                "variety": row.get("variety"),
                                "acreage": float(row.get("acreage") or 0),
                                "projected_harvest_date": row.get("projected_harvest_date"),
                                "notes": row.get("notes"),
                            })
                        farms = list(farms_dict.values())
                        return jsonify({"farms": farms, "total": len(farms)})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@farm_bp.route("/farms", methods=["POST"])
def create_farm():
    """Create a new farm with blocks."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    
    farm_name = (data.get("farm_name") or "").strip()
    if not farm_name:
        return jsonify({"error": "Farm name is required"}), 400
    
    location = (data.get("location") or "").strip() or None
    blocks = data.get("blocks", [])
    
    if not blocks or len(blocks) == 0:
        return jsonify({"error": "At least one block is required"}), 400
    
    # Validate blocks
    for i, block in enumerate(blocks):
        block_name = (block.get("block") or "").strip()
        crop = (block.get("crop") or "").strip()
        acreage = block.get("acreage")
        
        if not block_name:
            return jsonify({"error": f"Block {i+1}: Block name is required"}), 400
        if not crop:
            return jsonify({"error": f"Block {i+1}: Crop is required"}), 400
        if acreage is None or acreage <= 0:
            return jsonify({"error": f"Block {i+1}: Acreage must be greater than 0"}), 400
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Insert all blocks
        records = []
        for block in blocks:
            records.append({
                "user_id": user_id,
                "farm_name": farm_name,
                "location": location,
                "block": block.get("block").strip(),
                "crop": block.get("crop").strip(),
                "variety": (block.get("variety") or "").strip() or None,
                "acreage": float(block.get("acreage")),
                "projected_harvest_date": block.get("projected_harvest_date") or None,
                "notes": (block.get("notes") or "").strip() or None,
            })
        
        # Insert all records
        response = client.table("user_farm_data").insert(records).execute()
        
        return jsonify({
            "success": True,
            "message": f"Farm '{farm_name}' created with {len(blocks)} block(s)",
            "farm": {
                "farm_name": farm_name,
                "location": location,
                "blocks": response.data,
            }
        })
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        records = []
                        for block in blocks:
                            records.append({
                                "user_id": user_id,
                                "farm_name": farm_name,
                                "location": location,
                                "block": block.get("block").strip(),
                                "crop": block.get("crop").strip(),
                                "variety": (block.get("variety") or "").strip() or None,
                                "acreage": float(block.get("acreage")),
                                "projected_harvest_date": block.get("projected_harvest_date") or None,
                                "notes": (block.get("notes") or "").strip() or None,
                            })
                        response = client.table("user_farm_data").insert(records).execute()
                        return jsonify({
                            "success": True,
                            "message": f"Farm '{farm_name}' created with {len(blocks)} block(s)",
                            "farm": {
                                "farm_name": farm_name,
                                "location": location,
                                "blocks": response.data,
                            }
                        })
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            return jsonify({"error": "A block with this crop/variety already exists for this farm"}), 400
        
        return jsonify({"error": error_msg}), 500


@farm_bp.route("/farms/<farm_name>", methods=["PUT"])
def update_farm(farm_name: str):
    """Update an existing farm with blocks."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request data"}), 400
    
    new_farm_name = (data.get("farm_name") or "").strip()
    if not new_farm_name:
        return jsonify({"error": "Farm name is required"}), 400
    
    location = (data.get("location") or "").strip() or None
    blocks = data.get("blocks", [])
    
    if not blocks or len(blocks) == 0:
        return jsonify({"error": "At least one block is required"}), 400
    
    # Validate blocks
    for i, block in enumerate(blocks):
        block_name = (block.get("block") or "").strip()
        crop = (block.get("crop") or "").strip()
        acreage = block.get("acreage")
        
        if not block_name:
            return jsonify({"error": f"Block {i+1}: Block name is required"}), 400
        if not crop:
            return jsonify({"error": f"Block {i+1}: Crop is required"}), 400
        if acreage is None or acreage <= 0:
            return jsonify({"error": f"Block {i+1}: Acreage must be greater than 0"}), 400
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Delete all existing blocks for this farm
        client.table("user_farm_data").delete().eq("user_id", user_id).eq("farm_name", farm_name).execute()
        
        # Insert all blocks with new farm name
        records = []
        for block in blocks:
            records.append({
                "user_id": user_id,
                "farm_name": new_farm_name,
                "location": location,
                "block": block.get("block").strip(),
                "crop": block.get("crop").strip(),
                "variety": (block.get("variety") or "").strip() or None,
                "acreage": float(block.get("acreage")),
                "projected_harvest_date": block.get("projected_harvest_date") or None,
                "notes": (block.get("notes") or "").strip() or None,
            })
        
        # Insert all records
        response = client.table("user_farm_data").insert(records).execute()
        
        return jsonify({
            "success": True,
            "message": f"Farm '{new_farm_name}' updated with {len(blocks)} block(s)",
            "farm": {
                "farm_name": new_farm_name,
                "location": location,
                "blocks": response.data,
            }
        })
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_farm_data").delete().eq("user_id", user_id).eq("farm_name", farm_name).execute()
                        records = []
                        for block in blocks:
                            records.append({
                                "user_id": user_id,
                                "farm_name": new_farm_name,
                                "location": location,
                                "block": block.get("block").strip(),
                                "crop": block.get("crop").strip(),
                                "variety": (block.get("variety") or "").strip() or None,
                                "acreage": float(block.get("acreage")),
                                "projected_harvest_date": block.get("projected_harvest_date") or None,
                                "notes": (block.get("notes") or "").strip() or None,
                            })
                        response = client.table("user_farm_data").insert(records).execute()
                        return jsonify({
                            "success": True,
                            "message": f"Farm '{new_farm_name}' updated with {len(blocks)} block(s)",
                            "farm": {
                                "farm_name": new_farm_name,
                                "location": location,
                                "blocks": response.data,
                            }
                        })
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            return jsonify({"error": "A block with this crop/variety already exists for this farm"}), 400
        
        return jsonify({"error": error_msg}), 500


@farm_bp.route("/farms/<farm_id>", methods=["DELETE"])
def delete_farm(farm_id: str):
    """Delete a farm (all blocks for a farm_name)."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Delete all blocks for this farm_name (farm_id is actually farm_name)
        client.table("user_farm_data").delete().eq("user_id", user_id).eq("farm_name", farm_id).execute()
        return jsonify({"success": True, "message": f"Farm '{farm_id}' deleted"})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_farm_data").delete().eq("user_id", user_id).eq("farm_name", farm_id).execute()
                        return jsonify({"success": True, "message": f"Farm '{farm_id}' deleted"})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


@farm_bp.route("/blocks/<block_id>", methods=["DELETE"])
def delete_block(block_id: str):
    """Delete a specific block."""
    if not is_authenticated():
        return jsonify({"error": "Authentication required"}), 401
    
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "User not found"}), 401
    
    client = get_authenticated_supabase_client()
    if not client:
        return jsonify({"error": "Database not configured or not authenticated"}), 500
    
    try:
        # Delete the block (RLS will ensure user owns it)
        client.table("user_farm_data").delete().eq("id", block_id).execute()
        return jsonify({"success": True, "message": "Block deleted"})
    except Exception as e:
        error_msg = str(e)
        if "JWT expired" in error_msg or "PGRST303" in error_msg:
            if refresh_access_token():
                client = get_authenticated_supabase_client()
                if client:
                    try:
                        client.table("user_farm_data").delete().eq("id", block_id).execute()
                        return jsonify({"success": True, "message": "Block deleted"})
                    except Exception as retry_error:
                        return jsonify({"error": "Session expired. Please log in again."}), 401
            return jsonify({"error": "Session expired. Please log in again."}), 401
        return jsonify({"error": error_msg}), 500


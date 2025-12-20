#!/bin/bash

# Prepare altered_json.tar.gz for deployment
# This script creates a compressed archive of the altered_json folder for easy transfer to AWS

echo "📦 Preparing altered_json.tar.gz for deployment..."

# ─── STEP 1: VERIFY INPUT DATA EXISTS ───────────────────────────────────
# Check if the altered_json folder exists (this contains the enhanced JSON files)
if [ ! -d "../pipeline_critical_docs/altered_json" ]; then
    echo "❌ Error: ../pipeline_critical_docs/altered_json folder not found"
    echo "Please run post-extraction_alter_json.py first to create the altered JSON files"
    exit 1
fi

# ─── STEP 2: CLEAN UP OLD ARCHIVE ───────────────────────────────────────
# Remove existing tar.gz if it exists to avoid confusion
if [ -f "altered_json.tar.gz" ]; then
    echo "🗑️ Removing existing altered_json.tar.gz..."
    rm altered_json.tar.gz
fi

# ─── STEP 3: CREATE COMPRESSED ARCHIVE ──────────────────────────────────
# Create the tar.gz file (compressed archive) for easy transfer to AWS
echo "📦 Creating altered_json.tar.gz..."
cd ../pipeline_critical_docs  # Move to the directory containing the data
tar -czf ../web_application/altered_json.tar.gz altered_json/  # Create compressed archive
cd ../web_application  # Return to web application directory

# ─── STEP 4: VERIFY ARCHIVE CREATION ───────────────────────────────────
# Check if the file was created successfully and show statistics
if [ -f "altered_json.tar.gz" ]; then
    file_size=$(du -h altered_json.tar.gz | cut -f1)  # Get file size in human-readable format
    echo "✅ Successfully created altered_json.tar.gz (${file_size})"
    echo "📊 File contains $(tar -tzf altered_json.tar.gz | wc -l) files"  # Count files in archive
else
    echo "❌ Error: Failed to create altered_json.tar.gz"
    exit 1
fi

echo ""
echo "🚀 Ready for deployment! Run deploy_complete_update.sh to deploy to AWS" 
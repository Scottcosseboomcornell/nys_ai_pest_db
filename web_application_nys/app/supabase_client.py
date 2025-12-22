"""Supabase client initialization and utilities.

This module provides a singleton Supabase client instance that can be used
throughout the application for database operations and authentication.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from supabase import create_client, Client
except ImportError:
    # Supabase not installed or optional
    Client = None  # type: ignore
    create_client = None  # type: ignore


def get_supabase_client(access_token: Optional[str] = None) -> Optional[Client]:
    """Get or create the Supabase client instance.
    
    Args:
        access_token: Optional user access token for authenticated requests.
                     If provided, the client will use this token for RLS policies.
    
    Returns:
        Supabase Client instance if configured, None otherwise.
    """
    if create_client is None:
        return None
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        return None
    
    # Create client
    client = create_client(url, key)
    
    # If access token is provided, set it for authenticated requests
    # This allows RLS policies to work correctly
    if access_token:
        # Use postgrest.auth() to set the access token for all database requests
        client.postgrest.auth(access_token)
    
    return client


def is_supabase_configured() -> bool:
    """Check if Supabase is properly configured.
    
    Returns:
        True if Supabase URL and key are set, False otherwise.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return bool(url and key)


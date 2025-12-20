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


def get_supabase_client() -> Optional[Client]:
    """Get or create the Supabase client instance.
    
    Returns:
        Supabase Client instance if configured, None otherwise.
    """
    if create_client is None:
        return None
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        return None
    
    # Create client singleton (in production, you might want to cache this)
    return create_client(url, key)


def is_supabase_configured() -> bool:
    """Check if Supabase is properly configured.
    
    Returns:
        True if Supabase URL and key are set, False otherwise.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    return bool(url and key)

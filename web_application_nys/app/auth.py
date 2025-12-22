"""Authentication utilities for Supabase Auth."""

from __future__ import annotations

import os
from typing import Optional

from flask import session
from supabase import Client

from .supabase_client import get_supabase_client


def get_current_user_id() -> Optional[str]:
    """Get the current authenticated user's ID from session.
    
    Returns:
        User ID (UUID string) if authenticated, None otherwise.
    """
    return session.get("user_id")


def get_current_user_email() -> Optional[str]:
    """Get the current authenticated user's email from session.
    
    Returns:
        Email address if authenticated, None otherwise.
    """
    return session.get("user_email")


def get_current_user_access_token() -> Optional[str]:
    """Get the current authenticated user's access token from session.
    
    Returns:
        Access token string if authenticated, None otherwise.
    """
    return session.get("access_token")


def get_current_user_refresh_token() -> Optional[str]:
    """Get the current authenticated user's refresh token from session.
    
    Returns:
        Refresh token string if authenticated, None otherwise.
    """
    return session.get("refresh_token")


def refresh_access_token() -> bool:
    """Refresh the user's access token using the refresh token.
    
    Returns:
        True if token was refreshed successfully, False otherwise.
    """
    refresh_token = get_current_user_refresh_token()
    access_token = get_current_user_access_token()
    
    if not refresh_token:
        return False
    
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        # Use set_session - it will automatically refresh if the access token is expired
        # Pass both tokens, and Supabase will handle the refresh
        if access_token and refresh_token:
            response = client.auth.set_session(access_token, refresh_token)
        else:
            # If no access token, try refresh_session with refresh token
            response = client.auth.refresh_session(refresh_token)
        
        if response and hasattr(response, 'session') and response.session:
            # Update session with new tokens
            session["access_token"] = response.session.access_token
            session["refresh_token"] = response.session.refresh_token
            return True
    except Exception as e:
        # Refresh failed - user needs to log in again
        # Clear session so user knows they need to re-authenticate
        session.clear()
        return False
    
    return False


def is_authenticated() -> bool:
    """Check if user is currently authenticated.
    
    Returns:
        True if user is authenticated, False otherwise.
    """
    return get_current_user_id() is not None


def get_authenticated_supabase_client() -> Optional[Client]:
    """Get Supabase client with user's access token for authenticated database operations.
    
    This client will respect Row Level Security (RLS) policies.
    Automatically refreshes the token if it's expired.
    
    Returns:
        Supabase Client instance with user token if authenticated, None otherwise.
    """
    access_token = get_current_user_access_token()
    if not access_token:
        return None
    return get_supabase_client(access_token=access_token)


def get_auth_client() -> Optional[Client]:
    """Get Supabase client for authentication operations.
    
    Returns:
        Supabase Client instance if configured, None otherwise.
    """
    return get_supabase_client()


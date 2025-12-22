"""Authentication routes for signup, login, logout, and email verification."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .auth import get_auth_client, get_current_user_email, is_authenticated
from .supabase_client import get_supabase_client

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if is_authenticated():
        return redirect(url_for("routes.nys_pesticide_database"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("auth/login.html")
        
        client = get_supabase_client()
        if not client:
            flash("Authentication service is not configured.", "error")
            return render_template("auth/login.html")
        
        try:
            response = client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
            
            if response.user:
                # Store user info in session
                session["user_id"] = response.user.id
                session["user_email"] = response.user.email
                session["access_token"] = response.session.access_token
                session["refresh_token"] = response.session.refresh_token
                
                flash("Successfully logged in!", "success")
                next_url = request.args.get("next") or url_for("routes.nys_pesticide_database")
                return redirect(next_url)
            else:
                flash("Login failed. Please check your credentials.", "error")
        except Exception as e:
            error_msg = str(e)
            if "Invalid login credentials" in error_msg or "Email not confirmed" in error_msg:
                flash("Invalid email or password, or email not verified.", "error")
            else:
                flash(f"Login failed: {error_msg}", "error")
    
    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user signup."""
    if is_authenticated():
        return redirect(url_for("routes.nys_pesticide_database"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        
        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("auth/signup.html")
        
        if password != password_confirm:
            flash("Passwords do not match.", "error")
            return render_template("auth/signup.html")
        
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("auth/signup.html")
        
        client = get_supabase_client()
        if not client:
            flash("Authentication service is not configured.", "error")
            return render_template("auth/signup.html")
        
        try:
            # Build the redirect URL for email verification
            redirect_url = request.url_root.rstrip("/") + url_for("auth.verify_email")
            
            response = client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": redirect_url,
                }
            })
            
            if response.user:
                # Check if email was actually sent (Supabase may create user but not send email due to rate limits)
                # Note: Supabase free tier has a limit of 2 emails per hour
                flash(
                    "Account created! Please check your email to verify your account before logging in. "
                    "If you don't receive an email within a few minutes, you may have hit the rate limit (2 emails/hour). "
                    "You can use the 'Resend Verification' link on the login page.",
                    "success"
                )
                return redirect(url_for("auth.login"))
            else:
                flash("Signup failed. Please try again.", "error")
        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower():
                flash("An account with this email already exists. Please log in instead.", "error")
            elif "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                flash(
                    "Email rate limit reached (2 emails/hour on free tier). "
                    "Account was created but verification email was not sent. "
                    "Please wait an hour or use 'Resend Verification' on the login page.",
                    "error"
                )
            else:
                flash(f"Signup failed: {error_msg}", "error")
    
    return render_template("auth/signup.html")


@auth_bp.route("/logout")
def logout():
    """Handle user logout."""
    # Clear session
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("routes.nys_pesticide_database"))


@auth_bp.route("/verify-email")
def verify_email():
    """Handle email verification callback from Supabase."""
    token = request.args.get("token")
    token_hash = request.args.get("token_hash")
    type_param = request.args.get("type")
    
    client = get_supabase_client()
    if not client:
        flash("Verification service is not configured.", "error")
        return redirect(url_for("routes.nys_pesticide_database"))
    
    # Supabase sends token_hash in the email verification link
    if token_hash and type_param:
        try:
            # Verify the email using token_hash
            response = client.auth.verify_otp({
                "token_hash": token_hash,
                "type": type_param,
            })
            
            if response.user:
                flash("Email verified successfully! You can now log in.", "success")
                return redirect(url_for("auth.login"))
            else:
                flash("Email verification failed. Please try again.", "error")
        except Exception as e:
            error_msg = str(e)
            if "already verified" in error_msg.lower():
                flash("Email is already verified. You can log in now.", "success")
                return redirect(url_for("auth.login"))
            flash(f"Verification failed: {error_msg}", "error")
    elif token:
        # Fallback for token-based verification (older format)
        try:
            response = client.auth.verify_otp({
                "token": token,
                "type": type_param or "signup",
            })
            
            if response.user:
                flash("Email verified successfully! You can now log in.", "success")
                return redirect(url_for("auth.login"))
        except Exception as e:
            flash(f"Verification failed: {str(e)}", "error")
    else:
        flash("Invalid verification link. Please check your email for the correct link.", "error")
    
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    """Resend email verification."""
    email = request.form.get("email", "").strip()
    
    if not email:
        flash("Email is required.", "error")
        return redirect(url_for("auth.login"))
    
    client = get_supabase_client()
    if not client:
        flash("Verification service is not configured.", "error")
        return redirect(url_for("auth.login"))
    
    try:
        response = client.auth.resend({
            "type": "signup",
            "email": email,
            "options": {
                "email_redirect_to": request.url_root.rstrip("/") + url_for("auth.verify_email"),
            }
        })
        
        # Supabase may return success even if email wasn't sent due to rate limits
        # The Python client doesn't always raise exceptions for rate limits
        # Always warn users about the rate limit
        flash(
            "Verification email requested! ⚠️ Note: Free tier is limited to 2 emails/hour. "
            "If you don't receive it, you've likely hit the rate limit. "
            "You can manually verify the account in Supabase Dashboard: "
            "Authentication → Users → [Your Email] → Confirm Email button.",
            "success"
        )
    except Exception as e:
        error_msg = str(e)
        error_lower = error_msg.lower()
        error_repr = repr(e)
        
        # Check for HTTP 429 or rate limit errors in exception message or type
        if any(phrase in error_lower or phrase in error_repr.lower() for phrase in [
            "rate limit", "too many requests", "429", "email rate limit",
            "exceeded", "quota", "limit exceeded", "over_request_rate_limit",
            "rate_limit"
        ]):
            flash(
                "❌ Email rate limit reached (2 emails/hour on free tier). "
                "Please wait an hour, or manually verify the account in Supabase Dashboard: "
                "Authentication → Users → [Your Email] → Confirm Email button.",
                "error"
            )
        else:
            # Log the full error for debugging
            import logging
            logging.error(f"Resend verification error: {error_msg} (repr: {error_repr})")
            flash(
                f"⚠️ Verification email requested, but there may have been an issue: {error_msg}. "
                "If you've sent 2+ emails in the last hour, you've hit the rate limit. "
                "You can manually verify the account in Supabase Dashboard: "
                "Authentication → Users → [Your Email] → Confirm Email button.",
                "error"
            )
    
    return redirect(url_for("auth.login"))


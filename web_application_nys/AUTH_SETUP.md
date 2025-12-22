# Authentication Setup Guide

Authentication has been set up using Supabase Auth with email verification.

## What's Been Set Up

✅ **Authentication Routes**
- `/auth/login` - User login page
- `/auth/signup` - User signup page  
- `/auth/logout` - User logout
- `/auth/verify-email` - Email verification callback
- `/auth/resend-verification` - Resend verification email

✅ **UI Components**
- Auth buttons in top right corner of all pages
- Shows user email when logged in
- Login/Sign Up buttons when not authenticated

✅ **Session Management**
- Flask sessions store user ID and email
- User context available in all templates

## Required Configuration

### 1. Add FLASK_SECRET_KEY to .env

Add this line to your `.env` file (generate a new one for production):

```
FLASK_SECRET_KEY=758c093e59fcf6ca5fac96624b627c60b18406488d73902cb1c336a79b29b201
```

**Important:** Generate a new secret key for production:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Configure Supabase Email Redirect URLs

In your Supabase dashboard:

1. Go to **Authentication** → **URL Configuration**
2. Add your redirect URLs to **Redirect URLs**:
   - For local development: `http://127.0.0.1:5051/auth/verify-email`
   - For production: `https://yourdomain.com/auth/verify-email`

3. Set **Site URL** to your application URL:
   - Local: `http://127.0.0.1:5051`
   - Production: `https://yourdomain.com`

### 3. Configure Email Templates (Optional)

Supabase uses default email templates. You can customize them in:
**Authentication** → **Email Templates**

The signup confirmation email will include a link that redirects to:
`/auth/verify-email?token_hash=...&type=signup`

## How It Works

1. **Sign Up Flow:**
   - User fills out signup form
   - Account is created in Supabase
   - Verification email is sent automatically
   - User clicks link in email
   - Redirects to `/auth/verify-email` which verifies the account
   - User can then log in

2. **Login Flow:**
   - User enters email and password
   - Supabase authenticates
   - Session is created with user info
   - User is redirected to the main page

3. **Logout Flow:**
   - User clicks logout
   - Session is cleared
   - User is redirected to main page

## Testing

1. Start your Flask server:
   ```bash
   python run_dev.py
   ```

2. Visit `http://127.0.0.1:5051`

3. Click "Sign Up" in the top right

4. Fill out the form and submit

5. Check your email for the verification link

6. Click the verification link

7. Log in with your credentials

## Troubleshooting

### "Email not verified" error
- Make sure you've clicked the verification link in your email
- Check spam folder
- Use "Resend verification" on the login page

### Redirect URL not working
- Make sure the redirect URL is added in Supabase dashboard
- Check that the URL matches exactly (including http/https and port)

### Session not persisting
- Make sure `FLASK_SECRET_KEY` is set in `.env`
- Check browser cookies are enabled
- Clear browser cache and try again

## Security Notes

- Sessions are stored server-side using Flask's session
- Passwords are hashed by Supabase (never stored in plain text)
- Row Level Security (RLS) ensures users can only access their own data
- Email verification prevents unauthorized account creation
- Change `FLASK_SECRET_KEY` in production!

## Next Steps

After authentication is working, you can:
1. Protect routes that require login (e.g., My Farm, Application Log)
2. Use `is_authenticated()` and `get_current_user_id()` in your routes
3. Build user-specific features that use the authenticated user's ID


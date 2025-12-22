# Email Rate Limiting Issue

## Problem

Supabase's **free tier has a rate limit of 2 emails per hour** for all authentication emails (signup confirmations, password resets, etc.). This is a very low limit that can cause issues during development and testing.

## Symptoms

- First signup works and receives email
- Subsequent signups within the same hour don't receive emails
- Accounts are created in Supabase but show "waiting for verification"
- No emails appear in spam folder

## Solutions

### Option 1: Wait for Rate Limit Reset (Temporary)

The rate limit resets every hour. You can:
- Wait 1 hour between signup attempts
- Use the "Resend Verification" link on the login page (but this also counts toward the limit)

### Option 2: Set Up Custom SMTP (Recommended for Production)

By configuring a custom SMTP provider, you can bypass Supabase's free tier email limits.

#### Steps:

1. **Choose an SMTP Provider** (examples):
   - **SendGrid** (free tier: 100 emails/day)
   - **Mailgun** (free tier: 5,000 emails/month)
   - **Amazon SES** (very affordable)
   - **Postmark** (free tier: 100 emails/month)

2. **Get SMTP Credentials** from your chosen provider

3. **Configure in Supabase Dashboard**:
   - Go to: **Authentication** → **Email Templates** → **SMTP Settings**
   - Enable "Use custom SMTP server"
   - Enter your SMTP credentials:
     - Host (e.g., `smtp.sendgrid.net`)
     - Port (usually 587 for TLS)
     - Username/API Key
     - Password
     - Sender email and name

4. **Update Rate Limits** (optional):
   - Go to: **Authentication** → **Rate Limits**
   - Increase `email_sent` limit (if using custom SMTP)

### Option 3: Manual Email Verification (Development Only)

For development/testing, you can manually verify emails in Supabase Dashboard:

1. Go to **Authentication** → **Users**
2. Find the user account
3. Click on the user
4. Click **"Confirm Email"** button

**Note**: This is only for development. In production, users must verify via email.

### Option 4: Disable Email Confirmation (Development Only)

**⚠️ WARNING: Only for development/testing, NOT for production!**

You can temporarily disable email confirmation in Supabase Dashboard:

1. Go to: **Authentication** → **Email Auth**
2. Toggle OFF **"Enable email confirmations"**
3. Users can now log in immediately after signup without verification

**Remember to re-enable this for production!**

## Current Configuration

Your current rate limit (from `supabase/config.toml`):
```toml
[auth.rate_limit]
email_sent = 2  # Only 2 emails per hour!
```

## Monitoring

You can check email sending status in Supabase Dashboard:
- **Authentication** → **Logs** → Filter by "Email" events

## References

- [Supabase Email Rate Limits](https://supabase.com/docs/guides/deployment/going-into-prod)
- [Setting Up Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp)
- [Troubleshooting Auth Emails](https://supabase.com/docs/guides/troubleshooting/not-receiving-auth-emails-from-the-supabase-project-OFSNzw)


# Supabase Setup Guide

This guide will walk you through setting up Supabase for user authentication and data storage in the NYSPAD application.

## Step 1: Create a Supabase Account and Project

1. Go to [https://supabase.com](https://supabase.com)
2. Click "Start your project" or "Sign up" if you don't have an account
3. Sign up with GitHub, Google, or email
4. Once logged in, click "New Project"
5. Fill in the project details:
   - **Name**: Choose a name (e.g., "nyspad")
   - **Database Password**: Create a strong password (save this securely!)
   - **Region**: Choose the region closest to your users
   - **Pricing Plan**: Select "Free" for development (or choose a paid plan for production)
6. Click "Create new project" and wait for it to initialize (takes 1-2 minutes)

## Step 2: Get Your API Credentials

1. In your Supabase project dashboard, click on the **Settings** icon (gear icon) in the left sidebar
2. Click on **API** in the settings menu
3. You'll see two important values:
   - **Project URL**: This is your `SUPABASE_URL`
   - **anon/public key**: This is your `SUPABASE_ANON_KEY`
4. Copy both values (you'll need them in Step 4)

## Step 3: Create Database Tables

You'll need to create tables for:
- User farm data (crops, blocks, varieties, acreage, harvest dates)
- Application logs
- User favorites (starred pesticides)

### Option A: Using Supabase SQL Editor (Recommended)

1. In your Supabase dashboard, click on **SQL Editor** in the left sidebar
2. Click **New query**
3. Copy and paste the following SQL to create the tables:

```sql
-- Enable Row Level Security (RLS) for user data
-- This ensures users can only access their own data

-- User Farm Data Table
CREATE TABLE IF NOT EXISTS user_farm_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    crop TEXT NOT NULL,
    block TEXT,
    variety TEXT,
    acreage DECIMAL(10, 2),
    projected_harvest_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, crop, block, variety)
);

-- Application Log Table
CREATE TABLE IF NOT EXISTS application_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    epa_reg_no TEXT NOT NULL,
    pesticide_name TEXT NOT NULL,
    crop TEXT NOT NULL,
    block TEXT,
    variety TEXT,
    application_date TIMESTAMP WITH TIME ZONE NOT NULL,
    selected_rate TEXT,
    product_amount DECIMAL(10, 2),
    water_amount DECIMAL(10, 2),
    rei TEXT,
    phi TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User Favorites Table
CREATE TABLE IF NOT EXISTS user_favorites (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    epa_reg_no TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, epa_reg_no)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_user_farm_data_user_id ON user_farm_data(user_id);
CREATE INDEX IF NOT EXISTS idx_application_logs_user_id ON application_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_application_logs_date ON application_logs(application_date);
CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id ON user_favorites(user_id);

-- Enable Row Level Security
ALTER TABLE user_farm_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_favorites ENABLE ROW LEVEL SECURITY;

-- Create policies so users can only access their own data
CREATE POLICY "Users can view their own farm data"
    ON user_farm_data FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own farm data"
    ON user_farm_data FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own farm data"
    ON user_farm_data FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own farm data"
    ON user_farm_data FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own application logs"
    ON application_logs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own application logs"
    ON application_logs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own application logs"
    ON application_logs FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own application logs"
    ON application_logs FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own favorites"
    ON user_favorites FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own favorites"
    ON user_favorites FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own favorites"
    ON user_favorites FOR DELETE
    USING (auth.uid() = user_id);
```

4. Click **Run** (or press Ctrl+Enter / Cmd+Enter)
5. You should see "Success. No rows returned" if everything worked

### Option B: Using Supabase Table Editor (Visual)

1. Go to **Table Editor** in the left sidebar
2. Click **New table** for each table
3. Manually create columns matching the schema above
4. Enable RLS and create policies (this is more complex, so SQL Editor is recommended)

## Step 4: Configure Environment Variables

1. Copy `env.example` to `.env` in the `web_application_nys` directory:
   ```bash
   cd web_application_nys
   cp env.example .env
   ```

2. Open `.env` in a text editor

3. Add your Supabase credentials:
   ```
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_ANON_KEY=your-anon-key-here
   ```
   Replace `your-project-id` and `your-anon-key-here` with the values from Step 2

4. Save the file

## Step 5: Install Python Dependencies

Make sure you have the Supabase client library installed:

```bash
cd web_application_nys
source .venv/bin/activate  # or activate your virtual environment
pip install -r requirements.txt
```

This will install `supabase>=2.0.0` along with other dependencies.

## Step 6: Verify Setup

1. Start your Flask development server:
   ```bash
   python run_dev.py
   ```

2. Check that the application loads without errors

3. Visit the "My Farm" and "Application Log" pages - they should display placeholder content

4. The Supabase client will be initialized automatically when you add authentication features

## Next Steps

Once Supabase is set up, you can:

1. **Add Authentication**: Implement user sign-up and login using Supabase Auth
2. **Build My Farm Page**: Create forms to add/edit/delete farm data
3. **Build Application Log**: Create forms to log pesticide applications
4. **Add Favorites**: Allow users to star/favorite pesticides

## Security Notes

- **Never commit your `.env` file** to version control
- The `SUPABASE_ANON_KEY` is safe to use in client-side code (it's public)
- Row Level Security (RLS) policies ensure users can only access their own data
- For production, consider using the `service_role` key server-side only (never expose it)

## Troubleshooting

### "Module 'supabase' not found"
- Make sure you've installed dependencies: `pip install -r requirements.txt`
- Verify you're in the correct virtual environment

### "Supabase client not configured"
- Check that `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set in your `.env` file
- Restart your Flask server after adding environment variables

### "Permission denied" errors
- Verify that Row Level Security policies are created correctly
- Check that users are authenticated before accessing tables

## Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Python Client](https://github.com/supabase/supabase-py)
- [Row Level Security Guide](https://supabase.com/docs/guides/auth/row-level-security)


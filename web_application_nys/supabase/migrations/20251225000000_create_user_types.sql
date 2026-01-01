-- User Types Table
-- Stores user authorization levels: regular_user, full_editor, or partial_editor
CREATE TABLE IF NOT EXISTS user_types (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    user_type TEXT NOT NULL DEFAULT 'regular_user' CHECK (user_type IN ('regular_user', 'full_editor', 'partial_editor')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_user_types_user_type ON user_types(user_type);

-- Enable Row Level Security
ALTER TABLE user_types ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own user type
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_types'
          AND policyname = 'Users can view their own user type'
    ) THEN
        CREATE POLICY "Users can view their own user type"
            ON user_types FOR SELECT
            USING (auth.uid() = user_id);
    END IF;
END$$;

-- Policy: Only service role can insert/update user types (for admin use)
-- Note: This will be managed server-side, not through RLS
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_types'
          AND policyname = 'Service role can manage user types'
    ) THEN
        CREATE POLICY "Service role can manage user types"
            ON user_types FOR ALL
            USING (false)
            WITH CHECK (false);
    END IF;
END$$;

-- Function to automatically create a user_type record when a user signs up
CREATE OR REPLACE FUNCTION create_user_type_on_signup()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_types (user_id, user_type)
    VALUES (NEW.id, 'regular_user')
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to automatically create user_type when a user is created
DROP TRIGGER IF EXISTS on_auth_user_created_create_user_type ON auth.users;
CREATE TRIGGER on_auth_user_created_create_user_type
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION create_user_type_on_signup();



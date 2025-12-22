-- Add farm_name and location fields to user_farm_data table
ALTER TABLE user_farm_data 
ADD COLUMN IF NOT EXISTS farm_name TEXT,
ADD COLUMN IF NOT EXISTS location TEXT,
ADD COLUMN IF NOT EXISTS notes TEXT;

-- Update the unique constraint to include farm_name
-- Drop the old constraint if it exists (PostgreSQL creates it with a generated name)
DO $$ 
DECLARE
    constraint_name TEXT;
BEGIN
    -- Find the constraint name
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'user_farm_data'::regclass
    AND contype = 'u'
    AND array_length(conkey, 1) = 4; -- The old constraint has 4 columns
    
    IF constraint_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE user_farm_data DROP CONSTRAINT ' || quote_ident(constraint_name);
    END IF;
END $$;

-- Add new unique constraint with farm_name
-- Use a partial unique index to handle NULLs properly
CREATE UNIQUE INDEX IF NOT EXISTS user_farm_data_unique_idx 
ON user_farm_data (user_id, farm_name, crop, COALESCE(block, ''), COALESCE(variety, ''))
WHERE farm_name IS NOT NULL;


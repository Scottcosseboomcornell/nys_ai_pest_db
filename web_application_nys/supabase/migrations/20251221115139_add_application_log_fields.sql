-- Add fields to application_logs table for the new application log functionality
ALTER TABLE application_logs 
ADD COLUMN IF NOT EXISTS target TEXT,
ADD COLUMN IF NOT EXISTS mode_of_action TEXT,
ADD COLUMN IF NOT EXISTS acreage DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS farm_name TEXT,
ADD COLUMN IF NOT EXISTS blocks TEXT[]; -- Array of block IDs or names

-- Update pesticide_name to be nullable since we might not always have it
ALTER TABLE application_logs ALTER COLUMN pesticide_name DROP NOT NULL;


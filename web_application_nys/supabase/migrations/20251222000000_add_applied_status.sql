-- Add applied status and actual application date fields to application_logs table
ALTER TABLE application_logs
ADD COLUMN IF NOT EXISTS applied BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS actual_application_date TIMESTAMP WITH TIME ZONE;


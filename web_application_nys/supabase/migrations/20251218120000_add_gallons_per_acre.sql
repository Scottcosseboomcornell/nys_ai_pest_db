-- Add gallons_per_acre field to application_logs table
ALTER TABLE application_logs 
ADD COLUMN IF NOT EXISTS gallons_per_acre DECIMAL(10, 2);


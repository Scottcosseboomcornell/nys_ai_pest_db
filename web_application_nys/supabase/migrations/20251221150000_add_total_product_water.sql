-- Add total_product and total_water fields to application_logs table
ALTER TABLE application_logs 
ADD COLUMN IF NOT EXISTS total_product DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS total_water DECIMAL(10, 2);


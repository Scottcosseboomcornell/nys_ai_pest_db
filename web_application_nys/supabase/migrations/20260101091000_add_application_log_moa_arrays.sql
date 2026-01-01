-- Store pre-parsed MOA codes and normalized block keys for fast resistance-risk calculations
ALTER TABLE application_logs
ADD COLUMN IF NOT EXISTS moa_codes TEXT[],
ADD COLUMN IF NOT EXISTS block_keys TEXT[];

CREATE INDEX IF NOT EXISTS application_logs_moa_codes_gin_idx ON application_logs USING GIN (moa_codes);
CREATE INDEX IF NOT EXISTS application_logs_block_keys_gin_idx ON application_logs USING GIN (block_keys);



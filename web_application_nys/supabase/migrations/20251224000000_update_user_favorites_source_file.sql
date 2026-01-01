-- Update favorites to be keyed by source JSON filename (unique per label),
-- since EPA reg no can map to multiple NY labels.

ALTER TABLE IF EXISTS user_favorites
  ADD COLUMN IF NOT EXISTS source_file TEXT;

-- Allow multiple favorites with the same EPA reg no (different labels).
ALTER TABLE IF EXISTS user_favorites
  DROP CONSTRAINT IF EXISTS user_favorites_user_id_epa_reg_no_key;

-- Ensure a user can favorite the same label only once.
CREATE UNIQUE INDEX IF NOT EXISTS user_favorites_user_id_source_file_key
  ON user_favorites(user_id, source_file)
  WHERE source_file IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_favorites_source_file ON user_favorites(source_file);




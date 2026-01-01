-- Precomputed label index + guided filter join table
-- These tables are intentionally NOT user-owned (no RLS) because they represent shared label metadata.

-- Trigram extension for fast ILIKE searches
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1) label_index: one row per JSON label file (`source_file`)
CREATE TABLE IF NOT EXISTS public.label_index (
  source_file TEXT PRIMARY KEY,
  epa_reg_no TEXT,
  trade_name TEXT,
  company_name TEXT,
  product_type TEXT,
  active_ingredients TEXT[] DEFAULT '{}'::text[],
  -- canonical ingredient objects (compatible with existing frontend expectations)
  -- e.g. [{"name":"Cyazofamid","mode_Of_Action":"FRAC 21"}]
  active_ingredients_json JSONB DEFAULT '[]'::jsonb,
  moa_codes TEXT[] DEFAULT '{}'::text[],
  -- denormalized search text (lowercased) built by offline script
  search_text TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS label_index_epa_reg_no_idx ON public.label_index (epa_reg_no);
CREATE INDEX IF NOT EXISTS label_index_trade_name_trgm_idx ON public.label_index USING GIN (trade_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS label_index_company_name_trgm_idx ON public.label_index USING GIN (company_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS label_index_search_text_trgm_idx ON public.label_index USING GIN (search_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS label_index_active_ingredients_gin_idx ON public.label_index USING GIN (active_ingredients);
CREATE INDEX IF NOT EXISTS label_index_active_ingredients_json_gin_idx ON public.label_index USING GIN (active_ingredients_json);
CREATE INDEX IF NOT EXISTS label_index_moa_codes_gin_idx ON public.label_index USING GIN (moa_codes);

-- 2) label_crop_target: one row per (label, crop, target_type, target)
CREATE TABLE IF NOT EXISTS public.label_crop_target (
  source_file TEXT NOT NULL REFERENCES public.label_index(source_file) ON DELETE CASCADE,
  crop_norm TEXT NOT NULL,
  target_type_norm TEXT NOT NULL,
  target_norm TEXT NOT NULL,
  main_target_list BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (source_file, crop_norm, target_type_norm, target_norm)
);

CREATE INDEX IF NOT EXISTS label_crop_target_crop_type_target_idx
  ON public.label_crop_target (crop_norm, target_type_norm, target_norm);
CREATE INDEX IF NOT EXISTS label_crop_target_source_file_idx
  ON public.label_crop_target (source_file);

-- 3) Fast counts for guided filter dropdowns
CREATE OR REPLACE VIEW public.label_crop_target_counts AS
SELECT
  crop_norm,
  target_type_norm,
  target_norm,
  COUNT(DISTINCT source_file) AS label_count,
  BOOL_OR(main_target_list) AS main_target_list
FROM public.label_crop_target
GROUP BY crop_norm, target_type_norm, target_norm;

-- Convenience views for dropdowns
CREATE OR REPLACE VIEW public.label_crop_counts AS
SELECT
  crop_norm,
  COUNT(DISTINCT source_file) AS label_count
FROM public.label_crop_target
GROUP BY crop_norm;

CREATE OR REPLACE VIEW public.label_crop_target_type_counts AS
SELECT
  crop_norm,
  target_type_norm,
  COUNT(DISTINCT source_file) AS label_count
FROM public.label_crop_target
GROUP BY crop_norm, target_type_norm;



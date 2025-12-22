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


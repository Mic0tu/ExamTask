CREATE TABLE IF NOT EXISTS "public"."image" (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    upload_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    original_size BIGINT NOT NULL DEFAULT 0,
    large_size BIGINT NOT NULL DEFAULT 0,
    medium_size BIGINT NOT NULL DEFAULT 0,
    small_size BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'upload'
);

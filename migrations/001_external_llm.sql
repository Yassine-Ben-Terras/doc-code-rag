CREATE TABLE IF NOT EXISTS llm_settings (
 id INTEGER PRIMARY KEY CHECK (id = 1),
 provider TEXT NOT NULL, base_url TEXT NOT NULL, model TEXT NOT NULL,
 api_key_encrypted TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON llm_settings TO api_role;

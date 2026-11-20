CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE api_role LOGIN PASSWORD :'api_password' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE worker_role LOGIN PASSWORD :'worker_password' NOSUPERUSER BYPASSRLS;
CREATE TABLE roles (id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);
INSERT INTO roles(name) VALUES ('admin'), ('manager'), ('developer');
CREATE TABLE users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, role_id INT NOT NULL REFERENCES roles(id)
);
CREATE TABLE collections (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name TEXT UNIQUE NOT NULL);
CREATE TABLE collection_permissions (
 collection_id UUID REFERENCES collections(id) ON DELETE CASCADE,
 role_id INT REFERENCES roles(id) ON DELETE CASCADE, can_write BOOLEAN NOT NULL DEFAULT FALSE,
 PRIMARY KEY(collection_id, role_id)
);
CREATE TABLE documents (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
 name TEXT NOT NULL, source_url TEXT, storage_path TEXT,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','ready','failed')),
 error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), started_at TIMESTAMPTZ,
 UNIQUE(id, collection_id)
);
CREATE UNIQUE INDEX one_repository_per_collection ON documents(collection_id) WHERE source_url IS NOT NULL;
CREATE INDEX documents_pending ON documents(created_at) WHERE status = 'pending';
CREATE TABLE chunks (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), document_id UUID NOT NULL,
 collection_id UUID NOT NULL, content TEXT NOT NULL, section_path TEXT,
 page INT, line_start INT, line_end INT, embedding vector(1024) NOT NULL,
 FOREIGN KEY(document_id, collection_id) REFERENCES documents(id, collection_id) ON DELETE CASCADE,
 tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(section_path,'') || ' ' || content)) STORED
);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw(embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx ON chunks USING gin(tsv);
CREATE INDEX chunks_collection_idx ON chunks(collection_id);
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY chunks_read ON chunks FOR SELECT TO api_role USING (
 collection_id IN (SELECT cp.collection_id FROM collection_permissions cp
 JOIN users u ON u.role_id = cp.role_id
 WHERE u.id = NULLIF(current_setting('app.user_id', true), '')::uuid)
);
GRANT USAGE ON SCHEMA public TO api_role, worker_role;
GRANT SELECT ON roles TO api_role, worker_role;
GRANT SELECT, INSERT ON users TO api_role, worker_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON collections, collection_permissions, documents TO api_role;
GRANT SELECT ON chunks TO api_role;
GRANT SELECT, UPDATE ON documents TO worker_role;
GRANT SELECT, INSERT, DELETE ON chunks TO worker_role;
CREATE TABLE llm_settings (
 id INTEGER PRIMARY KEY CHECK (id = 1),
 provider TEXT NOT NULL, base_url TEXT NOT NULL, model TEXT NOT NULL,
 api_key_encrypted TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON llm_settings TO api_role;

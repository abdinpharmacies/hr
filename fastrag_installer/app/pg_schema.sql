CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_collections (
    name text PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS rag_keys (
    digest text PRIMARY KEY,
    collection text NOT NULL REFERENCES rag_collections(name),
    permissions text[] NOT NULL,
    public_only boolean NOT NULL DEFAULT false,
    revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS rag_records (
    id uuid PRIMARY KEY,
    collection text NOT NULL REFERENCES rag_collections(name),
    source_id text,
    title text NOT NULL,
    text text NOT NULL,
    metadata jsonb NOT NULL,
    public boolean NOT NULL DEFAULT false,
    archived boolean NOT NULL DEFAULT false,
    revision bigint NOT NULL DEFAULT 1,
    indexed_revision bigint,
    indexed_profile text,
    UNIQUE (collection, source_id)
);
CREATE INDEX IF NOT EXISTS rag_records_collection_idx ON rag_records(collection, id);
CREATE TABLE IF NOT EXISTS rag_files (
    id uuid PRIMARY KEY,
    record_id uuid NOT NULL REFERENCES rag_records(id),
    filename text NOT NULL,
    caption text NOT NULL,
    size integer NOT NULL,
    content bytea NOT NULL
);
CREATE INDEX IF NOT EXISTS rag_files_record_idx ON rag_files(record_id);
CREATE TABLE IF NOT EXISTS rag_chunks (
    record_id uuid NOT NULL REFERENCES rag_records(id),
    chunk_index integer NOT NULL,
    file_id uuid,
    content text NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (record_id, chunk_index)
);
CREATE TABLE IF NOT EXISTS rag_jobs (
    id uuid PRIMARY KEY,
    record_id uuid NOT NULL REFERENCES rag_records(id),
    revision bigint NOT NULL,
    profile text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    token uuid,
    error text,
    UNIQUE (record_id, revision, profile)
);
CREATE INDEX IF NOT EXISTS rag_jobs_poll_idx ON rag_jobs(profile, available_at, id)
    WHERE status IN ('queued', 'running');
CREATE TABLE IF NOT EXISTS rag_requests (
    collection text NOT NULL REFERENCES rag_collections(name),
    operation text NOT NULL,
    key uuid NOT NULL,
    fingerprint text NOT NULL,
    response jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (collection, operation, key)
);
CREATE INDEX IF NOT EXISTS rag_requests_time_idx ON rag_requests(created_at);

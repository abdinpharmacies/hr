CREATE TABLE IF NOT EXISTS messaging_schema (version integer PRIMARY KEY);
CREATE TABLE IF NOT EXISTS incoming_event (
    id bigserial PRIMARY KEY,
    account text NOT NULL,
    event_key text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('incoming', 'status', 'ignored')),
    fingerprint text NOT NULL,
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account, event_key)
);
CREATE INDEX IF NOT EXISTS incoming_pending ON incoming_event (available_at) WHERE state IN ('pending', 'processing');
CREATE TABLE IF NOT EXISTS outgoing_operation (
    id bigserial PRIMARY KEY,
    account text NOT NULL,
    token text NOT NULL,
    attempt integer NOT NULL,
    receipt text NOT NULL,
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'stored',
    outcome jsonb,
    sends integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account, token, attempt)
);
CREATE INDEX IF NOT EXISTS outgoing_pending ON outgoing_operation (available_at) WHERE state IN ('ready', 'report');
CREATE TABLE IF NOT EXISTS operator_audit (
    id bigserial PRIMARY KEY,
    event_id bigint NOT NULL REFERENCES incoming_event(id),
    actor text NOT NULL,
    note text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO messaging_schema(version) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS telegram_polling (
    provider_account text PRIMARY KEY,
    next_offset bigint NOT NULL CHECK (next_offset >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS incoming_conversation_pending ON incoming_event
    (account, (COALESCE(payload->>'sender',payload->>'destination','')), id)
    WHERE state NOT IN ('done','ignored');
CREATE INDEX IF NOT EXISTS outgoing_conversation_pending ON outgoing_operation
    (account, (payload->>'destination'), id)
    WHERE state!='done' OR outcome->>'status'='review';

CREATE TABLE IF NOT EXISTS public.agent_onboarding (
  watch_hash text PRIMARY KEY CHECK (length(watch_hash) = 64),
  code_hash text NOT NULL UNIQUE CHECK (length(code_hash) = 64),
  client text NOT NULL CHECK (client IN ('claude', 'chatgpt', 'codex', 'grok', 'hermes')),
  expires_at timestamptz NOT NULL,
  verified_at timestamptz
);

CREATE INDEX IF NOT EXISTS agent_onboarding_expires_idx
  ON public.agent_onboarding (expires_at);

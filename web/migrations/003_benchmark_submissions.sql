CREATE TABLE IF NOT EXISTS public.benchmark_submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL UNIQUE,
  provider text NOT NULL CHECK (provider IN ('anthropic', 'openai', 'gemini', 'compat')),
  model_name text NOT NULL CHECK (char_length(model_name) BETWEEN 1 AND 120),
  task_set text NOT NULL CHECK (char_length(task_set) BETWEEN 1 AND 80),
  tasks_digest text NOT NULL CHECK (tasks_digest ~ '^[0-9a-f]{64}$'),
  kit_version text NOT NULL CHECK (char_length(kit_version) BETWEEN 1 AND 32),
  release_accuracy double precision NOT NULL CHECK (release_accuracy BETWEEN 0 AND 1),
  field_accuracy double precision NOT NULL CHECK (field_accuracy BETWEEN 0 AND 1),
  efficiency double precision NOT NULL CHECK (efficiency BETWEEN 0 AND 1),
  safety double precision NOT NULL CHECK (safety BETWEEN 0 AND 1),
  overall double precision NOT NULL CHECK (overall BETWEEN 0 AND 1),
  critical_errors integer NOT NULL CHECK (critical_errors >= 0),
  engine_outcomes jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS benchmark_submissions_leader_idx
  ON public.benchmark_submissions (provider, model_name, overall DESC, created_at);

-- Apply with a direct connection to the intended Neon branch before deploying.
CREATE TABLE IF NOT EXISTS public.rate_buckets (
  key text PRIMARY KEY,
  tokens double precision NOT NULL,
  updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS rate_buckets_updated_at_idx ON public.rate_buckets (updated_at);

CREATE OR REPLACE FUNCTION public.take_token(p_key text, p_capacity integer, p_refill_per_sec double precision)
RETURNS TABLE (allowed boolean, retry_after_sec integer)
LANGUAGE plpgsql AS $$
DECLARE
  current_bucket public.rate_buckets%ROWTYPE;
  taken_at timestamptz;
  available double precision;
BEGIN
  IF p_capacity < 1 OR p_refill_per_sec <= 0 OR p_key IS NULL THEN
    RAISE EXCEPTION 'invalid rate limit configuration';
  END IF;
  INSERT INTO public.rate_buckets (key, tokens, updated_at)
    VALUES (p_key, p_capacity, clock_timestamp()) ON CONFLICT DO NOTHING;
  SELECT * INTO current_bucket FROM public.rate_buckets WHERE key = p_key FOR UPDATE;
  taken_at := clock_timestamp();
  available := LEAST(p_capacity::double precision, current_bucket.tokens +
    GREATEST(0, EXTRACT(EPOCH FROM taken_at - current_bucket.updated_at)) * p_refill_per_sec);
  allowed := available >= 1;
  retry_after_sec := CASE WHEN allowed THEN 0 ELSE CEIL((1 - available) / p_refill_per_sec)::integer END;
  UPDATE public.rate_buckets SET tokens = CASE WHEN allowed THEN available - 1 ELSE available END,
    updated_at = taken_at WHERE key = p_key;
  RETURN NEXT;
END;
$$;

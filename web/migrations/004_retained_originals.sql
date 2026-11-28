create table if not exists retained_originals (
  object_key text primary key,
  owner_id text not null,
  file_name text not null,
  byte_size bigint not null check (byte_size >= 0),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '30 days'),
  stored_at timestamptz,
  deleted_at timestamptz
);

create index if not exists retained_originals_expiry
  on retained_originals (expires_at, object_key) where deleted_at is null;

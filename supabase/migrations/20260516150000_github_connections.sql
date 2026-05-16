create table if not exists public.github_connections (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.tasks(id) on delete set null,
  state_hash text not null unique,
  encrypted_pending_code text,
  encrypted_access_token text,
  scopes text[] not null default '{}',
  github_login text,
  github_user_id bigint,
  status text not null default 'pending'
    check (status in ('pending', 'ready', 'exchanged', 'failed')),
  return_url text not null,
  error_summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  exchanged_at timestamptz
);

alter table public.github_connections enable row level security;

create index if not exists github_connections_task_id_idx
  on public.github_connections(task_id);

create index if not exists github_connections_state_hash_idx
  on public.github_connections(state_hash);

create index if not exists github_connections_status_idx
  on public.github_connections(status);

create index if not exists github_connections_created_at_idx
  on public.github_connections(created_at desc);

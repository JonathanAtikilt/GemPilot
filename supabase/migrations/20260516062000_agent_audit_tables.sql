create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  idea text,
  repo_name text,
  status text default 'new',
  scoped_mvp text,
  final_report jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.tool_calls (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.tasks(id) on delete set null,
  tool_name text not null,
  input_json jsonb default '{}'::jsonb,
  output_json jsonb default '{}'::jsonb,
  status text,
  verification_status text,
  created_at timestamptz default now()
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.tasks(id) on delete set null,
  step text not null,
  message text,
  data jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.generated_artifacts (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.tasks(id) on delete set null,
  artifact_type text not null,
  path text,
  content text,
  commit_sha text,
  created_at timestamptz default now()
);

alter table public.tasks enable row level security;
alter table public.tool_calls enable row level security;
alter table public.audit_logs enable row level security;
alter table public.generated_artifacts enable row level security;

create index if not exists tool_calls_task_id_idx on public.tool_calls (task_id);
create index if not exists tool_calls_created_at_idx on public.tool_calls (created_at desc);
create index if not exists audit_logs_task_id_idx on public.audit_logs (task_id);
create index if not exists audit_logs_created_at_idx on public.audit_logs (created_at desc);
create index if not exists generated_artifacts_task_id_idx on public.generated_artifacts (task_id);

-- Migration for agent memories
create table public.memories (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.tasks(id) on delete set null,
  idea text not null,
  summary text not null,
  outcome jsonb default '{}'::jsonb,
  tags text[] default '{}'::text[],
  embedding extensions.vector(768),
  created_at timestamptz default now()
);

-- Enable RLS
alter table public.memories enable row level security;

-- Add indexes
create index memories_task_id_idx on public.memories (task_id);
create index memories_created_at_idx on public.memories (created_at desc);
-- Embedding index can be added later once the demo corpus grows.

-- Match memories RPC
create or replace function public.match_memories(
  query_embedding extensions.vector(768),
  match_count int default 5
)
returns table (
  id uuid,
  task_id uuid,
  idea text,
  summary text,
  outcome jsonb,
  tags text[],
  similarity float,
  score float,
  created_at timestamptz
)
language plpgsql
as $$
begin
  return query
  select
    m.id,
    m.task_id,
    m.idea,
    m.summary,
    m.outcome,
    m.tags,
    1 - (m.embedding <=> query_embedding) as similarity,
    1 - (m.embedding <=> query_embedding) as score,
    m.created_at
  from public.memories m
  where m.embedding is not null
  order by m.embedding <=> query_embedding
  limit match_count;
end;
$$;

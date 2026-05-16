-- Migration for agent memories
create table public.memories (
  id uuid primary key default gen_random_uuid(),
  task_id uuid references public.tasks(id) on delete set null,
  idea text not null,
  summary text not null,
  outcome jsonb default '{}'::jsonb,
  tags text[] default '{}'::text[],
  embedding extensions.vector(2048),
  created_at timestamptz default now()
);

-- Enable RLS
alter table public.memories enable row level security;

-- Add indexes
create index memories_task_id_idx on public.memories (task_id);
create index memories_created_at_idx on public.memories (created_at desc);
-- No index for embeddings since it exceeds 2000 dimensions (2048)

-- Match memories RPC
create or replace function public.match_memories(
  query_embedding extensions.vector(2048),
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
  order by m.embedding <=> query_embedding
  limit match_count;
end;
$$;

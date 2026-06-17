drop function if exists public.match_rag_chunks(
  extensions.vector(2048),
  int,
  float,
  text[]
);

drop function if exists public.match_memories(
  extensions.vector(2048),
  int
);

alter table public.rag_chunks
  alter column embedding type extensions.vector(768)
  using null;

alter table public.memories
  alter column embedding type extensions.vector(768)
  using null;

create or replace function public.match_rag_chunks(
  query_embedding extensions.vector(768),
  match_count int default 10,
  match_threshold float default -1,
  filter_doc_types text[] default null
)
returns table (
  id uuid,
  chunk_id text,
  source text,
  title text,
  doc_type text,
  text text,
  metadata jsonb,
  similarity float,
  authority_score float,
  weighted_score float
)
language sql
stable
set search_path = public, extensions
as $$
  select
    rag_chunks.id,
    rag_chunks.chunk_id,
    rag_chunks.source,
    rag_chunks.title,
    rag_chunks.doc_type,
    rag_chunks.text,
    rag_chunks.metadata,
    1 - (rag_chunks.embedding <=> query_embedding) as similarity,
    rag_chunks.authority_score,
    (1 - (rag_chunks.embedding <=> query_embedding)) * rag_chunks.authority_score as weighted_score
  from public.rag_chunks
  where rag_chunks.embedding is not null
    and (filter_doc_types is null or rag_chunks.doc_type = any(filter_doc_types))
    and 1 - (rag_chunks.embedding <=> query_embedding) >= match_threshold
  order by weighted_score desc
  limit least(match_count, 50);
$$;

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

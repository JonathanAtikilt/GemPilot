create extension if not exists vector with schema extensions;

create table if not exists public.rag_chunks (
  id uuid primary key default gen_random_uuid(),
  chunk_id text unique not null,
  source text not null,
  title text,
  doc_type text,
  text text not null,
  metadata jsonb default '{}'::jsonb,
  authority_score double precision not null default 0.5,
  embedding extensions.vector(768),
  created_at timestamptz default now()
);

alter table public.rag_chunks enable row level security;

create index if not exists rag_chunks_source_idx on public.rag_chunks (source);
create index if not exists rag_chunks_doc_type_idx on public.rag_chunks (doc_type);

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

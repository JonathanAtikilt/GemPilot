-- Link OAuth connections to in-memory orchestrator tasks without FK to public.tasks.
alter table public.github_connections
  add column if not exists workflow_task_id text;

create index if not exists github_connections_workflow_task_id_idx
  on public.github_connections(workflow_task_id);

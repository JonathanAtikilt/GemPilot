import os
import re


def test_memories_migration_exists_and_contains_requirements():
    migrations_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "supabase",
        "migrations"
    )
    
    # Find the memories migration file
    memories_file = None
    for filename in os.listdir(migrations_dir):
        if "memories" in filename.lower() and filename.endswith(".sql"):
            memories_file = os.path.join(migrations_dir, filename)
            break
            
    assert memories_file is not None, "Memories migration file not found."
    
    with open(memories_file, "r") as f:
        content = f.read().lower()
        
    # Assert public.memories table
    assert "create table public.memories" in content or "create table if not exists public.memories" in content
    
    # Assert RLS
    assert "enable row level security" in content
    
    # Assert indexes
    assert "create index" in content
    assert "task_id" in content
    assert "created_at" in content
    # Note: Embedding index was removed because pgvector does not support indexing vectors over 2000 dimensions
    
    # Assert match_memories RPC
    assert "create or replace function public.match_memories" in content or "create function public.match_memories" in content

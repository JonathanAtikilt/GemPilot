import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.rag.store import SupabaseRagStore


@pytest.mark.asyncio
async def test_search_memories():
    with patch("agent.rag.store.get_supabase_url", return_value="http://localhost"), \
         patch("agent.rag.store.get_supabase_service_role_key", return_value="key"), \
         patch("supabase.create_client") as mock_create_client:
        
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.data = [{"id": "uuid-1", "summary": "test memory"}]
        mock_response.error = None
        mock_client.rpc.return_value.execute.return_value = mock_response

        store = SupabaseRagStore()
        result = await store.search_memories([0.1, 0.2], top_k=2)

        assert len(result) == 1
        assert result[0]["id"] == "uuid-1"
        assert result[0]["summary"] == "test memory"
        mock_client.rpc.assert_called_once_with(
            "match_memories",
            {
                "query_embedding": [0.1, 0.2],
                "match_count": 2,
            }
        )


@pytest.mark.asyncio
async def test_write_memory():
    with patch("agent.rag.store.get_supabase_url", return_value="http://localhost"), \
         patch("agent.rag.store.get_supabase_service_role_key", return_value="key"), \
         patch("supabase.create_client") as mock_create_client:
        
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.error = None
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        store = SupabaseRagStore()
        memory = {
            "idea": "test idea",
            "summary": "test summary",
            "outcome": {"workflow_task_id": "test_task"},
            "tags": ["workflow_outcome"],
            "embedding": [0.1, 0.2],
        }
        await store.write_memory(memory)

        mock_client.table.assert_called_once_with("memories")
        mock_client.table.return_value.insert.assert_called_once_with([memory])

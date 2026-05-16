# NVIDIA Nemotron Retrieval Models

MVPilot uses NVIDIA Nemotron retrieval models for grounding agent decisions in local documentation.

Embedding model: llama-nemotron-embed-1b-v2. Use passage mode when indexing documents and query mode when searching. Store embeddings with the text chunks that produced them.

Rerank model: llama-nemotron-rerank-1b-v2. Use it after vector retrieval to reorder candidate passages by relevance to the current task or question. If reranking is unavailable, keep the vector-search order and return a warning.

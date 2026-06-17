# Provider Retrieval Models

MVPilot uses configurable embedding providers for grounding agent decisions in local documentation.

Embedding model: gemini-embedding-001. Use passage mode when indexing documents and query mode when searching. Store embeddings with the text chunks that produced them.

Ranking: pgvector cosine similarity with source-authority weighting. The external reranker is intentionally removed for now; `agent/rag/rerank.py` is the future abstraction point for a cross-encoder.

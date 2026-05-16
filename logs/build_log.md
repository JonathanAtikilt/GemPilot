# Build Log

Initial MVPilot RAG service setup is in progress.

Expected validation path:

1. Start the backend server.
2. Ingest sample markdown documents.
3. Search for hackathon priorities and confirm returned chunks include source filenames, doc types, and scores.

If NVIDIA_API_KEY is not set, ingestion and search should return a clear missing-key error rather than silently using fake embeddings.

# Team Notes

The RAG and Docs Agent owns retrieval over hackathon rules, NVIDIA docs, generated project docs, README files, build logs, and team notes.

The Orchestrator Agent should call the RAG get-build-context endpoint before deciding project scope or next action. The RAG agent should provide grounded context and short recommendations only; it should not choose the final project by itself.

The GitHub Repo Agent should call the log reindex endpoint after creating commits or collecting build errors so the next orchestration cycle can use the latest evidence.

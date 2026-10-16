# Contributor instructions
Read docs/PRD.md. Build only the user-authorized milestone; Milestone 5 is authorized: retrieval/citation/abstention evaluation, security/offline verification, Streamlit integration tests and honest P0 acceptance evidence or release blockers. Later milestones remain out of scope until authorized.
All parsing, processing and domain logic belongs in src/knowledgebridge; never import Streamlit or access its session state there.
Treat documents as untrusted data: no execution, URL fetching, source-driven commands/paths, or unsafe HTML. Preserve source IDs, versions, page/section references and exact passage slices.
Use Python 3.12, typed public interfaces, Pydantic v2, bounded safe YAML, and the uv.lock workflow. Run pytest, Ruff, mypy and pip-audit; report actual failures/advisories.
Keep the app on 127.0.0.1 with telemetry and detailed UI errors disabled. Never log source contents. Keep local data, exports, caches and credentials out of Git. Preserve user-supplied PRD and technology notes.

The user requested a pause after Milestone 5 and the first GitHub commit/push. Do not start Milestone 6 without a new user instruction to resume. Keep documented release blockers visible.

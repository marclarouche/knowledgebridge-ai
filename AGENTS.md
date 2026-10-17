# Contributor instructions
Read docs/PRD.md. Milestone 6 is now authorized: prepare reproducible installation/user guides, architecture diagram, methodology/limitations, evaluation report, recorded sample answers, screenshots and a technical writing portfolio case study. Keep documented release blockers visible; portfolio preparation does not establish validated release readiness.
All parsing, processing and domain logic belongs in src/knowledgebridge; never import Streamlit or access its session state there.
Treat documents as untrusted data: no execution, URL fetching, source-driven commands/paths, or unsafe HTML. Preserve source IDs, versions, page/section references and exact passage slices.
Use Python 3.12, typed public interfaces, Pydantic v2, bounded safe YAML, and the uv.lock workflow. Run pytest, Ruff, mypy and pip-audit; report actual failures/advisories.
Keep the app on 127.0.0.1 with telemetry and detailed UI errors disabled. Never log source contents. Keep local data, exports, caches and credentials out of Git. Preserve user-supplied PRD and technology notes.

The user resumed Milestone 6 on October 17, 2026. The prior pause after Milestone 5 is superseded. Do not claim human benchmark completion, production readiness or a clean dependency audit without new evidence.

The user authorized investigating and fixing answer-validation failures encountered in the guided walkthrough, then continuing document import and library management. Keep original evaluation evidence historical and distinguish targeted follow-up probes from a full benchmark.

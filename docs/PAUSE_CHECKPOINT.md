> October 17 follow-up: the guided user walkthrough is complete, including disposable import, indexing, replacement and deletion. Citation hardening and remaining semantic failures are documented in [the investigation](walkthrough_validation_investigation.md). The user authorized committing and pushing all repository changes; earlier pause/deferred-walkthrough notes below are historical.

> Current status: Milestone 6 portfolio preparation completed October 17, 2026 after the user resumed work. See [Milestone 6 completion](milestone_6_completion.md) and the [guided walkthrough](user_guide.md#guided-fictional-walkthrough). The Phase 5 pause is superseded; documented release blockers remain open. Historical notes follow.

> Current status: Milestone 5 testing/evaluation completed October 16, 2026 with documented release blockers. See [Milestone 5 completion](milestone_5_completion.md). The user requested a pause after milestone 5 and the first GitHub commit/push. Milestone 6 has not started. Full user walkthrough remains deferred. Resume only when requested. Historical notes follow.

> Current status: Milestone 4 completed and verified October 16, 2026. See [Milestone 4 completion](milestone_4_completion.md). Milestones 5 and 6 have not started. Full user walkthrough is deferred until completion. The notes below are historical.

> Current status: Milestone 3 implemented and verified October 16, 2026. See [Milestone 3 completion](milestone_3_completion.md) for actual model probes, limitations and unresolved dependency advisories. Milestone 4 has not started. The notes below are historical.

> Current status: Milestone 2 completed October 16, 2026. See [Milestone 2 report](milestone_2_completion.md), including unresolved dependency audit findings. Milestone 3 has not started. The notes below are historical.

> Resumed and completed October 16, 2026. This is a historical checkpoint. See [Milestone 1 completion](milestone_1_completion.md) for current status. Milestone 2 has not started.

# KnowledgeBridge AI — paused Milestone 1 checkpoint

Paused October 15, 2026 at the user's explicit request. **Milestone 1 is in progress, not complete.** Do not start Milestone 2. Resume only when the user asks.

## Project and scope

Actual project: /Users/cyberlifecoach/Projects/knowledgebridge-ai. The shorthand /Projects/knowledgebridge-ai does not exist. Original knowledgebridge-ai-prd.md and knowledgebridge-techstack.md are preserved. docs/PRD.md is copied from the supplied PRD. AGENTS.md records the architecture and authorized scope.

M1 includes local ingestion, source identity/location records, chunking, a session-only inspection UI, fictional manuals and tests. There is no Ollama, embedding, vector/keyword index, RAG, chat, persistence, cloud or publishing implementation.

## Work saved

- pyproject.toml, uv.lock, AGENTS.md, .gitignore, .streamlit/config.toml, config/knowledgebridge.yaml, data/.gitkeep.
- src/knowledgebridge: __init__.py, config.py, models.py, parsers.py, chunker.py, ingestion.py.
- app.py: Knowledge Collections, Document Import, Parsed Documents, Passage Explorer, Settings and Diagnostics.
- Eight original fictional FleetOps manuals covering Markdown, TXT, DOCX and PDF, with intentional version conflicts and missing evidence, plus README and manifest.
- tests/test_ingestion.py and tests/test_chunker_ui.py.
- Python 3.12.15 virtual environment, locked external dependencies and installed editable knowledgebridge-ai 0.1.0.

Imports operate on bounded bytes and keep extracted records in memory. SHA-256 detects exact-byte duplicates. Stable IDs retain document version, section and chunk configuration. Passages are exact section slices with half-open Unicode offsets. PDF page references are preserved. DOCX tables are flattened in body order; PDF text extraction performs no OCR. Imported scripts/URLs remain data. Archive expansion, extraction, document, section and passage counts have bounds, but this is not a hardened native-parser CPU/RAM sandbox.

## Actual checks at pause

- Last full pytest run: **36 passed, 1 failed, 5 upstream SWIG deprecation warnings, in 4.81 seconds**.
- Failing test: test_ui_collection_demo_and_all_inspection_views_offline.
- Failure occurs when switching views after creating a collection and loading/reloading the demo. AppTest's active_collection_id selectbox attempts to find the raw UUID among formatted title labels and raises ValueError. Inspect the format_func lambda's capture of the reused names variable across view branches; this is a likely cause, not yet confirmed. Do not conceal the failure by dropping coverage.
- The previous first cold UI run hit its 20-second AppTest timeout. An isolated initial UI/demo load subsequently succeeded with zero exceptions and eight documents. Test timeout was changed to 45 seconds; the current failure is the distinct selectbox/formatting error above.
- Ruff lint passed after initial corrections; formatting was applied. Strict mypy passed across 7 source files. Three targeted no-untyped-call annotations cover PyMuPDF's native binding interfaces.
- pip check: no broken requirements.
- pip-audit: no known dependency vulnerabilities. The unpublished local knowledgebridge-ai 0.1.0 package was explicitly skipped because it is not on PyPI.
- Parser/chunker checks cover all four formats, corruption, empty/encrypted/image-only PDFs, SHA-256 duplicates, stable IDs, DOCX table ordering, page/source offsets, resource limits, inert content, network prohibition and 100 seeded chunk-boundary cases. The offline UI tour remains failing and must be resolved before claiming complete UI verification.

## Remaining M1 work

1. Resolve the active-collection selection/formatting issue; rerun the full suite without weakening the offline checks.
2. Review whitespace-only DOCX core title handling: the attempted strip patch did not match the formatted title expression in parsers.py. Such a title may currently cause final SourceDocument validation to escape the parser boundary. Add a focused regression and safe normalization/fallback.
3. Finish import/parser edge review and verify source-reference/limit behavior. No need to add later-stage features.
4. Write README.md, docs/architecture.md, docs/security.md, docs/methodology.md and docs/user_guide.md, including precise offsets, format limitations, lockfile workflow and session-only storage.
5. Initialize Git locally (not yet done). No repository URL for this new project was supplied; no commit or push has been authorized for KnowledgeBridge by the earlier, project-specific Microcopy instructions.
6. Verify uv lock/sync reproducibility, final pytest/Ruff/format/mypy/pip-audit, and a real local application smoke test. Use a free port such as 8502; Microcopy Lab is already running on 8501 and must not be stopped. No KnowledgeBridge server is currently running.
7. Provide the requested M1 completion report and readiness assessment only after actual verification. Do not proceed to M2 without a separate instruction.

## Useful commands

From the project directory:

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/python -m ruff check --no-cache .
.venv/bin/python -m ruff format --check --no-cache .
.venv/bin/python -m mypy
.venv/bin/python -m pip check
.venv/bin/python -m pip_audit --progress-spinner off
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

uv 0.13.1 was bootstrapped separately at /Users/cyberlifecoach/Documents/Codex/2026-10-15/wor/work/kb-tooling/bin/uv. Standard supported workflow: uv lock, then uv sync --locked --group dev. A fresh sync selected managed Python 3.12.15 under the declared >=3.12,<3.13 constraint. Installing dependencies/model-independent tooling used network; normal parsing and chunking require none.

Scratch builders and patch scripts are retained under /Users/cyberlifecoach/Documents/Codex/2026-10-15/wor/work/kb1. Do not overwrite current formatted project files wholesale with older staging copies. The current project is the source of truth.

# KnowledgeBridge AI — Milestone 2 completion

Completed October 16, 2026 in `/Users/cyberlifecoach/Projects/knowledgebridge-ai`.
Functional exit criterion met: supported test queries retrieve source-referenced passages with local keyword, semantic and hybrid retrieval, without language-model answer generation. Dependency audit has unresolved findings detailed below. Milestone 3 has not started.

## Implementation

New engine modules: `embedding_adapter.py`, `retrieval_models.py`, `index_repository.py`, `indexing.py`, and `retriever.py`. Streamlit remains the presentation layer. Updated configuration, core collection/status descriptions, app views, AGENTS.md, lockfile, README, architecture, methodology, security and user guide. Added `tests/test_retrieval.py`, isolated UI test storage, `scripts/evaluate_retrieval.py`, and 30 development probe questions. Original supplied PRD and technology notes remain preserved.

- Ollama embedding batches through a loopback-only HTTP adapter; no proxy/redirect/cloud fallback, model pulling, implicit truncation or default Chroma embedding function.
- Installed official `embeddinggemma:latest` locally (approximately 621 MB of weights). Verified digest `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`, 768-dimensional finite normalized vectors.
- Chroma 1.5.9 embedded Rust backend, cosine retrieval, telemetry disabled. Explicit backend selection prevents an environment variable from silently selecting a network backend.
- SQLite source catalog, validated source fingerprint, generation manifest, and isolated FTS5 tables. Keyword tokenization retains underscores; punctuation splits. Quoted OR terms prevent FTS/SQL syntax injection. BM25 statistics are isolated per snapshot.
- Equal-weight reciprocal rank fusion, default 20 candidates per method, top five results, k=60; deduplicated source-linked hits with individual ranks and scores.
- Immutable vector generations staged before atomic SQLite activation. Failed embeddings or database writes preserve the active snapshot. Old generations remain to allow in-flight reads and avoid destructive cleanup.
- Selected-document reindexing rechunks retained sections with current settings and atomically rebuilds all collection embeddings. Model digest/configuration changes block semantic/hybrid queries until rebuilding. Keyword retrieval works without Ollama.
- New Index and Search view builds/reopens persisted sources, retrieves exact passages with visible passage IDs and section/page/version details, and exposes collapsible diagnostics. Saved/session source differences are disclosed.

## Actual verification

| Check | Result |
| --- | --- |
| pytest, actual project | **72 passed**, five upstream SWIG deprecation warnings, final run 7.91 seconds |
| Ruff lint | Passed |
| Ruff formatting | Passed, 34 files checked |
| Strict mypy | Passed, 12 source files |
| pip check | No broken requirements |
| uv sync --locked --group dev | Passed; 135-package lock resolution; Intel macOS compatibility explicitly constrained |
| Offline tests | Passed for four-format ingestion, Chroma/FTS indexing with controlled vectors, keyword retrieval, UI reopening/search, and explicit semantic failure |
| Failure tests | Passed for missing/corrupt index records, model identity changes, bad vectors/responses, redirects, query limits, failed embeddings and SQLite rollback |
| Live local smoke | Built eight fictional manuals into 31 passages; hybrid query showed relevant exact API and PDF excerpts with source references |
| Fresh-process persistence/reindex | Passed with real Ollama, new active generation, eight documents and 31 passages |
| Git exclusions | Persistent SQLite/Chroma files, environment files, virtual environment and outputs are ignored |

The existing KnowledgeBridge server was restarted on http://127.0.0.1:8502. The other application on port 8501 was not stopped. No commit, remote setup or push was performed.

## Real-model development probes

Thirty AI-authored questions include 24 designated filename/excerpt targets and six unsupported/unrelated questions. Top-five target presence:

| Mode | Designated targets found |
| --- | --- |
| Keyword | 23/24 (95.83%) |
| Semantic | 24/24 (100%) |
| Hybrid | 23/24 (95.83%) |

RQ-019, the legacy MFA-default question, missed its designated legacy passage in keyword and hybrid top-five results. This remains a documented ranking limitation. There was no tuning to force this fixture to pass. Scores do not establish source authority or answer support. Unsupported questions have no success target and can still retrieve neighbors. These figures are development target-hit rates, not exhaustive Recall@k or independent human-reviewed benchmark results. Human evaluation, abstention and answer support remain later milestones.

Reproduce with:

```sh
uv run python scripts/evaluate_retrieval.py --data-dir work/evaluation-index --output outputs/retrieval-probe.json
```

## Dependency audit findings

The actual project audit returned **five findings in Chroma 1.5.9, representing four unique advisories**, with no fix versions listed. PYSEC-2026-311 appears twice. No findings were suppressed. The unpublished local package `knowledgebridge-ai` 0.1.0 was skipped because it is not available on PyPI.

- [PYSEC-2026-311 / CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c): server collection creation with dangerous remote model configuration.
- [PYSEC-2026-3814 / CVE-2026-45833](https://github.com/advisories/GHSA-36p7-vc44-83pf): server collection update with dangerous remote model configuration.
- [PYSEC-2026-3815 / CVE-2026-45831](https://github.com/advisories/GHSA-xph7-9rjv-w5fr): server RBAC resource scoping.
- [PYSEC-2026-3813 / CVE-2026-45830](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr): server tenant authorization bypass.

Applicability assessment: the embedded-only design starts no Chroma HTTP server, uses no server RBAC/tenant authorization, and accepts no configurable embedding functions or remote repositories. The reported attack paths are not exposed by this application. This is a scoped assessment, not a vulnerability-free declaration. The dependency audit remains nonzero and must be reviewed before release or any server/multiuser deployment.

## Storage and limitations

Indexing explicitly persists extracted source sections, passages, metadata, keyword data and embeddings in Git-ignored `data/index`, with an operator override via `KNOWLEDGEBRIDGE_DATA_DIR`. Original binary uploads are not retained; keep originals. Retained extracted sources support rechunking/re-embedding but cannot recover omitted parser content. Prior and interrupted vector/keyword generations remain on disk; deletion and cleanup controls are Milestone 4 work. Local storage is unencrypted.

Structural integrity checks cover source links, fingerprints, FTS contents, vector IDs and embedding identity; they cannot detect every same-shape numerical corruption or deliberate same-user tampering. Native document parsers are not hardened CPU/RAM sandboxes. Default ranking settings are not calibrated for production, and approximate vector candidate boundaries can differ across platforms.

No generated answers, evidence sufficiency decisions, conflict adjudication, replacement/deletion workflows, cloud connectors or agent execution were added. Ready for separately authorized Milestone 3 development, with the documented audit and retrieval limitations carried forward.

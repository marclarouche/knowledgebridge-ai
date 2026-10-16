# KnowledgeBridge AI

Milestone 4: persistent local document libraries, source-grounded answers and lifecycle management.
Python 3.12, Streamlit, Ollama, embedded Chroma and SQLite FTS5.

## Install and run

```sh
uv sync --locked --group dev
ollama pull embeddinggemma
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Start the local Ollama service first. Generation defaults to the locally installed `qwen3-vl:4b-instruct`; install it separately if needed. The application never pulls models automatically. Open http://127.0.0.1:8502.

Installation requires downloads unless dependencies/models are cached. Normal operations use local disk and loopback Ollama only. Collection management, source inspection, keyword search and document deletion require no running model. Indexing and indexed-document replacement require the configured embedding model; answers require both embedding and generation models.

The existing lockfile includes Intel macOS compatibility constraints for ONNX Runtime. To intentionally update dependencies, run `uv lock`, review changes, then sync with `--locked` and rerun checks.

## Current capabilities

- Import UTF-8 TXT/Markdown, DOCX and text-based PDF; retain exact extracted sections, source identities, versions and passage offsets.
- Persist empty collections and pending imports immediately, with create/rename/delete controls. Pending sources are separate from the last active search index.
- Build keyword/semantic indexes and retrieve source passages with transparent hybrid ranking.
- Replace a document atomically after validation and successful embedding/indexing. Failed replacement leaves the old source and index active.
- Delete a document using retained embeddings for the remaining active sources, without Ollama. Deleting the last indexed source removes the active index and preserves an empty saved collection.
- Remove retired vector/keyword generations after lifecycle operations; retry failed cleanup from Settings and Diagnostics.
- Inspect exact current passages in Source Explorer, navigate there from answer references, and flag references to replaced/deleted sources or superseded indexes.
- Generate cited local answers, abstain on detected missing/unsupported evidence, and show confirmed version-dependent conflicts. Verify important claims against original documents.

## Storage and deletion

Collections and extracted imports are saved in Git-ignored `data/index` immediately. Original binary uploads are not retained; keep originals for reparsing/recovery. Pending sources become searchable after a successful build. `KNOWLEDGEBRIDGE_DATA_DIR` relocates application-owned storage.

Milestone 4 upgrades the catalog additively from schema 1 to 2, preserving existing active snapshots and source identities. Revision checks reject stale writes and builds. Deleted collection IDs are retained as content-free tombstones to prevent stale sessions from restoring them.

Deletion removes saved sources and active search records. Retired generations are cleaned afterward; a failed cleanup is explicitly reported and retryable. This is logical deletion, not secure erasure: database/file remnants, backups and transient process/browser memory can retain old data. The latest answer stays only in session memory for navigation; there is no disk answer history.

## Verify

```sh
uv run pytest -q -p no:cacheprovider
uv run ruff check --no-cache .
uv run ruff format --check --no-cache .
uv run mypy
uv run python -m pip check
uv run python -m pip_audit --progress-spinner off
```

See [User guide](docs/user_guide.md), [Architecture](docs/architecture.md), [Security](docs/security.md), [Methodology](docs/methodology.md) and [Milestone 3 results](docs/milestone_3_completion.md). The fictional probe scripts remain development tools, not an independent human-authored benchmark.

## Known limitations and remaining milestones

CPU answer generation is slow and model drafts can over-abstain or fail exact citation validation. Same-model support review is fallible. Native document parsers are not hardened resource sandboxes; OCR and complex layouts are unsupported. Chroma 1.5.9 has four unique unresolved server/configuration advisories (five audit entries, one duplicated). The app uses only the embedded backend with explicit vectors and exposes no Chroma HTTP server; see the scoped assessment in security.md. The audit is not clean.

Milestone 5 evaluation and Milestone 6 portfolio release remain pending. The complete end-to-end walkthrough will follow completion of the project.

Milestone 4 verification and remaining limitations: [completion report](docs/milestone_4_completion.md).

Milestone 5 evaluation tooling: [reproduction and metrics](docs/evaluation.md), [acceptance evidence and release blockers](docs/acceptance.md). The development dataset is AI-authored; independent human benchmark/support review remains pending.

Milestone 5 results and release blockers: [completion report](docs/milestone_5_completion.md).

# Installation and reproduction

KnowledgeBridge AI is a local, single-user development/portfolio application. Its software pipeline is implemented, but the [release blockers](acceptance.md#release-blockers) remain open. No human benchmark pass or production readiness is claimed.

## Prerequisites

Install Git, uv and Ollama using their official distributions. Use Python **3.12**; `pyproject.toml` excludes 3.13. Installation and model downloads need internet access. Normal operation uses local disk and loopback Ollama after installation.

The recorded development host is Intel macOS with CPU inference. Other platforms have not been verified here. The lockfile explicitly includes Intel macOS compatibility constraints. Model memory and latency depend on hardware; no minimum RAM or response-time guarantee has been established. Ensure space for the Python environment, both model downloads and your document index.

## Create the locked environment

```sh
git clone https://github.com/marclarouche/knowledgebridge-ai.git
cd knowledgebridge-ai
uv python install 3.12
uv sync --locked --group dev
uv run python --version
```

Run subsequent commands from the repository root. `--locked` rejects dependency drift; do not regenerate `uv.lock` to work around an installation error. Record the OS, architecture and full error first. Updating dependencies requires reviewing a new lock and rerunning checks.

## Install the local models

Start Ollama through its desktop application or `ollama serve` in a separate terminal. Use one service, listening on its default loopback port 11434. In another terminal:

```sh
ollama pull embeddinggemma:latest
ollama pull qwen3-vl:4b-instruct
ollama list
```

Model downloads are explicit operator actions; the app never pulls models. Model tags can change. The historical evaluation records exact digests in [the committed evidence](evidence/milestone5/knowledgebridge-m5-evaluation.json); a fresh pull may produce different outputs. The application checks embedding identity and requires a rebuild when it changes. Both configured models must run locally; cloud-backed models are rejected.

## Launch

```sh
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Open [KnowledgeBridge AI](http://127.0.0.1:8502). Repository settings disable telemetry and detailed browser errors. Keep the loopback address; this application has no authentication or multiuser access controls. Stop with Ctrl+C.

For an isolated fictional walkthrough, choose an unused directory instead of the normal library:

```sh
KNOWLEDGEBRIDGE_DATA_DIR="$PWD/work/portfolio-demo" uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

This environment-variable syntax is for macOS/Linux shells. The override points to application-owned storage; it does not import that directory's files. Original uploads are not retained. Normal storage is Git-ignored `data/index`; keep originals and protect backups containing extracted source text.

## Verify

```sh
uv run pytest -q -p no:cacheprovider
uv run ruff check --no-cache .
uv run ruff format --check --no-cache .
uv run mypy
uv run python -m pip check
uv run pip-audit --progress-spinner off
```

The October 17 run passed 136 tests, lint, formatting, strict typing and dependency consistency. The audit returned nonzero: five entries/four unique advisories in Chroma 1.5.9. A nonzero audit is an open finding, not an installation failure to suppress. See [security](security.md) and [evaluation](evaluation.md).

## Troubleshooting

| Symptom | Next action |
|---|---|
| Port 8502 already in use | Stop your earlier instance or select another loopback port and open that port in the browser. |
| Ollama unavailable/model missing | Start the local service, check `ollama list`, and compare model names with `config/knowledgebridge.yaml`. Keyword search and source inspection can work without Ollama. |
| Slow answer or timeout | CPU generation can exceed a minute; one answer can require two generation calls. A timeout is a service failure, not correct evidence abstention. Inspect diagnostics; do not assume a longer timeout fixes quality. |
| Embedding identity changed | Rebuild the collection index with the configured local model. |
| Pending documents absent from search | Build the active index in Index and Search. Import persistence and search activation are separate. |
| Stale form/reference | Reload the collection. Inspect current sources; superseded references are deliberately withheld. |
| Scanned PDF/poor extraction | Use externally prepared text/OCR and compare extracted passages with the original. OCR is outside this app. |
| Cleanup warning | Retry Clean obsolete index generations in Settings and Diagnostics. Deletion is logical, not secure erasure. |

Continue with the [guided walkthrough](user_guide.md#guided-fictional-walkthrough).

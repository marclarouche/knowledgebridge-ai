# KnowledgeBridge AI — Milestone 6 portfolio preparation

Prepared October 17, 2026. The user authorized resuming Phase 6 after the Phase 5 pause. This milestone packages the application for developer reproduction and portfolio review. The product is **not cleared for a validated release**: the Phase 5 human-evaluation, model-quality/performance and dependency blockers remain open.

## Deliverables

| PRD deliverable | Location |
|---|---|
| Installation guide | [Locked setup and troubleshooting](installation.md) |
| User guide | [Workflow and fictional walkthrough](user_guide.md) |
| Architecture diagram | [Mermaid system diagram and component boundaries](architecture.md#system-diagram) |
| Methodology and limitations | [Extraction/ranking methodology](methodology.md), [security scope](security.md) |
| Evaluation report | [Results and release decision](evaluation_report.md), [full Phase 5 evidence](milestone_5_completion.md) |
| Sample questions and answers | [Actual recorded successful, withheld and failed outputs](sample_answers.md) |
| Screenshots | [Live fictional-demo captures and provenance](screenshots/README.md) |
| Technical writing portfolio case study | [Problem, design, evidence and tradeoffs](portfolio_case_study.md) |

The README links these materials, includes both explicit model pulls, and describes the development/portfolio status. Removed stale milestone labels from the application header and demo description. No domain logic, dependencies, configured model/timeouts or original supplied PRD/technology notes changed.

## Reproduction evidence

A new Python 3.12.15 environment was created outside the normal project environment at `/private/tmp/knowledgebridge-m6-repro-venv`. `uv sync --locked --group dev` resolved the existing 135-package lock and installed 130 packages, including the editable local project. The first offline attempt correctly failed because the fresh cache lacked wheels; online installation then succeeded. This supports the documented distinction between online installation and offline operation after setup. The existing `.venv` and lockfile were preserved. This is a fresh environment on the same Intel macOS host, not independent cross-platform developer acceptance.

All **136 tests passed** in the fresh environment (90.46 seconds; five upstream SWIG deprecation warnings). Ruff lint and formatting passed (62 files); strict mypy passed across 19 source files; pip check found no broken requirements. A fresh pip-audit in that environment returned nonzero: five entries in Chroma 1.5.9, representing the same four unique advisories with no fixes listed. No advisory was suppressed. The local audit report is `/private/tmp/kb-m6-dependency-audit.json`.

The loopback Streamlit demo used isolated `/private/tmp/knowledgebridge-m6-demo` storage. The browser imported all eight bundled fictional manuals, built 31 passages using the already-installed `embeddinggemma:latest`, and retrieved the API authentication passage for `AUTH_REQUIRED` in hybrid mode. A second browser session reopened the persisted collection and active index. A live question, `What does AUTH_REQUIRED mean?`, returned an answered status with the expected HTTP 401 claim and exact API citation; Inspect source opened the current passage context. These checks did not use or mutate the normal library. Model tags/digests matched the preinstalled historical models; no model download was required.

Portfolio Markdown file links and sample-answer text/quoted slices were checked against the files and committed evaluation JSON; git diff --check passed. Screenshots were visually inspected. Historical output remains clearly distinct from the current browser walkthrough. Exact returned citations and a same-model support review do not establish independently verified semantic support.

## Release boundary

Phase 6 portfolio packaging does not close the [acceptance blockers](acceptance.md#release-blockers). At least 30 genuinely human-authored questions and independent support review are still absent; recorded answer failures, missed conflicts and latency still need product acceptance; Chroma findings remain unresolved. The full 33-case real-model evaluation was not rerun, no human review was invented, and no remote release/tag or production deployment was performed.

# Testing and evaluation

Milestone 5 separates software regression checks from evidence about model quality. The supplied FleetOps questions are AI-authored development cases, not the 30 human-authored benchmark required by PRD section 14. No independent human review has been performed. A model's own support review and an exact quote match do not establish answer support accuracy.

## Reproduce the development run

Use Python 3.12 and the locked environment, with the configured Ollama models already installed. From the project root:

```sh
uv sync --locked
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pip-audit --format json --output /tmp/kb-dependency-audit.json
uv run python scripts/evaluate_milestone5.py --answers --timeout 60 --output /tmp/kb-m5-evaluation.json
```

The evaluator imports the eight fictional samples into a temporary index and removes that index on normal exit. It never opens the application library. It refuses to overwrite an existing report, saves progress atomically after each case, and marks a run complete only when all selected cases finish. Output contains fictional questions, answers and excerpts; use only an approved non-sensitive dataset. Keep result files out of Git.

Omit `--timeout` to use the application's configured 240-second per-request budget. The recorded development run explicitly uses 60 seconds per generation request, not a 60-second end-to-end answer budget: an answered response usually needs both a draft and a review request. A timeout is a service failure, not an evidence abstention. `--case-ids RQ-001,RQ-025,RQ-031` selects an explicitly reported subset. Without `--answers`, only processing and retrieval run.

The evaluation stores the corpus SHA-256 values, dataset digest, exact configuration, model digests, platform, passage IDs, per-case outputs and timing. IDs and corpus targets are validated before model evaluation. Each relevance annotation must resolve to at least one exact indexed passage.

## Metrics and denominators

- **Passage Recall@k:** for each targeted question, count distinct annotated relevant passage IDs retrieved in the first k results divided by all relevant IDs resolved from its filename/substring annotations. Report the macro-average across targeted cases. This is recall against the supplied annotations, not exhaustive human relevance judgments. A source sentence split by changed chunking fails annotation validation rather than silently reducing the denominator.
- **Target hit rate@k:** proportion of targeted questions retrieving at least one relevant passage. This differs from recall when a question has multiple relevant passages. Untargeted questions have null retrieval scores; retrieval does not determine abstention.
- **Citation validity rate:** valid returned citation objects divided by all returned citation objects. Re-resolve generation, passage, quote, offsets and source metadata against active storage. Missing evidence references are reported separately. Zero citations yields null, never 100%.
- **Supported-answer coverage:** `answered` statuses divided by questions expected to be answerable. This is a status/availability measure, not semantic correctness.
- **Correct abstention rate:** explicit `insufficient_evidence` outputs divided by all attempted questions annotated unanswerable/partial/injection/unrelated. Generation and validation failures stay in the denominator and do not count as correct abstentions.
- **False-answer frequency:** `answered` outputs on questions annotated unanswerable divided by all attempted unanswerable cases. A zero rate can coexist with poor availability and must be read beside correct abstention and failure counts.
- **Conflict status rate:** `conflicting_evidence` outputs divided by explicitly unscoped conflict cases. Version-scoped historical questions may be answerable.
- **Document processing success:** accepted fictional imports divided by attempted imports, reported separately from malformed-input rejection regression tests.
- **Answer support accuracy:** null until independent human review. Humans must check every factual claim against cited evidence in its context, scope, version and question completeness, including reversed negation, invented values, omitted conditions and inappropriate authority selection.

## Independent review workflow

Obtain at least 30 questions actually authored by humans, covering supported, unsupported, exact-term, paraphrase and conflict cases. Do not relabel this development dataset as human-authored. Save an `EvaluationDataset` JSON with unique IDs, category, question, expected_status and filename/contains relevance targets. Record actual authorship and review the expected labels against the unchanged fictional corpus. `human_authored` is an attestation supplied by the dataset author; the software cannot verify a person's identity or authorship.

Run with `--dataset /path/to/human_questions.json`. Create an unfilled worksheet:

```sh
uv run python scripts/score_human_reviews.py --evaluation /tmp/kb-m5-evaluation.json --output /tmp/kb-review-worksheet.json
```

A reviewer should read the corresponding question, full source context, claims and citations in the evaluation report and original fictional manuals. Fill reviewer, verdict (`supported`, `unsupported`, or `not_applicable`) and rationale. Use `not_applicable` only for outputs without factual answered claims. Leave every row in the file. Empty fields are intentionally invalid and do not count as completed review.

```sh
uv run python scripts/score_human_reviews.py --evaluation /tmp/kb-m5-evaluation.json --reviews /tmp/kb-review-worksheet.json --output /tmp/kb-review-scores.json
```

The scorer rejects duplicate/unknown cases and reviews of changed answers using exact answer digests. It reports both support accuracy on reviewed answered outputs and review coverage; partial review is not a complete quality result. Human judgments and their rationales remain necessary even when citation validity is 100%.

## Offline and security verification scope

The development evaluator installs a Python audit hook that allows only literal loopback connections to the configured Ollama port and blocks external Python socket connects and external name resolution. Recorded blocked attempts must be investigated. This verifies application-level behavior with installed dependencies and local models; it is not an OS firewall, native-library sandbox or proof that the separate Ollama server cannot contact a network. The adapter rejects cloud-backed models, redirects and model downloads; it exposes no tool execution API.

Offline regression tests deny network access while parsing documents, building/querying embedded Chroma with fixture embeddings, using fixture generation, rendering all nine Streamlit views, and performing answer/source and library lifecycle interactions. Those fixtures test mechanics, not real model quality. The real evaluator separately exercises installed embeddings and generation under the process guard. No network interface is disabled or user service stopped for testing.

Security tests cover adversarial source instructions, inert script/URL text, a canary outside library storage, prohibited shell/execution paths, strict local endpoints, hostile FTS query/identifier inputs, malformed parser inputs, archive expansion/path limits, YAML bounds, model response bounds and stale references. These are scoped tests, not a penetration test or a hardened native-parser resource sandbox.

Ruff's optional security rule set flags three S608 dynamic SQL constructions in the index repository. The dynamic portions are internal FTS table names passed through `fts_table`, which accepts only `kb_` plus 32 lowercase hex characters. Queries/text/limits use SQLite parameters. The SQL-injection regression exercises hostile queries and rejects hostile table names; these three findings are reviewed identifier-construction false positives, not suppressed globally. Ordinary Ruff lint remains required.

See the milestone completion report for actual results and release blockers. A passing test suite alone is not permission to claim all P0 quality criteria or the product definition of done.

# Security and privacy

Source documents and questions are untrusted data. No document-directed shell commands, file operations, URL fetching, macros or HTML execution occur. Source excerpts render as inert text/code. Application diagnostics do not log source content, questions, vectors, raw parser exceptions or raw model responses.

Streamlit binds to 127.0.0.1 with telemetry and detailed UI exceptions disabled. Chroma uses only PersistentClient with anonymized telemetry disabled, no reset permission and no embedding function. Tests block Python network APIs during local indexing with fixture vectors and keyword retrieval. Normal model calls go only to configured loopback IP literals (127.0.0.1 or ::1). The HTTP adapter does not use environment proxies or follow redirects, does not pull models, checks the installed local model catalog and rejects cloud-backed model metadata. Operators must still trust their local Ollama service; a compromised loopback service is outside these controls.

Model/dependency downloads are explicit installation steps. There are no normal external inference/embedding APIs. Model weights are managed separately by Ollama.

Configuration is capped at 32 KiB with YAML SafeLoader and strict fields. File bytes, extracted text, sections, PDF pages, DOCX expansion, documents, passages, queries, model batches/responses and vector dimensions have bounds. Model socket timeouts are configurable. DOCX archives reject unsafe member paths, duplicates, encryption and DTD/entities. No files are extracted to disk. These controls are not a native-parser CPU/RAM sandbox; isolate genuinely hostile files. This single-user local app is not intended for public network exposure.

## Persistent data

Creating a collection or importing a source immediately saves extracted text and metadata to Git-ignored `data/index` (or the operator-selected `KNOWLEDGEBRIDGE_DATA_DIR`). Building additionally persists passages, keyword indexes and embeddings. Original binary uploads are not retained. Files are unencrypted local data protected by operating-system permissions. Deletion removes active saved/search records and then cleans retired generations. Failed cleanup is reported and retryable. Deleted collection IDs and timestamps remain as content-free tombstones to reject stale restoration. This is not secure erasure: filesystem/database remnants, backups, swap and transient browser/process memory may retain prior content. The latest answer/reference stays only in session memory for source navigation, not disk history.


Random internal generation names are validated before becoming SQLite identifiers. Source IDs and questions are SQL parameters or quoted token expressions; they cannot choose filesystem paths or tables. Failed builds do not replace active indexes. Source-link validation, fingerprints, FTS correspondence and vector ID/identity checks detect structural inconsistency. They do not protect against deliberate same-user database tampering or every numerical bit flip.

## Recovery

A missing/corrupt vector generation can be rebuilt from saved extracted sources using Build / rebuild. If the source/FTS catalog itself is corrupt, the app stops with a diagnostic. Stop the app, preserve the entire data directory as a backup, select a new empty application data directory using `KNOWLEDGEBRIDGE_DATA_DIR`, and reimport your original documents. Do not manually delete isolated database files from a running index. Dependency scanning excludes only the unpublished local package; report actual advisories from each run.

## Dependency audit — October 16, 2026

`pip-audit` for Chroma 1.5.9 reports five findings representing four unique advisories (PYSEC-2026-311 appears twice), with no fixed version listed:

| Advisory | Reported issue |
| --- | --- |
| [PYSEC-2026-311 / CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) | Server collection creation accepts dangerous remote model configuration |
| [PYSEC-2026-3814 / CVE-2026-45833](https://github.com/advisories/GHSA-36p7-vc44-83pf) | Server collection update permits remote-code model configuration |
| [PYSEC-2026-3815 / CVE-2026-45831](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) | Server RBAC does not scope permissions to resources |
| [PYSEC-2026-3813 / CVE-2026-45830](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) | Server tenant authorization bypass |

Applicability assessment: this application explicitly selects the embedded Rust backend with PersistentClient, starts no Chroma HTTP server, configures no server authentication/RBAC, accepts no user-specified embedding functions or remote model repositories, and supplies only validated explicit vectors. The reported server/configuration attack paths are not exposed by this design. This is a scoped assessment, not a claim that the installed package is vulnerability-free. The audit remains nonzero; no finding is suppressed. Reassess before adding a Chroma server, multiuser access, remote embedding configuration or public deployment, and review upstream fixes before release.


## Milestone 3 generation controls

Generation uses the same loopback-only, bounded no-proxy/no-redirect HTTP transport as embeddings. Installed local generation-model identity is checked before and after model work; cloud-backed metadata is rejected. Source passages and questions are untrusted JSON in a separate user message beneath fixed system policy. The model receives no tools, conversation history or ability to execute commands, open source paths or fetch URLs. Raw drafts are never rendered until schema, exact active-source citations and a separate support review pass. Output renders with text/code controls, including hostile quoted source text. Questions, prompts and answers are not logged or persisted by the application; transient process/browser memory and the separately operated Ollama service are outside a secure-erasure guarantee.

Prompt boundaries and a second call to the same model do not guarantee immunity to injection or hallucination. Citation existence and exact quotes are structural checks, not proof of entailment or source truth. The review call can share errors with the draft model. Missing, partial or unsupported details cause abstention when detected. Review is required for important use. Existing Chroma advisory findings remain unresolved as documented above.


## Milestone 4 mutation safety

Replacement validates source limits and metadata before committing any active change. Embedding/storage failures leave the prior source/index in place. Revision comparisons at both staging and activation reject stale sessions and concurrent writes; deleted collection tombstones prevent resurrection. UI confirmations are tied to collection/document identity and revision. Deletion of a remaining indexed library uses only validated retained vectors and requires no model/network. Obsolete generation cleanup is restricted to application-generated names, excludes active/staging generations under a database transaction, and never follows document-provided paths. Removal is logical and can leave physical remnants or backups.

Source Explorer accepts passage IDs as lookup data, not paths/commands. References must resolve within the active collection; a superseded generation or changed quote is marked outdated. The app does not display a cached answer as current after its index changes. Lifecycle tests operate on isolated fictional data; user-owned live collections are not deleted by verification.

## Milestone 5 verification

The security/offline regression suite checks hostile source text, no execution imports, a file canary, restricted endpoints, socket guards and SQL identifier/query injection. All nine Streamlit views render with socket access denied. The real evaluation permits only Python loopback socket activity to the configured local model port; this does not constrain native code or the separate Ollama server. No OS air-gap or native-parser sandbox is claimed. Three optional Ruff S608 findings are reviewed validated internal FTS identifiers, with values bound as SQL parameters and hostile input regression coverage. See [evaluation](evaluation.md) and [acceptance evidence](acceptance.md). Existing Chroma advisories remain open.

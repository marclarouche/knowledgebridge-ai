4. Recommended technology stack
Unlike the previous three applications, KnowledgeBridge AI needs persistent storage because we don't want to regenerate embeddings and rebuild the entire document collection every time the application starts.
I recommend using Chroma for semantic indexing and SQLite FTS5 for keyword search, with both stored locally.
Component	Technology	Purpose
Language	Python 3.12	Core application
Interface	Streamlit	Local browser-based user interface
Generation model	Ollama, configurable	Source-grounded answers
Embedding model	Ollama embedding model	Semantic search
Vector database	Chroma PersistentClient	Persistent embeddings and passage retrieval
Keyword search	SQLite FTS5	Exact and ranked keyword retrieval
Metadata	SQLite	Document catalog and indexing state
Document extraction	python-docx, PyMuPDF	DOCX and text-based PDF parsing
Schema validation	Pydantic v2	Documents, passages, citations, answers
Configuration	PyYAML	Chunking, retrieval, model settings
Testing	pytest, Streamlit AppTest	Unit and UI tests
Code quality	Ruff, mypy	Linting and type checking
Dependency security	pip-audit	Dependency vulnerability checks
Version control	Git	Project history
Chroma documents its local persistent client, while SQLite FTS5 provides a practical keyword search option without needing a search server. Streamlit's AppTest supports automated interface tests. 

Chroma Docs
+1



Local AI configuration
I would use two distinct models rather than one model for everything.

Embedding model
Initial candidate: embeddinggemma
Converts document passages and questions into numerical vectors for semantic retrieval. This model is documented as supported by Ollama, but we should verify its current availability and performance on your machine. 

GitHub







Generation model
A configurable locally installed instruction-tuned model
Produces answers from retrieved passages. The final choice should be based on your available RAM, inference speed, citation behavior, and evaluation results, rather than choosing the largest model.



For the MVP, I would avoid adding LangChain or LlamaIndex. They can be useful for more complex RAG applications, but implementing the small retrieval pipeline directly will give you greater visibility into chunking, ranking, citation validation, and abstention logic.
That is also more compelling from a portfolio perspective because you can explain exactly how the system works.
5. Repository structure

knowledgebridge-ai/
├── app.py
├── pyproject.toml
├── README.md
├── AGENTS.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── config/
│   └── knowledgebridge.yaml
├── src/
│   └── knowledgebridge/
│       ├── __init__.py
│       ├── models.py
│       ├── parsers/
│       │   ├── markdown.py
│       │   ├── plaintext.py
│       │   ├── docx.py
│       │   └── pdf.py
│       ├── chunker.py
│       ├── collection_manager.py
│       ├── metadata_store.py
│       ├── embedding_adapter.py
│       ├── vector_index.py
│       ├── keyword_index.py
│       ├── retriever.py
│       ├── ranker.py
│       ├── answer_generator.py
│       ├── evidence_validator.py
│       ├── citations.py
│       └── diagnostics.py
├── samples/
│   └── fleetops_demo/
│       ├── admin_security.md
│       ├── user_guide.md
│       ├── api_reference.md
│       ├── configuration.md
│       ├── troubleshooting.md
│       ├── release_notes.md
│       ├── faq.md
│       ├── legacy_configuration.md
│       └── evaluation_questions.json
├── tests/
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── security.md
│   ├── methodology.md
│   └── user_guide.md
└── data/
    └── .gitkeep



The data/ directory will hold local source copies, database records, and embeddings. All generated contents of this directory should be excluded from Git, apart from an empty placeholder if needed.
The core engine must never import Streamlit, and the sample dataset must remain clearly fictional.
6. Codex kickoff prompt
This prompt is designed to create the project foundation without prematurely introducing AI inference, vector indexing, or a full chatbot.
Copy it into Codex after creating the repository and saving the PRD as docs/PRD.md.

You are the lead software engineer for KnowledgeBridge AI v1.

PROJECT OVERVIEW

KnowledgeBridge AI is a local-first, source-grounded technical documentation assistant.

The application will use retrieval-augmented generation (RAG) to answer questions using a curated collection of technical manuals.

Answers must include verifiable source citations. When documentation is insufficient, the application must explicitly abstain rather than fabricate an answer.

Build MILESTONE 1 ONLY.

Read docs/PRD.md as the primary specification before implementing.

TECHNOLOGY STACK

Python 3.12
Streamlit
Pydantic v2
PyYAML
python-docx
PyMuPDF
pytest
Ruff
mypy
pip-audit
Git

Future milestones:
Ollama for embeddings and answer generation
Chroma for local vector indexing
SQLite FTS5 for keyword retrieval
SQLite for document metadata

Do not introduce the future milestone dependencies until necessary.

ARCHITECTURAL REQUIREMENTS

1. Streamlit is only the presentation layer.

2. All parsing, processing, and domain logic belongs in
   src/knowledgebridge/.

3. No module in src/knowledgebridge/ may import Streamlit
   or depend on Streamlit session state.

4. Use typed Python interfaces and Pydantic models.

5. Preserve document identifiers, document versions,
   section identifiers, page numbers, and source locations.

6. Design the architecture for future retrieval and citation
   validation, but do not implement AI or search yet.

7. Maintain a local-first security model.

8. Keep future AI adapters separate from domain logic.

9. Do not use LangChain or LlamaIndex in v1 unless a
   specific, documented technical need emerges.

MILESTONE 1 DELIVERABLES

1. Initialize the project repository.

Create:
pyproject.toml
README.md
AGENTS.md
.gitignore
.streamlit/config.toml
config/knowledgebridge.yaml

2. Create the Python package:

src/knowledgebridge/

Include only modules needed for Milestone 1.

3. Implement typed domain models.

At minimum:

KnowledgeCollection
SourceDocument
DocumentSection
DocumentPassage
ImportResult
ExtractionWarning
IndexStatus

Design source location objects to support:

document ID
document version
section or heading
PDF page number where available
character offsets where reliable
stable passage identifiers

4. Implement safe document import.

Supported formats:
TXT
Markdown
DOCX
Text-based PDF

Requirements:

UTF-8 processing where applicable
Maximum 10 MB per file
Configurable document and extraction limits
Malformed file detection
Duplicate content detection using SHA-256
Extraction warnings
No automatic execution of embedded content
No automatic external URL fetching

5. Implement document parsing.

Preserve:
headings where detectable
paragraph boundaries
DOCX table text
PDF page numbers
source offsets where reliable

Do not implement OCR.

Do not silently claim full support for diagrams,
images, comments, tracked changes, or complex tables.

6. Implement structure-aware chunking.

The chunker shall:

Prefer section and paragraph boundaries
Preserve document and section references
Generate stable passage identifiers
Support configurable chunk limits
Support configurable overlap
Avoid uncontrolled duplication
Provide reproducible output

Do not claim an optimized chunk size without evaluation.

7. Implement a basic Streamlit interface.

Views:

Knowledge Collections
Document Import
Parsed Documents
Passage Explorer
Settings and Diagnostics

Allow users to:

Create an in-session collection
Upload supported documents
Inspect extraction results
View normalized sections
Browse generated passages
See parsing and validation warnings

Do not create a functioning chat interface yet.

8. Create the fictional FleetOps Demo document collection.

Include:

Administrator Security Guide
User Guide
API Reference
Configuration Manual
Troubleshooting Guide
Release Notes
FAQ
Legacy Configuration Guide

Include realistic technical terminology, headings,
procedures, API paths, configuration examples,
and deliberately conflicting versioned information.

All sample material must be explicitly identified
as fictional.

9. Create automated tests.

Test:

Valid TXT import
Valid Markdown import
DOCX extraction
PDF extraction with page references
Corrupted files
Empty files
Oversized files
Duplicate detection
Stable document identifiers
Section extraction
Chunking boundaries
Chunk source references
Unsupported formats
Malicious embedded instructions treated as data
No unwanted external network activity

10. Add development tooling.

Configure:
pytest
Ruff
mypy
pip-audit

Pin dependencies through a supported lockfile workflow.

11. Create documentation.

README.md
docs/architecture.md
docs/security.md
docs/methodology.md
docs/user_guide.md

Include:
Installation instructions
Environment setup
Streamlit launch command
Supported document formats
Parsing limitations
Security model
Testing commands
Known limitations

SECURITY REQUIREMENTS

All processing must occur locally.

Bind Streamlit to 127.0.0.1 by default.

Do not implement cloud APIs.

No telemetry.

No automatic URL fetching.

No shell or filesystem commands sourced from
imported document content.

Treat imported text as untrusted data.

Apply file size and extraction limits.

Do not render uploaded text as unsafe HTML.

Do not log sensitive source document contents.

Use safe, generic user-facing error messages.

Preserve helpful non-sensitive developer diagnostics.

Design the future local storage directory so indexed
content and source documents cannot accidentally be
committed to a public Git repository.

OUT OF SCOPE

No Ollama integration.
No embeddings.
No vector database.
No keyword search engine.
No RAG answer generation.
No chat history.
No cloud synchronization.
No automatic publishing.
No user authentication.
No multiuser collaboration.
No agentic tool execution.

TESTING AND VERIFICATION

Run the available automated tests.

Run Ruff and mypy.

Run pip-audit where the environment permits.

Perform a local application smoke test.

Fix implementation defects found during testing.

Do not claim successful tests unless they actually ran.

Document environmental blockers and any unresolved
dependency security advisories.

COMPLETION REPORT

When Milestone 1 is complete, provide:

1. Files created and modified.
2. Architecture summary.
3. Import and parsing capabilities.
4. Document chunking implementation.
5. Installation and startup commands.
6. Actual test results.
7. Security observations.
8. Known limitations.
9. Readiness assessment for Milestone 2.

Do not proceed to Milestone 2 without a separate
instruction.



7. Development roadmap
KnowledgeBridge AI v1 milestones
1. Foundation and document ingestion
   Build the independent engine, parsers, passage models, chunking logic, and Streamlit interface.
   Codex kickoff
2. Indexing and retrieval
   Add Ollama embeddings, Chroma storage, SQLite keyword search, and hybrid ranking.
3. Answer generation
   Integrate a local instruction model, evidence gating, citation validation, and explicit abstention.
4. Library management
   Implement document replacement, reindexing, deletion, collection management, and source exploration.
5. Testing and evaluation
   Evaluate source retrieval, answer support, correct abstention, malicious inputs, and offline functionality.
6. Portfolio release
   Complete installation documentation, technical architecture, benchmark methodology, screenshots, and a case study.

8. Starting the project in Codex
On your Mac, create the new project:
mkdir -p ~/Projects/knowledgebridge-ai
cd ~/Projects/knowledgebridge-ai
git init


Open the folder in Codex, save the PRD as docs/PRD.md, and paste the kickoff prompt.
After the first milestone, the launch command should be:
streamlit run app.py


The local browser address will ordinarily be http://localhost:8501. If one of your other Streamlit applications is already running on that port, use a different port for KnowledgeBridge AI.
9. What will make this portfolio project stand out?
Of the five applications we're developing, KnowledgeBridge AI is arguably the strongest demonstration of AI integration with information architecture and source governance.
DocAudit AI shows that you can evaluate documentation quality. Sprint2Docs AI demonstrates that you understand engineering change management. Microcopy Lab showcases UX writing.
KnowledgeBridge AI adds the ability to design systems that make technical documentation discoverable and verifiable.
For the eventual LinkedIn announcement and portfolio, I would demonstrate three carefully selected questions against your fictional manuals: one with a supported answer and working citation, one that cannot be answered from the documents, and one where two document versions conflict.
That third example is especially valuable because it demonstrates something many AI demonstrations omit: the importance of recognizing uncertainty and conflicting documentation rather than producing a confident but potentially incorrect answer.
My recommendation: Build KnowledgeBridge AI with citation integrity and correct abstention as its defining capabilities. Don't prioritize conversational sophistication over evidence quality. A simple application that reliably reveals its sources and limitations will make a more credible technical writing portfolio piece than a sophisticated chatbot that cannot substantiate its answers.